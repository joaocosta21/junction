"""What an upload must be to be read as a photo of an order list (task T18).

Scores on the 20% "guardrails": the image is untrusted input. It is checked here, by its own first bytes and
its size, before any model is asked; the type a sender declares is not trusted. It is held in memory only.

The accepted types are those the Gemini documentation lists for image input with `generateContent`
("Image understanding (generateContent)", aistudio.google.com/docs, read 14 Nov 2026): PNG, JPEG, WebP, HEIC
and HEIF. The same page limits a request with inline image data to 20 MB in all; ours stops at 5 MB a photo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from tta.contracts.errors import InvalidRequest

MEGABYTE = 1024 * 1024
MAX_IMAGE_MEGABYTES = 5
MAX_IMAGE_BYTES = MAX_IMAGE_MEGABYTES * MEGABYTE

JPEG, PNG, WEBP, HEIC, HEIF = "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"
ACCEPTED_TYPES = (JPEG, PNG, WEBP, HEIC, HEIF)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_RIFF, _WEBP = b"RIFF", b"WEBP"  # bytes 0-3 and 8-11 of a WebP file
_FTYP = b"ftyp"  # bytes 4-7 of an ISO media file: HEIC, HEIF, AVIF, MP4
_ISO_BRANDS_START, _BRAND_LENGTH = 8, 4
_ISO_HEADER_LENGTH = 16  # box size, "ftyp", major brand, minor version; the compatible brands follow
# Brands of an `ftyp` box (ISO/IEC 23008-12): HEVC-coded images are HEIC, the general image brands HEIF.
_HEIC_BRANDS = frozenset({b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"hevm", b"hevs"})
_HEIF_BRANDS = frozenset({b"mif1", b"msf1"})
_AVIF_BRANDS = frozenset({b"avif", b"avis"})  # AVIF also names mif1, and is not on Gemini's list

EMPTY = "The upload is empty. Send one photo of the order list: JPEG, PNG, WebP or HEIC, at most 5 MB."
TOO_LARGE = "The photo is larger than 5 MB, the most that is read. Send a smaller photo, or type the request."
NOT_AN_IMAGE = (
    "The upload is not a JPEG, PNG, WebP or HEIC image by its first bytes, so it was not read. "
    "Send a photo of the order list, or type the request."
)


@dataclass(frozen=True)
class CheckedImage:
    """An upload whose first bytes say it is an image Gemini accepts, of at most 5 MB. Held in memory only."""

    data: bytes = field(repr=False)  # never shown in a repr, so never in a log line or a trace by mistake
    media_type: str  # the type the first bytes give, never the one the sender declared

    @property
    def digest(self) -> str:
        """The SHA-256 of the image: how a recording names the photo it transcribes."""
        return hashlib.sha256(self.data).hexdigest()

    @property
    def size(self) -> int:
        return len(self.data)


def _iso_brands(data: bytes) -> frozenset[bytes]:
    """The major and compatible brands of the `ftyp` box an ISO media file opens with."""
    box_size = int.from_bytes(data[:4], "big")
    end = min(box_size, len(data))
    brands = {data[_ISO_BRANDS_START:_ISO_BRANDS_START + _BRAND_LENGTH]}
    brands.update(data[start:start + _BRAND_LENGTH] for start in range(_ISO_HEADER_LENGTH, end, _BRAND_LENGTH))
    return frozenset(brands)


def _iso_image_type(data: bytes) -> str | None:
    if len(data) < _ISO_HEADER_LENGTH or data[4:8] != _FTYP:
        return None
    brands = _iso_brands(data)
    if brands & _AVIF_BRANDS:
        return None
    if brands & _HEIC_BRANDS:
        return HEIC
    return HEIF if brands & _HEIF_BRANDS else None


def sniffed_type(data: bytes) -> str | None:
    """The image type the first bytes give, or `None` when they are not those of an accepted image."""
    if data.startswith(_PNG_SIGNATURE):
        return PNG
    if data.startswith(_JPEG_SIGNATURE):
        return JPEG
    if data[:4] == _RIFF and data[8:12] == _WEBP:
        return WEBP
    return _iso_image_type(data)


def checked_image(data: bytes) -> CheckedImage:
    """The upload as an image to read. Raises `InvalidRequest` for an empty upload, one over 5 MB, or one that
    is not an accepted image by its first bytes. Nothing of the upload is repeated in the error."""
    if not data:
        raise InvalidRequest(EMPTY, missing=["image"])
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidRequest(TOO_LARGE)
    media_type = sniffed_type(data)
    if media_type is None:
        raise InvalidRequest(NOT_AN_IMAGE)
    return CheckedImage(data=data, media_type=media_type)
