#!/usr/bin/env python3
"""Shared image preparation for the vision provider scripts.

Why this exists
---------------
The provider scripts (anthropic/openai/gemini/azure) used to read a screenshot
and base64-encode it *verbatim* with no size bound, even though the skill's own
guidance says to "resize to 2000px max" (SKILL.md) and patterns.md ships an
unused ``preprocess_image`` helper. An un-capped full-page PNG produces a large,
slow, interruptible multimodal request. When several such requests stack up (or
retry), the call can hang for a very long time instead of failing fast.

This module makes that documented advice *automatic*: every screenshot is bounded
in **width** and in **encoded-payload size** before it is sent to any provider.

Design choices (and why)
------------------------
* **Cap WIDTH, not the longest edge.** Web screenshots are rendered at a target
  width; text legibility tracks width. Capping the *longest* edge would squash a
  tall full-page capture (e.g. 1280x8000 -> 320x2000), destroying the small text
  a journey check may depend on. We cap width instead, so a tall page keeps its
  rendered width and stays readable.
* **Downscale only.** A small image is never upscaled (no invented detail).
* **Aspect ratio is always preserved**, high-quality LANCZOS resampling.
* **The payload bound is a real, fail-closed bound.** If, after capping width to
  the legibility floor, the encoded image still exceeds the byte ceiling, we
  re-encode as progressively-lower-quality JPEG; if it *still* won't fit, we
  raise a clear error rather than silently sending an oversized payload (which
  is exactly the hang we are removing). This only ever triggers for pathological
  inputs (huge noisy photos), never for real UI screenshots.
* **EXIF orientation is honored** so sideways-captured text is not sent rotated.

Capture hygiene still matters: for text-critical verification prefer
viewport-sized captures and corroborate with browser/DOM facts (see SKILL.md
"Known Limitations for Web UI Analysis"). The cap removes a hang risk; it does
not make vision reliable for sub-pixel typography.
"""

from __future__ import annotations

import base64
import io
import os
import sys

# --- Tunable bounds -------------------------------------------------------
# Width cap (the legibility-critical dimension). Matches the skill's existing
# written advice ("resize to 2000px max", SKILL.md) so this wiring introduces no
# new policy -- it just enforces what the docs already recommend.
MAX_WIDTH = 2000

# Hard ceiling on the *encoded* (base64) payload, in bytes. Anthropic's
# per-image limit is 5 MB; 4 MB of base64 keeps us comfortably under it with
# headroom for the surrounding request envelope. This is enforced (fail-closed),
# not merely advisory.
MAX_ENCODED_BYTES = 4_000_000

# Never downscale width below this while chasing the payload ceiling. Protects
# small-text legibility. A 1024px-wide screenshot is far under the byte ceiling
# in practice, so this floor is only reached by pathological inputs.
MIN_WIDTH = 1024

# Bound on the width-shrink loop. Each step multiplies width by ~0.85.
_MAX_SHRINK_STEPS = 12

# JPEG qualities tried (high -> low) when a floored image still exceeds the
# ceiling and must be losslessly-then-lossily reduced to fit.
_JPEG_RESCUE_QUALITIES = (80, 70, 60, 50, 40)


def _require_pillow():
    """Import Pillow or fail with an actionable message.

    Capping is the whole point of this module; silently sending an un-capped
    image if Pillow is missing would reintroduce the exact fragility we are
    removing. So we fail loud with a fix instruction instead. The wrapper
    scripts (vision-analyze*.sh) install Pillow into the venv, so the supported
    path never hits this.
    """
    try:
        from PIL import Image, ImageOps  # noqa: F401

        return Image, ImageOps
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Pillow is required to prepare images for vision analysis "
            "(it bounds screenshot size so a large payload can't hang the "
            "request). Install it with: pip install pillow"
        ) from exc


def _output_format(pil_format: "str | None", ext: str) -> str:
    """Pick the encode format. Preserve the source format when it is one we can
    round-trip safely; otherwise fall back to PNG (lossless, keeps text
    crisp)."""
    fmt = (pil_format or "").upper()
    if fmt in {"PNG", "JPEG", "WEBP"}:
        return fmt
    if ext in {"jpg", "jpeg"}:
        return "JPEG"
    if ext == "webp":
        return "WEBP"
    return "PNG"


def _media_type_for(out_format: str) -> str:
    return {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }[out_format]


def _flatten_for_jpeg(image):
    """JPEG has no alpha and cannot hold CMYK cleanly; normalize to RGB."""
    if image.mode in ("RGBA", "LA", "P", "CMYK", "YCbCr", "I", "F"):
        return image.convert("RGB")
    return image


def _encode(image, out_format: str, quality: int = 90) -> bytes:
    """Encode a PIL image to bytes in ``out_format``."""
    buf = io.BytesIO()
    if out_format == "JPEG":
        _flatten_for_jpeg(image).save(
            buf, format="JPEG", quality=quality, optimize=True
        )
    elif out_format == "WEBP":
        image.save(buf, format="WEBP", quality=quality, method=4)
    else:  # PNG
        image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _encoded_len(data: bytes) -> int:
    return len(base64.standard_b64encode(data))


def _downscale_to_width(Image, image, target_width: int):
    """Return a copy scaled so width == target_width (aspect preserved).
    Downscale only -- if target_width >= current width, returns unchanged."""
    w, h = image.size
    if target_width >= w:
        return image
    scale = target_width / float(w)
    new_size = (target_width, max(1, round(h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def prepare_image_bytes(
    image_path: str,
    *,
    max_width: int = MAX_WIDTH,
    max_encoded_bytes: int = MAX_ENCODED_BYTES,
    min_width: int = MIN_WIDTH,
) -> "tuple[bytes, str]":
    """Load an image and return ``(processed_bytes, media_type)``, bounded so it
    cannot produce an oversized/interruptible vision request.

    Bounds applied, in order:
      1. Width capped to ``max_width`` (downscale only, aspect preserved).
      2. Encoded payload capped to ``max_encoded_bytes`` -- first by reducing
         width down to ``min_width``, then (if still over) by re-encoding as
         progressively-lower-quality JPEG. If it still cannot fit, raise.

    Raises FileNotFoundError if the path is missing, RuntimeError (with an
    actionable message) if Pillow is unavailable, the file is not a decodable
    image, or the image cannot be reduced under the payload ceiling.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    Image, ImageOps = _require_pillow()

    try:
        with Image.open(image_path) as img:
            img.load()
            src_format = img.format
            # Honor EXIF orientation, then detach a copy so the handle can close.
            image = ImageOps.exif_transpose(img)
            image = image.copy()
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to read image '{image_path}': {exc}") from exc

    ext = image_path.lower().rsplit(".", 1)[-1] if "." in image_path else ""
    out_format = _output_format(src_format, ext)
    media_type = _media_type_for(out_format)

    # 1. Width cap.
    if image.size[0] > max_width:
        image = _downscale_to_width(Image, image, max_width)

    # 2a. Payload cap by shrinking width, never below the floor.
    data = _encode(image, out_format)
    steps = 0
    while (
        _encoded_len(data) > max_encoded_bytes
        and image.size[0] > min_width
        and steps < _MAX_SHRINK_STEPS
    ):
        target_w = max(min_width, int(image.size[0] * 0.85))
        image = _downscale_to_width(Image, image, target_w)
        data = _encode(image, out_format)
        steps += 1

    # 2b. Still over at the width floor: re-encode lossily (JPEG) to GUARANTEE
    # the bound. Only pathological inputs (huge noisy photos) reach here.
    if _encoded_len(data) > max_encoded_bytes:
        for quality in _JPEG_RESCUE_QUALITIES:
            jpeg = _encode(image, "JPEG", quality=quality)
            if _encoded_len(jpeg) <= max_encoded_bytes:
                print(
                    f"note: '{os.path.basename(image_path)}' re-encoded to JPEG "
                    f"q{quality} to fit the {max_encoded_bytes // 1_000_000}MB "
                    "payload bound.",
                    file=sys.stderr,
                )
                return jpeg, "image/jpeg"
        # Truly cannot fit -- fail clearly rather than send an oversized payload.
        raise RuntimeError(
            f"Image '{os.path.basename(image_path)}' could not be reduced under "
            f"the {max_encoded_bytes // 1_000_000}MB payload bound even at "
            f"{image.size[0]}x{image.size[1]} JPEG q{_JPEG_RESCUE_QUALITIES[-1]}. "
            "Use a smaller or viewport-sized capture."
        )

    return data, media_type


def prepare_image_base64(
    image_path: str,
    *,
    max_width: int = MAX_WIDTH,
    max_encoded_bytes: int = MAX_ENCODED_BYTES,
    min_width: int = MIN_WIDTH,
) -> "tuple[str, str]":
    """Same as :func:`prepare_image_bytes` but returns a base64-encoded string
    (the form the Anthropic/OpenAI/Azure SDKs want)."""
    data, media_type = prepare_image_bytes(
        image_path,
        max_width=max_width,
        max_encoded_bytes=max_encoded_bytes,
        min_width=min_width,
    )
    return base64.standard_b64encode(data).decode("utf-8"), media_type
