"""Untrusted uploads: file type, size limits, decompression bombs, metadata stripping."""

import io
import struct
import zlib

import numpy as np
import pytest
from PIL import Image

from app.jobs import config
from app.jobs.validate import ImageRejectionCode, InvalidImage, clean_image, sniff_format

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def encode(img: Image.Image, fmt: str, **kwargs: object) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def gradient(width: int = 40, height: int = 20) -> Image.Image:
    x = np.linspace(0, 255, width, dtype=np.uint8)
    rgb = np.dstack([np.tile(x, (height, 1))] * 3)
    return Image.fromarray(rgb, "RGB")


def rejection(data: bytes) -> ImageRejectionCode:
    with pytest.raises(InvalidImage) as err:
        clean_image(data)
    return err.value.code


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_accepts_supported_formats(fmt: str) -> None:
    clean = clean_image(encode(gradient(), fmt))

    assert clean.jpeg.startswith(b"\xff\xd8\xff")
    assert clean.rgb.shape == (20, 40, 3)
    assert Image.open(io.BytesIO(clean.jpeg)).format == "JPEG"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xff\xd8\xff\xe0rest", "JPEG"),
        (b"\x89PNG\r\n\x1a\nrest", "PNG"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "WEBP"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", None),
        (b"GIF89a", None),
        (b"%PDF-1.7", None),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", None),
        (b"", None),
    ],
)
def test_sniff_format_uses_magic_bytes(data: bytes, expected: str | None) -> None:
    assert sniff_format(data) == expected


def test_rejects_other_image_types_whatever_they_are_called() -> None:
    # A GIF is a valid image, but not one we accept, even if it's stored as photo.jpg.
    assert rejection(encode(gradient(), "GIF")) is ImageRejectionCode.UNSUPPORTED_IMAGE
    assert rejection(b"#!/bin/sh\nrm -rf /\n") is ImageRejectionCode.UNSUPPORTED_IMAGE


def test_rejects_files_over_the_byte_limit() -> None:
    data = b"\xff\xd8\xff" + b"\0" * config.MAX_UPLOAD_BYTES
    assert rejection(data) is ImageRejectionCode.IMAGE_TOO_LARGE


def test_rejects_a_file_whose_body_doesnt_match_its_magic_bytes() -> None:
    # PNG signature in front of a JPEG: parsed as PNG only, which fails.
    data = b"\x89PNG\r\n\x1a\n" + encode(gradient(), "JPEG")
    assert rejection(data) is ImageRejectionCode.IMAGE_UNREADABLE


def test_rejects_truncated_images() -> None:
    data = encode(gradient(400, 300), "JPEG")
    assert rejection(data[: len(data) // 3]) is ImageRejectionCode.IMAGE_UNREADABLE


def png_claiming_size(width: int, height: int) -> bytes:
    """A small, valid-looking PNG whose header claims width x height pixels."""
    data = bytearray(encode(Image.new("L", (8, 8)), "PNG"))
    # IHDR is the first chunk: 8-byte signature, 4-byte length, b"IHDR", then the data.
    start = 8 + 4
    assert data[start : start + 4] == b"IHDR"
    data[start + 4 : start + 12] = struct.pack(">II", width, height)
    crc = zlib.crc32(bytes(data[start : start + 4 + 13]))
    data[start + 4 + 13 : start + 4 + 13 + 4] = struct.pack(">I", crc)
    return bytes(data)


def test_rejects_decompression_bombs_from_the_header_without_decoding() -> None:
    # 100 000 x 100 000 px would need 10 GB once decoded. If the check ran after decoding,
    # this would raise "unreadable" (the pixel data is missing) or exhaust memory.
    bomb = png_claiming_size(100_000, 100_000)
    assert len(bomb) < 1000
    assert rejection(bomb) is ImageRejectionCode.IMAGE_TOO_LARGE


def test_accepts_images_just_under_the_pixel_limit_by_header() -> None:
    # 7000 x 7000 = 49 MP passes the size check (then fails decoding: no pixel data).
    assert rejection(png_claiming_size(7000, 7000)) is ImageRejectionCode.IMAGE_UNREADABLE


def test_strips_exif_gps_and_applies_orientation() -> None:
    img = gradient(40, 20)
    exif = img.getexif()
    exif[ORIENTATION] = 6  # "rotate 90° clockwise to display"
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (47.0, 22.0, 0.0), 3: "E", 4: (8.0, 32.0, 0.0)})
    raw = encode(img, "JPEG", exif=exif, icc_profile=b"fake icc profile", comment=b"secret")
    assert Image.open(io.BytesIO(raw)).getexif().get_ifd(GPS_IFD)

    clean = clean_image(raw)
    out = Image.open(io.BytesIO(clean.jpeg))

    assert out.size == (20, 40)  # turned upright
    assert clean.rgb.shape == (40, 20, 3)
    assert len(out.getexif()) == 0
    assert "icc_profile" not in out.info
    assert "comment" not in out.info
    assert b"Exif" not in clean.jpeg


def test_converts_transparent_and_palette_images_to_rgb() -> None:
    rgba = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    palette = gradient().convert("P")

    assert clean_image(encode(rgba, "PNG")).rgb.shape == (10, 10, 3)
    assert clean_image(encode(palette, "PNG")).rgb.shape == (20, 40, 3)
