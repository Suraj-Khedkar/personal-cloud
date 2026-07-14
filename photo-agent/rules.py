"""Detection rules — conservative: return match only when highly confident."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

COPY_NAME_RE = re.compile(r"\(\d+\)|\bcopy\b|~\d", re.IGNORECASE)

# Explicit screenshot filenames only
SCREENSHOT_RE = re.compile(
    r"(screenshot|screen[\s_.-]?shot|screencapture|simulator)",
    re.IGNORECASE,
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def perceptual_hash(path: Path) -> imagehash.ImageHash | None:
    try:
        with Image.open(path) as img:
            return imagehash.phash(img)
    except Exception:
        return None


def _load_grayscale(path: Path) -> np.ndarray | None:
    try:
        if path.suffix.lower() in {".heic", ".heif"}:
            with Image.open(path) as img:
                return np.array(img.convert("L"))
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    except Exception:
        return None


def _laplacian_variance(frame: np.ndarray) -> float:
    return float(cv2.Laplacian(frame, cv2.CV_64F).var())


def blur_scores(path: Path) -> dict[str, float] | None:
    frame = _load_grayscale(path)
    if frame is None:
        return None
    h, w = frame.shape
    full = _laplacian_variance(frame)
    y1, y2 = h // 4, 3 * h // 4
    x1, x2 = w // 4, 3 * w // 4
    center = _laplacian_variance(frame[y1:y2, x1:x2])
    tile_scores: list[float] = []
    rows, cols = 4, 4
    th, tw = h // rows, w // cols
    for r in range(rows):
        for c in range(cols):
            tile = frame[r * th : (r + 1) * th, c * tw : (c + 1) * tw]
            if tile.size > 0:
                tile_scores.append(_laplacian_variance(tile))
    max_tile = max(tile_scores) if tile_scores else full
    effective = max(center, max_tile)
    return {"full": full, "center": center, "max_tile": max_tile, "effective": effective}


def blur_score(path: Path) -> float | None:
    scores = blur_scores(path)
    return scores["effective"] if scores else None


def is_blurry(path: Path, threshold: float) -> tuple[bool, str, float]:
    """
    Only flags images that are blurry everywhere (subject AND full frame).
    Confidence 1.0 only when both are extremely low.
    """
    scores = blur_scores(path)
    if scores is None:
        return False, "", 0.0

    effective = scores["effective"]
    full = scores["full"]
    # Require entire image AND subject area to be extremely blurry
    if effective < threshold and full < threshold:
        return (
            True,
            f"entire image blurry (subject={effective:.1f}, full={full:.1f})",
            1.0,
        )
    return False, "", effective


def is_screenshot(path: Path, patterns: list[str]) -> tuple[bool, str, float]:
    """Only explicit screenshot filenames — no aspect-ratio guessing."""
    name = path.name
    if SCREENSHOT_RE.search(name):
        return True, f"filename is screenshot: {name}", 1.0
    name_lower = name.lower()
    for pat in patterns:
        if pat.lower() in name_lower:
            return True, f"filename contains '{pat}'", 1.0
    return False, "", 0.0


def has_camera_exif(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return False
            camera_tags = {271, 272, 306, 36867, 36868}
            return bool(camera_tags.intersection(set(exif.keys())))
    except Exception:
        return False


def _ocr_text(path: Path) -> str:
    try:
        import pytesseract
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((1200, 1200))
            return pytesseract.image_to_string(img).lower()
    except Exception:
        return ""


def is_greeting_illustration(
    path: Path,
    filename_phrases: list[str],
    ocr_keywords: list[str],
) -> tuple[bool, str, float]:
    """
    Only explicit wish phrases in filename or OCR text.
    No visual/text-density guessing — too many false positives.
    """
    name_lower = path.name.lower()

    for phrase in filename_phrases:
        if phrase.lower() in name_lower:
            return True, f"filename contains '{phrase}'", 1.0

    ocr = _ocr_text(path)
    if ocr:
        for kw in ocr_keywords:
            if kw.lower() in ocr:
                return True, f"image text contains '{kw}'", 1.0

    return False, "", 0.0


def pick_best_to_keep(paths: list[Path], blur_threshold: float) -> Path:
    """
    Choose the single copy to keep in Nextcloud.
    Prefer: no '(1)' in name → sharpest → largest → shortest path.
    """

    def rank(p: Path) -> tuple[int, float, int, int]:
        name = p.name
        is_copy = 1 if COPY_NAME_RE.search(name) else 0
        score = blur_score(p) or 0.0
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        return (is_copy, -score, -size, len(str(p)))

    return min(paths, key=rank)
