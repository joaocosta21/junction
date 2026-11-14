"""A photo sent to the gateway: read from a multipart form in memory, never written to disk (task T18).

Scores on the 20% "guardrails": the upload is untrusted input. The gateway's body limit stays 64 KB on every
route but the two that take a photo, which allow one photo of at most 5 MB plus a small form; the body is read
into memory under that cap and parsed here with `python-multipart`, because the framework's own form parser
writes a file over 1 MB to a temporary file. Whether the bytes are an image is decided by the agent package from
their first bytes (`tta.agent.images`), before any model is asked.

    POST /v1/requests/read-image   the REST route (`tta.api.routes`)
    POST /run-photo                the first page's upload control (`tta.ui.request_page`)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field
from python_multipart.exceptions import FormParserError
from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from tta.api.docs import PROBLEM_REF
from tta.api.errors import BodyTooLarge, body_too_large_problem, problem_response
from tta.api.limits import MAX_BODY_BYTES, BodyLimitMiddleware
from tta.contracts.agent import Reading
from tta.contracts.errors import PROBLEM_CONTENT_TYPE, InvalidRequest
from tta.contracts.request import PurchaseRequest

KILOBYTE, MEGABYTE = 1024, 1024 * 1024
# The same 5 MB as `tta.agent.images.MAX_IMAGE_BYTES` (a test holds them equal): the gateway does not import the
# agent package, which is optional (`tta.api.hooks`).
MAX_IMAGE_BYTES = 5 * MEGABYTE
FORM_ALLOWANCE_BYTES = 64 * KILOBYTE  # the form's other fields and its framing
MAX_UPLOAD_BODY_BYTES = MAX_IMAGE_BYTES + FORM_ALLOWANCE_BYTES
MAX_FIELD_BYTES = 16 * KILOBYTE  # a text field of the form: the request box holds at most 2,000 characters
MAX_PARTS = 8
IMAGE_FIELD = "image"
FORM_TYPE = b"multipart/form-data"
READ_IMAGE_PATH = "/v1/requests/read-image"
PHOTO_PAGE_PATH = "/run-photo"
UPLOAD_PATHS = frozenset({READ_IMAGE_PATH, PHOTO_PAGE_PATH})
ACCEPTED_TYPES = "image/jpeg, image/png, image/webp, image/heic, image/heif"  # Gemini's list (`tta.agent.images`)

NOT_A_PHOTO_FORM = (
    "Send the photo as multipart/form-data, with one file in the field `image`: JPEG, PNG, WebP or HEIC, at "
    "most 5 MB."
)
PHOTO_TOO_LARGE = "The photo is larger than 5 MB, the most that is read. Send a smaller photo, or type the request."
BODY_TOO_LARGE = "The request body is larger than 5 MB and 64 KB, the most this route reads."

REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": [IMAGE_FIELD],
                    "properties": {
                        IMAGE_FIELD: {
                            "type": "string", "contentMediaType": "application/octet-stream",
                            "description": "One photo of the order list, at most 5 MB. Its first bytes decide "
                                           "its type; the declared type is not trusted.",
                        },
                    },
                },
                "encoding": {IMAGE_FIELD: {"contentType": ACCEPTED_TYPES}},
            },
        },
    },
}


def body_too_large_answer() -> dict[int | str, dict[str, object]]:
    """The 413 a photo route can answer, as the route documents it."""
    problem = body_too_large_problem(BODY_TOO_LARGE).model_dump(mode="json", exclude_none=True)
    return {413: {
        "description": "`invalid-request`: the body is larger than this route reads",
        "content": {PROBLEM_CONTENT_TYPE: {"schema": PROBLEM_REF, "example": problem}},
    }}


class ImageReading(BaseModel):
    """What `POST /v1/requests/read-image` answers: the lines read in the photo, word for word, and the typed
    request read from those lines, with who did each (`reading.sentence`)."""

    model_config = ConfigDict(frozen=True)

    transcription: tuple[str, ...] = Field(description="The lines read in the photo, top to bottom, as written.")
    request: PurchaseRequest = Field(description="The typed request read from those lines, as in reading.request.")
    reading: Reading


@dataclass(frozen=True)
class Upload:
    """One photo and the form's text fields, in memory."""

    image: bytes = field(repr=False)  # never shown in a repr, so never in a log line by mistake
    media_type: str  # as the sender declared it: not trusted
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class _Part:
    headers: dict[bytes, bytes] = field(default_factory=dict)
    data: bytearray = field(default_factory=bytearray)
    too_large: bool = False


class _Collector:
    """The parts of one multipart body, each held in memory up to its cap."""

    def __init__(self) -> None:
        self.parts: list[_Part] = []
        self._part = _Part()
        self._name = self._value = b""

    def callbacks(self) -> dict[str, object]:
        return {
            "on_part_begin": self._begin, "on_part_data": self._data, "on_part_end": self._end,
            "on_header_field": self._header_field, "on_header_value": self._header_value,
            "on_header_end": self._header_end,
        }

    def _begin(self) -> None:
        if len(self.parts) >= MAX_PARTS:
            raise InvalidRequest(NOT_A_PHOTO_FORM)
        self._part = _Part()

    def _data(self, data: bytes, start: int, end: int) -> None:
        if len(self._part.data) + end - start > MAX_IMAGE_BYTES:
            self._part.too_large = True  # the rest is not kept; the part is refused when the form is read
            return
        self._part.data.extend(data[start:end])

    def _end(self) -> None:
        self.parts.append(self._part)

    def _header_field(self, data: bytes, start: int, end: int) -> None:
        self._name += data[start:end]

    def _header_value(self, data: bytes, start: int, end: int) -> None:
        self._value += data[start:end]

    def _header_end(self) -> None:
        self._part.headers[self._name.strip().lower()] = self._value.strip()
        self._name = self._value = b""


def _upload(parts: list[_Part]) -> Upload:
    """The one photo of the field `image` and the text fields. Raises `InvalidRequest` for any other form."""
    images: list[_Part] = []
    fields: dict[str, str] = {}
    for part in parts:
        _, options = parse_options_header(part.headers.get(b"content-disposition", b""))
        name = options.get(b"name", b"").decode("utf-8", "replace")
        if b"filename" in options:
            if name != IMAGE_FIELD:
                raise InvalidRequest(NOT_A_PHOTO_FORM)
            images.append(part)
        elif len(part.data) <= MAX_FIELD_BYTES and not part.too_large:
            fields[name] = part.data.decode("utf-8", "replace")
        else:
            raise InvalidRequest(NOT_A_PHOTO_FORM)
    if len(images) != 1:
        raise InvalidRequest(NOT_A_PHOTO_FORM)
    (image,) = images
    if image.too_large:
        raise InvalidRequest(PHOTO_TOO_LARGE)
    media_type = image.headers.get(b"content-type", b"").decode("latin-1")
    return Upload(image=bytes(image.data), media_type=media_type, fields=fields)


def parse_form(body: bytes, content_type: str) -> Upload:
    """The photo and the fields of a `multipart/form-data` body. Raises `InvalidRequest` for anything else."""
    kind, options = parse_options_header(content_type)
    boundary = options.get(b"boundary")
    if kind != FORM_TYPE or not boundary:
        raise InvalidRequest(NOT_A_PHOTO_FORM)
    collector = _Collector()
    try:
        parser = MultipartParser(boundary, collector.callbacks())  # type: ignore[arg-type]
        parser.write(body)
        parser.finalize()
    except FormParserError as error:
        raise InvalidRequest(NOT_A_PHOTO_FORM) from error
    return _upload(collector.parts)


async def read_upload(request: Request) -> Upload:
    """The photo of this request, read into memory under the upload cap, never written to disk."""
    if not request.headers.get("content-type", "").lower().startswith(FORM_TYPE.decode()):
        raise InvalidRequest(NOT_A_PHOTO_FORM)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_UPLOAD_BODY_BYTES:
            raise BodyTooLarge(BODY_TOO_LARGE)
    return parse_form(bytes(body), request.headers["content-type"])


def _declared_length(scope: Scope) -> int | None:
    """The Content-Length of the request when it is a plain number; anything else is left to the body limit."""
    for name, value in scope.get("headers", ()):
        if name == b"content-length" and value.isdigit():
            return int(value)
    return None


class UploadBodyLimit:
    """The gateway's body limit (`tta.api.limits.BodyLimitMiddleware`): 64 KB on every route, and one photo with
    a small form on the two that take one. A photo route's declared length over its cap is answered here, with
    its own sentence, before anything is read."""

    def __init__(self, app: ASGIApp) -> None:
        self._default = BodyLimitMiddleware(app, max_bytes=MAX_BODY_BYTES)
        self._uploads = BodyLimitMiddleware(app, max_bytes=MAX_UPLOAD_BODY_BYTES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") not in UPLOAD_PATHS:
            await self._default(scope, receive, send)
            return
        declared = _declared_length(scope)
        if declared is not None and declared > MAX_UPLOAD_BODY_BYTES:
            await problem_response(body_too_large_problem(BODY_TOO_LARGE))(scope, receive, send)
            return
        await self._uploads(scope, receive, send)
