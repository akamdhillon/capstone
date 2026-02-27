"""
Clarity+ Face Service
=====================
Stateless face detection, enrollment, and recognition service.
Uses InsightFace (RetinaFace + ArcFace) via ONNX Runtime.
Runs on Jetson (TensorRT) or Mac (CPU) transparently.
"""

import base64
import time
import logging
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from insightface.app import FaceAnalysis

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("service.face")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Clarity+ Face Service")

# ---------------------------------------------------------------------------
# Global model reference (loaded once at startup)
# ---------------------------------------------------------------------------
face_app: Optional[FaceAnalysis] = None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class DetectRequest(BaseModel):
    image: str  # base64-encoded image


class EnrollRequest(BaseModel):
    images: List[str]  # list of base64-encoded images (5-10 recommended)


class KnownEmbedding(BaseModel):
    user_id: str
    embedding: List[float]  # 512 floats


class RecognizeRequest(BaseModel):
    image: str  # base64-encoded image
    known_embeddings: List[KnownEmbedding]


class AnalysisRequest(BaseModel):
    """Legacy request for orchestrator compatibility."""
    image_path: str


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
def load_models():
    """Load InsightFace models once at boot."""
    global face_app
    logger.info("Loading InsightFace models (buffalo_l) …")
    t0 = time.time()

    face_app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],  # safe default; TRT added on Jetson
    )
    # det_size controls the resolution fed to RetinaFace.
    # 640×640 is a good balance of speed and accuracy.
    face_app.prepare(ctx_id=-1, det_size=(640, 640))

    elapsed = time.time() - t0
    logger.info(f"Models loaded in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Health check for backend/orchestrator connectivity."""
    return {"status": "ok", "service": "face", "model_loaded": face_app is not None}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _decode_image(b64: str) -> np.ndarray:
    """Decode a base64 string to a BGR numpy image."""
    try:
        img_bytes = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image")
    return img


def _detect_single(img: np.ndarray) -> dict:
    """
    Run detection on *img* and return the highest-confidence face.
    Returns dict with keys: face, bbox, landmarks  (or None if no faces).
    """
    if face_app is None:
        raise HTTPException(status_code=503, detail="Face model not loaded yet")
    faces = face_app.get(img) or []
    if not faces:
        logger.warning("InsightFace get() returned no faces for this image.")
        return None

    # Pick the face with the highest detection score (same as test.py get_best_face)
    best = max(faces, key=lambda f: f.det_score)
    logger.info(f"InsightFace detected {len(faces)} faces. Best det_score: {best.det_score:.4f}, bbox: {best.bbox.astype(int).tolist()}")
    
    landmarks = best.kps.tolist() if best.kps is not None else []
    return {
        "face": best,
        "bbox": best.bbox.tolist(),           # [x1, y1, x2, y2]
        "landmarks": landmarks,               # 5-point landmarks
    }


def _get_embedding(face) -> np.ndarray:
    """
    Return the L2-normalised 512-d embedding from an InsightFace result.
    InsightFace already normalises by default, but we enforce it here.
    """
    emb = face.normed_embedding  # 512-d, already L2-normalised
    emb = emb / (np.linalg.norm(emb) + 1e-10)
    return emb


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity (both vectors should be L2-normalised → dot == cos)."""
    return float(np.dot(a, b))


def _bbox_xywh(bbox_xyxy: list) -> list:
    """Convert [x1,y1,x2,y2] → [x,y,w,h] for the API response."""
    x1, y1, x2, y2 = bbox_xyxy
    return [x1, y1, x2 - x1, y2 - y1]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# ── POST /face/detect ─────────────────────────────────────────────────────
@app.post("/face/detect")
async def detect(request: DetectRequest):
    """Detect the most prominent face in a base64 image."""
    t0 = time.time()
    img = _decode_image(request.image)
    result = _detect_single(img)

    latency = round((time.time() - t0) * 1000, 1)

    if result is None:
        return {
            "face_detected": False,
            "bbox": None,
            "landmarks": None,
            "latency_ms": latency,
        }

    return {
        "face_detected": True,
        "bbox": _bbox_xywh(result["bbox"]),
        "landmarks": result["landmarks"],
        "latency_ms": latency,
    }


# ── POST /face/enroll ─────────────────────────────────────────────────────
@app.post("/face/enroll")
async def enroll(request: EnrollRequest):
    """
    Generate a robust face embedding from 5-10 images.
    Steps:
      1. Detect + embed each image
      2. Remove outlier embeddings (> 1.5σ from mean)
      3. Average remaining embeddings
      4. L2-normalise the final vector
    """
    t0 = time.time()

    if len(request.images) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 images required (5-10 recommended)",
        )

    embeddings: List[np.ndarray] = []

    for idx, b64 in enumerate(request.images):
        img = _decode_image(b64)
        result = _detect_single(img)
        if result is None:
            logger.warning(f"No face found in image {idx}, skipping")
            continue
        emb = _get_embedding(result["face"])
        embeddings.append(emb)

    if len(embeddings) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 2 usable faces, only got {len(embeddings)}",
        )

    # ── Outlier removal ────────────────────────────────────────────────
    emb_stack = np.stack(embeddings)              # (N, 512)
    mean_emb = emb_stack.mean(axis=0)
    mean_emb = mean_emb / (np.linalg.norm(mean_emb) + 1e-10)

    # Cosine distances from mean
    cos_dists = 1.0 - emb_stack @ mean_emb       # lower = closer
    
    # If all images are very similar, sigma is near 0. 
    # Use a minimum threshold to avoid dropping good embeddings.
    sigma = cos_dists.std()
    threshold = max(1.5 * sigma, 0.15) # At least 0.15 distance allowed
    keep_mask = cos_dists <= threshold

    kept = emb_stack[keep_mask]
    if len(kept) < 1:
        # If everything was filtered, fall back to all
        kept = emb_stack

    # ── Final embedding ────────────────────────────────────────────────
    final_emb = kept.mean(axis=0)
    final_emb = final_emb / (np.linalg.norm(final_emb) + 1e-10)

    # Quality score = mean cosine similarity of kept embeddings to final
    quality = float(np.mean(kept @ final_emb))

    latency = round((time.time() - t0) * 1000, 1)

    logger.info("--- Face Enrollment Complete ---")
    logger.info(f"Submitted {len(request.images)} images, kept {int(keep_mask.sum())} faces (quality: {quality:.4f})")

    return {
        "embedding": final_emb.tolist(),
        "quality_score": round(quality, 4),
        "faces_processed": int(keep_mask.sum()),
        "faces_submitted": len(request.images),
        "latency_ms": latency,
    }


# ── POST /face/recognize ──────────────────────────────────────────────────
@app.post("/face/recognize")
async def recognize(request: RecognizeRequest):
    """
    Compare a probe image against a set of known embeddings.
    Returns the best match with confidence and match_type.
    """
    t0 = time.time()

    img = _decode_image(request.image)
    result = _detect_single(img)

    latency_fn = lambda: round((time.time() - t0) * 1000, 1)

    if result is None:
        return {
            "match": False,
            "user_id": None,
            "confidence": 0.0,
            "match_type": "no_face",
            "latency_ms": latency_fn(),
        }

    probe_emb = _get_embedding(result["face"])

    # Compare against every known embedding
    best_score = -1.0
    best_user = None

    logger.info(f"--- Face Recognition Started ---")
    logger.info(f"Comparing probe face against {len(request.known_embeddings)} known users")

    for known in request.known_embeddings:
        ref = np.array(known.embedding, dtype=np.float32)
        ref = ref / (np.linalg.norm(ref) + 1e-10)
        score = _cosine_similarity(probe_emb, ref)
        
        # Log every single comparison
        logger.info(f"  -> Compare vs user_id={known.user_id}: similarity = {score:.4f}")
        
        if score > best_score:
            best_score = score
            best_user = known.user_id

    logger.info(f"Best match: user_id={best_user} with similarity {best_score:.4f}")

    # ── Threshold logic ────────────────────────────────────────────────
    if best_score >= 0.70:
        match_type = "strong"
        matched = True
    elif best_score >= 0.60:
        match_type = "weak"
        matched = True
    else:
        match_type = "unknown"
        matched = False

    return {
        "match": matched,
        "user_id": best_user if matched else None,
        "confidence": round(best_score, 4),
        "match_type": match_type,
        "latency_ms": latency_fn(),
    }


# ── POST /analyze  (orchestrator compat) ──────────────────────────────────
@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """
    Legacy endpoint used by the orchestrator.
    Reads image from disk, detects face, returns basic info.
    """
    logger.info(f"Analyzing face for: {request.image_path}")

    try:
        img = cv2.imread(request.image_path)
        if img is None:
            return {"service": "face", "faces_detected": 0, "identity": "Unknown"}

        result = _detect_single(img)
        if result is None:
            return {"service": "face", "faces_detected": 0, "identity": "Unknown"}

        return {
            "service": "face",
            "faces_detected": 1,
            "identity": "Unknown",  # recognition requires known embeddings
            "bbox": _bbox_xywh(result["bbox"]),
        }
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        return {"service": "face", "faces_detected": 0, "identity": "Unknown"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
