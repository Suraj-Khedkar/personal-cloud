"""CLIP detection — only used when enable_clip: true. Requires high confidence."""

from __future__ import annotations

from pathlib import Path

_model = None
_processor = None
_device = None

JUNK_PROMPTS = [
    "a photograph of a laptop computer screen",
    "a photo of a computer monitor screen",
    "a screenshot of a computer display",
    "a photograph of a document or paper on a desk",
]

KEEP_PROMPTS = [
    "a portrait photograph of a person",
    "a landscape or nature photograph",
    "a photo of friends or family outdoors",
    "a vacation or travel photograph",
    "a selfie photograph",
    "a wedding or celebration photograph",
]


def _load_clip():
    global _model, _processor, _device
    if _model is not None:
        return _model, _processor, _device

    import torch
    from transformers import CLIPModel, CLIPProcessor

    _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    _model.eval()

    if torch.backends.mps.is_available():
        _device = "mps"
    elif torch.cuda.is_available():
        _device = "cuda"
    else:
        _device = "cpu"

    _model.to(_device)
    return _model, _processor, _device


def is_screen_or_document(
    path: Path,
    confidence_threshold: float = 0.55,
    margin_threshold: float = 0.25,
    has_camera_exif_fn=None,
) -> tuple[bool, str, float]:
    """High-confidence CLIP only — skips camera photos."""
    if has_camera_exif_fn and has_camera_exif_fn(path):
        return False, "", 0.0

    try:
        import torch
        from PIL import Image

        model, processor, device = _load_clip()

        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((512, 512))

        all_prompts = JUNK_PROMPTS + KEEP_PROMPTS
        inputs = processor(text=all_prompts, images=img, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image[0].softmax(dim=0).cpu().tolist()

        junk_probs = probs[: len(JUNK_PROMPTS)]
        keep_probs = probs[len(JUNK_PROMPTS) :]
        max_junk = max(junk_probs)
        max_junk_idx = junk_probs.index(max_junk)
        max_keep = max(keep_probs)
        margin = max_junk - max_keep

        if max_junk >= confidence_threshold and margin >= margin_threshold:
            label = JUNK_PROMPTS[max_junk_idx]
            return True, f"AI certain: {label} ({max_junk:.0%})", max_junk

        return False, "", max_junk

    except Exception:
        return False, "", 0.0


def clip_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False
