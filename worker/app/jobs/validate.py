"""Untrusted upload bytes -> a clean JPEG, or a reason to refuse them.

The browser re-encodes photos before upload (#28), but anyone can call the Storage API
directly with their own token, so every file in the bucket is treated as hostile:

1. File type from the magic bytes (the file's first bytes), never from the stored
   content type or the file name.
2. Width x height read from the header and checked *before* decoding (decompression
   bombs: a few KB that decode to gigabytes).
3. Decode, apply the EXIF orientation, and write a fresh JPEG with no metadata at all:
   no EXIF (so no GPS position), no ICC profile, no comments. The UI only shows this copy.

Everything here is a pure function on bytes.
"""

import io
import warnings
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageOps

from app.jobs import config

RgbImage = npt.NDArray[np.uint8]

# Pillow has its own bomb guard: it warns above MAX_IMAGE_PIXELS and refuses at twice
# that. Our explicit check below runs first; this keeps Pillow's guard in line with it.
Image.MAX_IMAGE_PIXELS = config.MAX_PIXELS


class ImageRejectionCode(StrEnum):
    IMAGE_MISSING = "image_missing"
    UNSUPPORTED_IMAGE = "unsupported_image"
    IMAGE_TOO_LARGE = "image_too_large"
    IMAGE_UNREADABLE = "image_unreadable"


MESSAGES: dict[ImageRejectionCode, str] = {
    ImageRejectionCode.IMAGE_MISSING: (
        "We couldn't find your photo any more. Please upload it again."
    ),
    ImageRejectionCode.UNSUPPORTED_IMAGE: (
        "This file isn't a supported image. Please upload a JPEG, PNG or WebP photo."
    ),
    ImageRejectionCode.IMAGE_TOO_LARGE: (
        "This photo is too large to process. Please upload a photo of at most 10 MB and "
        "50 megapixels, for example straight from your phone's camera."
    ),
    ImageRejectionCode.IMAGE_UNREADABLE: (
        "We couldn't read this photo; the file may be damaged or incomplete. Please take "
        "the photo again and upload it."
    ),
}


class InvalidImage(Exception):  # noqa: N818 - an outcome, like pipeline.Rejection
    def __init__(self, code: ImageRejectionCode, detail: str = "") -> None:
        self.code = code
        self.message = MESSAGES[code]
        # For logs only; never shown to the user.
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else str(code))


@dataclass(frozen=True)
class CleanImage:
    # The re-encoded photo, upright, without metadata. Stored for the UI.
    jpeg: bytes
    # The same pixels as an RGB array (height, width, 3), for the pipeline.
    rgb: RgbImage


def sniff_format(data: bytes) -> str | None:
    """Pillow format name from the file's magic bytes, or None if it's not allowed."""
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def clean_image(data: bytes) -> CleanImage:
    """Check and re-encode an uploaded photo. Raises InvalidImage."""
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise InvalidImage(ImageRejectionCode.IMAGE_TOO_LARGE, f"{len(data)} bytes")

    fmt = sniff_format(data)
    if fmt is None:
        raise InvalidImage(ImageRejectionCode.UNSUPPORTED_IMAGE, f"magic bytes {data[:12]!r}")

    try:
        # Escalate Pillow's bomb *warning* to an error too.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            # open() only reads the header. formats= stops Pillow from trying any other
            # decoder, so the file is parsed as the type its magic bytes claim, or not at all.
            with Image.open(io.BytesIO(data), formats=[fmt]) as img:
                width, height = img.size
                if width * height > config.MAX_PIXELS:
                    raise InvalidImage(ImageRejectionCode.IMAGE_TOO_LARGE, f"{width}x{height} px")
                img.seek(0)  # animated PNG/WebP: the first frame only
                img.load()  # the actual decode
                upright = ImageOps.exif_transpose(img)
                rgb_img = upright.convert("RGB")
    except InvalidImage:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise InvalidImage(ImageRejectionCode.IMAGE_TOO_LARGE, str(e)) from e
    except Exception as e:
        # Truncated, corrupt or lying files. Pillow raises many different types here.
        raise InvalidImage(ImageRejectionCode.IMAGE_UNREADABLE, f"{type(e).__name__}: {e}") from e

    # A brand-new image from the bare pixels. Pillow carries some metadata of the decoded
    # file along (e.g. a JPEG comment in .info) and writes it again on save; an image
    # built from an array has none to carry.
    rgb = np.asarray(rgb_img, np.uint8)
    out = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(out, format="JPEG", quality=config.JPEG_QUALITY, optimize=True)
    return CleanImage(jpeg=out.getvalue(), rgb=rgb)
