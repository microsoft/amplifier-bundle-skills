"""Unit tests for the image-vision screenshot capping helper.

These tests exercise the resize/downscale + payload-bounding logic directly,
with no network calls. They require Pillow:  pip install pillow pytest

Run:  python -m pytest skills/image-vision/tests/test_image_utils.py
"""

import base64
import io
import os
import sys

import pytest

# Import the helper from the sibling examples/ directory.
EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
sys.path.insert(0, EXAMPLES_DIR)

from PIL import Image, ImageFilter  # noqa: E402

import image_utils  # noqa: E402


def _make_image(tmp_path, name, size, color=(123, 200, 75), mode="RGB"):
    """Write a solid-color image and return its path."""
    img = Image.new(mode, size, color)
    path = os.path.join(tmp_path, name)
    img.save(path)
    return path


def _make_noise_image(tmp_path, name, size, fmt="PNG", blur=0):
    """Write a random-noise image to force the payload ceiling to engage.

    Pure noise is ~incompressible (PNG and JPEG both stay large). A small blur
    makes it JPEG-friendly while PNG stays large -- useful for exercising the
    JPEG-rescue path deterministically."""
    w, h = size
    img = Image.frombytes("RGB", size, os.urandom(w * h * 3))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    path = os.path.join(tmp_path, name)
    img.save(path, format=fmt)
    return path


def _dims(data: bytes):
    with Image.open(io.BytesIO(data)) as im:
        return im.size


def _enc_len(data: bytes) -> int:
    return len(base64.standard_b64encode(data))


# --- Width cap ------------------------------------------------------------


def test_downscale_caps_width(tmp_path):
    path = _make_image(tmp_path, "big.png", (4000, 3000))
    data, media_type = image_utils.prepare_image_bytes(path, max_width=2000)
    w, h = _dims(data)
    assert w == 2000
    assert media_type == "image/png"


def test_aspect_ratio_preserved(tmp_path):
    path = _make_image(tmp_path, "wide.png", (4000, 1000))  # 4:1
    data, _ = image_utils.prepare_image_bytes(path, max_width=2000)
    w, h = _dims(data)
    assert w == 2000
    assert abs(w / h - 4.0) < 0.05


def test_no_upscale_small_image(tmp_path):
    path = _make_image(tmp_path, "small.png", (100, 80))
    data, _ = image_utils.prepare_image_bytes(path, max_width=2000)
    assert _dims(data) == (100, 80)  # unchanged -- never upscales


def test_exactly_at_cap_is_unchanged(tmp_path):
    path = _make_image(tmp_path, "edge.png", (2000, 1500))
    data, _ = image_utils.prepare_image_bytes(path, max_width=2000)
    assert _dims(data) == (2000, 1500)


def test_tall_fullpage_preserves_width(tmp_path):
    """A tall full-page capture must NOT be squashed: width is the
    legibility-critical dimension. 1280x8000 stays 1280 wide (it is a flat
    color image well under the payload ceiling)."""
    path = _make_image(tmp_path, "tall.png", (1280, 8000))
    data, _ = image_utils.prepare_image_bytes(path, max_width=2000)
    w, h = _dims(data)
    assert w == 1280  # width preserved, not crushed
    assert h == 8000  # height preserved (payload was already small)


# --- Payload cap (must be a REAL, fail-closed bound) ----------------------


def test_payload_ceiling_forces_width_downscale(tmp_path):
    # Noise barely compresses, so a 1600x1200 PNG is over a small ceiling.
    path = _make_noise_image(tmp_path, "noise.png", (1600, 1200))
    data, _ = image_utils.prepare_image_bytes(
        path, max_width=4000, max_encoded_bytes=400_000, min_width=256
    )
    assert _enc_len(data) <= 400_000  # actually under the ceiling
    w, _ = _dims(data)
    assert w >= 256  # floor respected


def test_payload_rescued_to_jpeg_at_floor(tmp_path):
    # At the width floor, a still-too-big PNG must be re-encoded to JPEG so the
    # returned payload is GUARANTEED under the ceiling -- never silently
    # oversized. Blurred noise: large as PNG, small as JPEG.
    path = _make_noise_image(tmp_path, "blur.png", (1024, 1024), blur=2)
    data, media_type = image_utils.prepare_image_bytes(
        path, max_width=4000, max_encoded_bytes=500_000, min_width=1024
    )
    assert _enc_len(data) <= 500_000  # actually under the ceiling
    assert media_type == "image/jpeg"  # had to fall back to JPEG to fit


def test_payload_bound_fails_closed_when_incompressible(tmp_path):
    # Pure noise that cannot be compressed under a tiny ceiling even at the
    # floor and lowest JPEG quality must RAISE -- never return an oversized
    # payload that could hang the request.
    path = _make_noise_image(tmp_path, "purenoise.png", (1024, 1024))
    with pytest.raises(RuntimeError):
        image_utils.prepare_image_bytes(
            path, max_width=4000, max_encoded_bytes=100_000, min_width=1024
        )


# --- Format / media type --------------------------------------------------


def test_jpeg_media_type(tmp_path):
    path = _make_image(tmp_path, "photo.jpg", (3000, 2000))
    data, media_type = image_utils.prepare_image_bytes(path, max_width=1000)
    assert media_type == "image/jpeg"
    with Image.open(io.BytesIO(data)) as im:
        assert im.format == "JPEG"


def test_cmyk_jpeg_normalized(tmp_path):
    # CMYK JPEGs must be normalized to RGB so providers/decoders accept them.
    path = _make_image(tmp_path, "cmyk.jpg", (1200, 800), color=(10, 20, 30, 40), mode="CMYK")
    data, media_type = image_utils.prepare_image_bytes(path, max_width=600)
    assert media_type == "image/jpeg"
    with Image.open(io.BytesIO(data)) as im:
        assert im.mode == "RGB"


def test_base64_helper_roundtrips(tmp_path):
    path = _make_image(tmp_path, "ui.png", (2400, 1200))
    b64, media_type = image_utils.prepare_image_base64(path, max_width=2000)
    assert media_type == "image/png"
    raw = base64.standard_b64decode(b64)
    with Image.open(io.BytesIO(raw)) as im:
        assert im.size[0] == 2000


# --- EXIF orientation -----------------------------------------------------


def test_exif_orientation_applied(tmp_path):
    # Build a portrait image, tag it orientation=6 (rotate 90 CW on display).
    # exif_transpose should swap dimensions so text isn't sent sideways.
    img = Image.new("RGB", (400, 200), (50, 100, 150))
    exif = img.getexif()
    exif[274] = 6  # 274 = Orientation tag
    path = os.path.join(tmp_path, "rot.jpg")
    img.save(path, exif=exif)
    data, _ = image_utils.prepare_image_bytes(path, max_width=4000)
    w, h = _dims(data)
    assert (w, h) == (200, 400)  # transposed


# --- Error handling -------------------------------------------------------


def test_missing_file_raises_filenotfound(tmp_path):
    missing = os.path.join(tmp_path, "does-not-exist.png")
    with pytest.raises(FileNotFoundError):
        image_utils.prepare_image_bytes(missing)


def test_non_image_raises_runtimeerror(tmp_path):
    path = os.path.join(tmp_path, "fake.png")
    with open(path, "w") as f:
        f.write("this is not an image")
    with pytest.raises(RuntimeError):
        image_utils.prepare_image_bytes(path)
