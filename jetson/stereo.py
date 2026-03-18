"""
Clarity+ Stereo Vision Module
==============================
Stereo calibration (checkerboard), depth estimation, and user position tracking.
Designed for two USB webcams on Jetson Nano (cameras at configurable indices).

Usage:
    from stereo import StereoCalibrator, StereoDepthEstimator, estimate_user_position
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("stereo")

# ---------------------------------------------------------------------------
# SGBM defaults (tuned for 1080p parallel stereo at ~0.5 m - 5 m)
# ---------------------------------------------------------------------------
_NUM_DISPARITIES = 128
_BLOCK_SIZE = 5
_P1 = 8 * 3 * (_BLOCK_SIZE ** 2)
_P2 = 32 * 3 * (_BLOCK_SIZE ** 2)
_MIN_DEPTH = 0.2
_MAX_DEPTH = 10.0
_CLAHE_CLIP = 2.0
_CLAHE_GRID = 8
_MEDIAN_K = 5


# ═══════════════════════════════════════════════════════════════════════════
# StereoCalibrator
# ═══════════════════════════════════════════════════════════════════════════
class StereoCalibrator:
    """Collect checkerboard image pairs and run full stereo calibration."""

    def __init__(self, board_size: Tuple[int, int] = (9, 6), square_size_mm: float = 25.0):
        """
        Args:
            board_size: inner corner count (cols, rows) of the checkerboard.
            square_size_mm: physical size of one square in millimetres.
        """
        self.board_size = board_size
        self.square_size_mm = square_size_mm

        self._obj_points: List[np.ndarray] = []
        self._img_points_left: List[np.ndarray] = []
        self._img_points_right: List[np.ndarray] = []
        self._image_size: Optional[Tuple[int, int]] = None

        # Calibration outputs
        self.calibrated = False
        self.camera_matrix_left: Optional[np.ndarray] = None
        self.dist_coeffs_left: Optional[np.ndarray] = None
        self.camera_matrix_right: Optional[np.ndarray] = None
        self.dist_coeffs_right: Optional[np.ndarray] = None
        self.R: Optional[np.ndarray] = None
        self.T: Optional[np.ndarray] = None
        self.map_left: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self.map_right: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self.Q: Optional[np.ndarray] = None
        self.baseline_m: float = 0.0

        # 3-D object points for one checkerboard view
        objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
        objp *= square_size_mm
        self._objp_template = objp

    @property
    def pair_count(self) -> int:
        return len(self._obj_points)

    def capture_checkerboard(
        self, left: np.ndarray, right: np.ndarray
    ) -> Dict:
        """Detect checkerboard corners in a stereo pair.

        Returns dict with 'found', 'pair_index', and annotated images if found.
        """
        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if len(right.shape) == 3 else right

        flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        found_l, corners_l = cv2.findChessboardCorners(gray_l, self.board_size, flags)
        found_r, corners_r = cv2.findChessboardCorners(gray_r, self.board_size, flags)

        if not (found_l and found_r):
            return {"found": False, "pair_index": self.pair_count}

        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_l = cv2.cornerSubPix(gray_l, corners_l, (11, 11), (-1, -1), criteria)
        corners_r = cv2.cornerSubPix(gray_r, corners_r, (11, 11), (-1, -1), criteria)

        self._obj_points.append(self._objp_template.copy())
        self._img_points_left.append(corners_l)
        self._img_points_right.append(corners_r)

        if self._image_size is None:
            h, w = gray_l.shape[:2]
            self._image_size = (w, h)

        # Draw corners on copies for visual feedback
        vis_l = left.copy()
        vis_r = right.copy()
        cv2.drawChessboardCorners(vis_l, self.board_size, corners_l, True)
        cv2.drawChessboardCorners(vis_r, self.board_size, corners_r, True)

        logger.info("Checkerboard pair %d captured", self.pair_count)
        return {
            "found": True,
            "pair_index": self.pair_count,
            "annotated_left": vis_l,
            "annotated_right": vis_r,
        }

    def calibrate(self) -> Dict:
        """Run stereo calibration with collected pairs.

        Returns dict with 'success', 'rms_error', 'pairs_used', 'baseline_m'.
        """
        if self.pair_count < 10:
            return {
                "success": False,
                "error": f"Need >= 10 pairs, have {self.pair_count}",
            }

        w, h = self._image_size

        # Per-camera calibration for initial intrinsics
        flags_mono = 0
        _, mtx_l, dist_l, _, _ = cv2.calibrateCamera(
            self._obj_points, self._img_points_left, (w, h), None, None, flags=flags_mono
        )
        _, mtx_r, dist_r, _, _ = cv2.calibrateCamera(
            self._obj_points, self._img_points_right, (w, h), None, None, flags=flags_mono
        )

        # Stereo calibration
        flags_stereo = cv2.CALIB_FIX_INTRINSIC
        rms, mtx_l, dist_l, mtx_r, dist_r, R, T, E, F = cv2.stereoCalibrate(
            self._obj_points,
            self._img_points_left,
            self._img_points_right,
            mtx_l, dist_l, mtx_r, dist_r,
            (w, h),
            flags=flags_stereo,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6),
        )

        # Rectification
        R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
            mtx_l, dist_l, mtx_r, dist_r, (w, h), R, T, alpha=0
        )

        map_l1, map_l2 = cv2.initUndistortRectifyMap(mtx_l, dist_l, R1, P1, (w, h), cv2.CV_16SC2)
        map_r1, map_r2 = cv2.initUndistortRectifyMap(mtx_r, dist_r, R2, P2, (w, h), cv2.CV_16SC2)

        self.camera_matrix_left = mtx_l
        self.dist_coeffs_left = dist_l
        self.camera_matrix_right = mtx_r
        self.dist_coeffs_right = dist_r
        self.R = R
        self.T = T
        self.Q = Q
        self.map_left = (map_l1, map_l2)
        self.map_right = (map_r1, map_r2)
        # Baseline = magnitude of the translation vector (mm -> m)
        self.baseline_m = float(np.linalg.norm(T)) / 1000.0
        self.calibrated = True

        logger.info(
            "Stereo calibration complete: RMS=%.4f, baseline=%.3f m, pairs=%d",
            rms, self.baseline_m, self.pair_count,
        )
        return {
            "success": True,
            "rms_error": float(rms),
            "pairs_used": self.pair_count,
            "baseline_m": self.baseline_m,
        }

    def save(self, path: str) -> None:
        """Persist calibration to an .npz file."""
        if not self.calibrated:
            raise RuntimeError("Cannot save — not calibrated yet")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(
            path,
            camera_matrix_left=self.camera_matrix_left,
            dist_coeffs_left=self.dist_coeffs_left,
            camera_matrix_right=self.camera_matrix_right,
            dist_coeffs_right=self.dist_coeffs_right,
            R=self.R, T=self.T, Q=self.Q,
            map_left_1=self.map_left[0], map_left_2=self.map_left[1],
            map_right_1=self.map_right[0], map_right_2=self.map_right[1],
            image_size=np.array(self._image_size),
            baseline_m=np.array([self.baseline_m]),
        )
        logger.info("Calibration saved to %s", path)

    def load(self, path: str) -> bool:
        """Load calibration from disk. Returns True on success."""
        if not os.path.exists(path):
            return False
        data = np.load(path)
        self.camera_matrix_left = data["camera_matrix_left"]
        self.dist_coeffs_left = data["dist_coeffs_left"]
        self.camera_matrix_right = data["camera_matrix_right"]
        self.dist_coeffs_right = data["dist_coeffs_right"]
        self.R = data["R"]
        self.T = data["T"]
        self.Q = data["Q"]
        self.map_left = (data["map_left_1"], data["map_left_2"])
        self.map_right = (data["map_right_1"], data["map_right_2"])
        sz = data["image_size"]
        self._image_size = (int(sz[0]), int(sz[1]))
        self.baseline_m = float(data["baseline_m"][0])
        self.calibrated = True
        logger.info("Calibration loaded from %s (baseline=%.3f m)", path, self.baseline_m)
        return True

    def reset(self) -> None:
        """Discard all collected pairs and calibration data."""
        self._obj_points.clear()
        self._img_points_left.clear()
        self._img_points_right.clear()
        self.calibrated = False
        self.map_left = None
        self.map_right = None


# ═══════════════════════════════════════════════════════════════════════════
# StereoDepthEstimator
# ═══════════════════════════════════════════════════════════════════════════
class StereoDepthEstimator:
    """Compute depth maps from a calibrated stereo pair."""

    def __init__(self, calibrator: StereoCalibrator, processing_scale: float = 0.5):
        self._cal = calibrator
        self._scale = processing_scale

    @property
    def is_ready(self) -> bool:
        return self._cal.calibrated and self._cal.map_left is not None

    def rectify(
        self, left: np.ndarray, right: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Apply stereo rectification maps."""
        rect_l = cv2.remap(left, self._cal.map_left[0], self._cal.map_left[1], cv2.INTER_LINEAR)
        rect_r = cv2.remap(right, self._cal.map_right[0], self._cal.map_right[1], cv2.INTER_LINEAR)
        return rect_l, rect_r

    @staticmethod
    def _normalize_lighting(
        left_gray: np.ndarray, right_gray: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        clahe = cv2.createCLAHE(clipLimit=_CLAHE_CLIP, tileGridSize=(_CLAHE_GRID, _CLAHE_GRID))
        left_n = clahe.apply(left_gray)
        right_n = clahe.apply(right_gray)
        cdf_l = np.bincount(left_n.ravel(), minlength=256).cumsum().astype(np.float64)
        cdf_r = np.bincount(right_n.ravel(), minlength=256).cumsum().astype(np.float64)
        cdf_l /= cdf_l[-1] + 1e-6
        cdf_r /= cdf_r[-1] + 1e-6
        lut = np.interp(cdf_r, cdf_l, np.arange(256)).astype(np.uint8)
        return left_n, lut[right_n]

    def compute_depth(
        self, left: np.ndarray, right: np.ndarray
    ) -> np.ndarray:
        """Full pipeline: rectify -> disparity -> depth (metres).

        Returns a float32 depth map the same size as the *scaled* processing
        resolution (not full-res).
        """
        if not self.is_ready:
            raise RuntimeError("Stereo not calibrated")

        rect_l, rect_r = self.rectify(left, right)

        # Downscale for speed
        h, w = rect_l.shape[:2]
        pw, ph = int(w * self._scale), int(h * self._scale)
        proc_l = cv2.resize(rect_l, (pw, ph))
        proc_r = cv2.resize(rect_r, (pw, ph))

        gray_l = cv2.cvtColor(proc_l, cv2.COLOR_BGR2GRAY) if len(proc_l.shape) == 3 else proc_l
        gray_r = cv2.cvtColor(proc_r, cv2.COLOR_BGR2GRAY) if len(proc_r.shape) == 3 else proc_r

        gray_l, gray_r = self._normalize_lighting(gray_l, gray_r)

        nd = ((_NUM_DISPARITIES + 15) // 16) * 16
        nd = max(16, min(nd, gray_l.shape[1]))

        stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=nd,
            blockSize=_BLOCK_SIZE,
            P1=_P1, P2=_P2,
            disp12MaxDiff=1,
            uniquenessRatio=15,
            speckleWindowSize=200,
            speckleRange=16,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )
        disparity = stereo.compute(gray_l, gray_r)

        if _MEDIAN_K > 0:
            disparity = cv2.medianBlur(disparity, _MEDIAN_K)

        disp_px = disparity.astype(np.float32) / 16.0
        disp_px = np.where(disp_px > 0, disp_px, np.nan)

        fx = self._cal.camera_matrix_left[0, 0] * self._scale
        depth = (fx * self._cal.baseline_m) / disp_px
        depth = np.where(np.isfinite(depth), depth, np.nan)
        depth = np.clip(depth, _MIN_DEPTH, _MAX_DEPTH)
        depth = np.where(np.isfinite(depth), depth, 0.0)

        return depth


# ═══════════════════════════════════════════════════════════════════════════
# User position estimation
# ═══════════════════════════════════════════════════════════════════════════

def estimate_user_position(
    depth_map: np.ndarray,
    region: Optional[Tuple[int, int, int, int]] = None,
    fx: float = 1100.0,
    fy: float = 1100.0,
    cx: Optional[float] = None,
    cy: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    """Estimate user position relative to the camera.

    Args:
        depth_map: float32 depth in metres (processing-scaled resolution).
        region: (x, y, w, h) bounding box of the user in the depth map.
                If None, uses the centre 40 % of the frame.
        fx, fy: focal lengths in pixels (at depth_map resolution).
        cx, cy: principal point (defaults to image centre).

    Returns:
        {"depth_m", "horizontal_m", "height_m"} where:
        - depth_m: median depth in the region
        - horizontal_m: offset right of camera centre (negative = left)
        - height_m: offset above camera centre (negative = below)
    """
    h, w = depth_map.shape[:2]
    if cx is None:
        cx = w / 2.0
    if cy is None:
        cy = h / 2.0

    if region is not None:
        rx, ry, rw, rh = region
    else:
        margin_x, margin_y = int(w * 0.3), int(h * 0.3)
        rx, ry = margin_x, margin_y
        rw, rh = w - 2 * margin_x, h - 2 * margin_y

    rx = max(0, min(rx, w - 1))
    ry = max(0, min(ry, h - 1))
    rw = max(1, min(rw, w - rx))
    rh = max(1, min(rh, h - ry))

    roi = depth_map[ry : ry + rh, rx : rx + rw]
    valid = roi[(roi > _MIN_DEPTH) & (roi < _MAX_DEPTH)]

    if valid.size == 0:
        return {"depth_m": None, "horizontal_m": None, "height_m": None}

    depth_m = float(np.median(valid))

    centre_u = rx + rw / 2.0
    centre_v = ry + rh / 2.0

    horizontal_m = float((centre_u - cx) * depth_m / fx)
    height_m = float((cy - centre_v) * depth_m / fy)

    return {
        "depth_m": round(depth_m, 3),
        "horizontal_m": round(horizontal_m, 3),
        "height_m": round(height_m, 3),
    }
