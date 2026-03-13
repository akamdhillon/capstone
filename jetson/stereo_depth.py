#!/usr/bin/env python3
"""
Minimal Stereo Vision Depth Pipeline
===================================
Estimates depth from two 1080p USB webcams in a parallel stereo configuration.
Uses OpenCV and numpy only. Designed for macOS dev, portable to RPi/Jetson.

Usage: python stereo_depth.py
Click any pixel to print estimated depth. Press 'q' to quit.
"""

import cv2
import numpy as np
from typing import Tuple, Optional

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
WIDTH = 1920
HEIGHT = 1080
BASELINE_M = 0.122
FX = FY = 1100.0
NUM_DISPARITIES = 128
BLOCK_SIZE = 5
SGBM_MODE = cv2.STEREO_SGBM_MODE_SGBM_3WAY

# SGBM parameters
P1 = 8 * 3 * (BLOCK_SIZE ** 2)
P2 = 32 * 3 * (BLOCK_SIZE ** 2)

# Depth clamping (meters) - filter invalid/outlier values
MIN_DEPTH = 0.2
MAX_DEPTH = 10.0

# Processing scale: 1.0 = full 1080p (slower), 0.5 = half-res (faster, ~15-30 FPS)
PROCESSING_SCALE = 0.5

# Lighting normalization (helps when cameras have different exposure/white balance)
NORMALIZE_LIGHTING = True
CLAHE_CLIP_LIMIT = 2.0
CLAHE_GRID_SIZE = 8

# Disparity post-processing (reduces speckle/noise)
DISPARITY_MEDIAN_KERNEL = 5  # 0 = disabled

# Mouse click state
_click_point: Optional[Tuple[int, int]] = None


def _on_mouse(event: int, x: int, y: int, flags: int, userdata) -> None:
    """Store click coordinates for depth lookup."""
    global _click_point
    if event == cv2.EVENT_LBUTTONDOWN:
        _click_point = (x, y)


def normalize_lighting(left_gray: np.ndarray, right_gray: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Normalize brightness/contrast between left and right images.
    Reduces stereo matching errors when cameras have different exposure or white balance.
    Uses CLAHE (local contrast) + histogram matching (right matched to left).
    """
    if not NORMALIZE_LIGHTING:
        return left_gray, right_gray

    # CLAHE: local contrast normalization (handles uneven lighting per camera)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=(CLAHE_GRID_SIZE, CLAHE_GRID_SIZE))
    left_norm = clahe.apply(left_gray)
    right_norm = clahe.apply(right_gray)

    # Histogram match right to left (aligns global brightness so both look similar)
    cdf_left = np.bincount(left_norm.ravel(), minlength=256).cumsum()
    cdf_right = np.bincount(right_norm.ravel(), minlength=256).cumsum()
    cdf_left = cdf_left / (cdf_left[-1] + 1e-6)
    cdf_right = cdf_right / (cdf_right[-1] + 1e-6)
    lut = np.interp(cdf_right, cdf_left, np.arange(256)).astype(np.uint8)
    right_matched = lut[right_norm]

    return left_norm, right_matched


def capture_frames(
    cap_left: cv2.VideoCapture,
    cap_right: cv2.VideoCapture,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Capture synchronized frames from both cameras.
    Returns (left_frame, right_frame) or (None, None) on failure.
    """
    ret_l, frame_l = cap_left.read()
    ret_r, frame_r = cap_right.read()
    if not ret_l or not ret_r:
        return None, None
    return frame_l, frame_r


def compute_disparity(
    left: np.ndarray,
    right: np.ndarray,
) -> np.ndarray:
    """
    Compute disparity map from rectified stereo pair.
    Assumes parallel cameras (no geometric rectification applied).
    Intrinsics: fx=fy=1100, cx=width/2, cy=height/2, zero distortion.
    Uses Semi-Global Block Matching (SGBM).
    Input: grayscale left and right images.
    Output: disparity map (16-bit fixed-point, divide by 16 for pixel disparity).
    """
    # SGBM expects grayscale
    if len(left.shape) == 3:
        left_gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
    else:
        left_gray = left
    if len(right.shape) == 3:
        right_gray = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
    else:
        right_gray = right

    # Normalize lighting between cameras (CLAHE + histogram match)
    left_gray, right_gray = normalize_lighting(left_gray, right_gray)

    # numDisparities must be divisible by 16
    nd = ((NUM_DISPARITIES + 15) // 16) * 16
    nd = max(16, min(nd, left_gray.shape[1]))

    stereo = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=nd,
        blockSize=BLOCK_SIZE,
        P1=P1,
        P2=P2,
        disp12MaxDiff=1,
        uniquenessRatio=15,
        speckleWindowSize=200,
        speckleRange=16,
        mode=SGBM_MODE,
    )
    disparity = stereo.compute(left_gray, right_gray)

    # Post-process: median filter reduces speckle noise
    if DISPARITY_MEDIAN_KERNEL > 0:
        disparity = cv2.medianBlur(disparity, DISPARITY_MEDIAN_KERNEL)

    return disparity


def compute_depth(
    disparity: np.ndarray,
    focal_px: float = FX,
    baseline_m: float = BASELINE_M,
) -> np.ndarray:
    """
    Convert disparity map to depth in meters.
    depth = (focal_length_pixels * baseline_meters) / disparity_pixels
    Disparity from SGBM is in 16-bit fixed-point (divide by 16 for pixels).
    Invalid/zero disparity yields inf; we clamp to MIN_DEPTH/MAX_DEPTH.
    """
    # SGBM returns 16-bit fixed-point disparity
    disp_px = disparity.astype(np.float32) / 16.0

    # Avoid division by zero
    disp_px = np.where(disp_px > 0, disp_px, np.nan)
    depth = (focal_px * baseline_m) / disp_px

    # Clamp invalid values
    depth = np.where(np.isfinite(depth), depth, np.nan)
    depth = np.clip(depth, MIN_DEPTH, MAX_DEPTH)
    depth = np.where(np.isfinite(depth), depth, 0.0)
    return depth


def init_cameras() -> Tuple[Optional[cv2.VideoCapture], Optional[cv2.VideoCapture]]:
    """
    Open both cameras and set resolution to 1920x1080.
    Disable auto exposure and auto white balance where supported.
    """
    cap_left = cv2.VideoCapture(0)
    cap_right = cv2.VideoCapture(1)

    for i, cap in enumerate([cap_left, cap_right]):
        if not cap.isOpened():
            print(f"Failed to open camera {i}")
            return None, None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, 30)

        # Disable auto exposure and auto white balance (not all backends support)
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        try:
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        except Exception:
            pass

    # Sync exposure: set both to same manual value (helps with lighting mismatch)
    exp_val = 0.25
    cap_left.set(cv2.CAP_PROP_EXPOSURE, exp_val)
    cap_right.set(cv2.CAP_PROP_EXPOSURE, exp_val)

    # Warmup: discard a few frames so settings take effect
    for _ in range(5):
        cap_left.read()
        cap_right.read()

    return cap_left, cap_right


def main() -> None:
    global _click_point

    print("Stereo Depth Pipeline")
    print("--------------------")
    print("Click any pixel to print depth. Press 'q' to quit.")
    print("")

    cap_left, cap_right = init_cameras()
    if cap_left is None or cap_right is None:
        print("Could not open both cameras. Exiting.")
        return

    # Verify resolution
    w_l = int(cap_left.get(cv2.CAP_PROP_FRAME_WIDTH))
    h_l = int(cap_left.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w_r = int(cap_right.get(cv2.CAP_PROP_FRAME_WIDTH))
    h_r = int(cap_right.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Left camera: {w_l}x{h_l}, Right camera: {w_r}x{h_r}")

    # Window for display (we show 4 panels: left, right, disparity, depth)
    win_name = "Stereo Depth"
    cv2.namedWindow(win_name)
    cv2.setMouseCallback(win_name, _on_mouse)

    # Process and display at reduced resolution for ~15-30 FPS
    proc_w = int(WIDTH * PROCESSING_SCALE)
    proc_h = int(HEIGHT * PROCESSING_SCALE)

    frame_count = 0
    t_start = cv2.getTickCount()

    while True:
        left, right = capture_frames(cap_left, cap_right)
        if left is None or right is None:
            continue

        # Downsample for faster disparity (full res capture, process at proc_w x proc_h)
        left_proc = cv2.resize(left, (proc_w, proc_h))
        right_proc = cv2.resize(right, (proc_w, proc_h))

        # Compute disparity and depth (focal length scales with processing resolution)
        disparity = compute_disparity(left_proc, right_proc)
        focal_proc = FX * PROCESSING_SCALE
        depth = compute_depth(disparity, focal_px=focal_proc)

        # Normalize disparity for visualization (0-255)
        disp_vis = disparity.copy()
        disp_vis = np.clip(disp_vis, 0, NUM_DISPARITIES * 16)
        disp_vis = (disp_vis / (NUM_DISPARITIES * 16) * 255).astype(np.uint8)
        disp_vis = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)

        # Normalize depth for visualization (meters -> 0-255)
        depth_vis = depth.copy()
        depth_vis = np.clip(depth_vis, MIN_DEPTH, MAX_DEPTH)
        depth_vis = ((depth_vis - MIN_DEPTH) / (MAX_DEPTH - MIN_DEPTH) * 255).astype(np.uint8)
        depth_vis = cv2.applyColorMap(depth_vis, cv2.COLORMAP_VIRIDIS)

        # Build 2x2 layout (each panel proc_w x proc_h)
        top = np.hstack([left_proc, right_proc])
        bottom = np.hstack([disp_vis, depth_vis])
        combined = np.vstack([top, bottom])

        # Draw labels
        cv2.putText(combined, "Left", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(combined, "Right", (proc_w + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(combined, "Disparity", (10, proc_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(combined, "Depth (m)", (proc_w + 10, proc_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Handle mouse click - map display coords to depth pixel (2x2 grid)
        if _click_point is not None:
            dx, dy = _click_point
            _click_point = None
            px = dx % proc_w
            py = dy % proc_h
            px = max(0, min(px, depth.shape[1] - 1))
            py = max(0, min(py, depth.shape[0] - 1))
            d = depth[py, px]
            print(f"Depth at ({px}, {py}): {d:.2f} m")

        cv2.imshow(win_name, combined)

        # FPS
        frame_count += 1
        if frame_count % 30 == 0:
            t_now = cv2.getTickCount()
            fps = 30.0 / ((t_now - t_start) / cv2.getTickFrequency())
            t_start = t_now
            print(f"FPS: {fps:.1f}")

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
