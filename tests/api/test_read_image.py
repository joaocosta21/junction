"""`POST /v1/requests/read-image`: a photo of an order list becomes a typed request, with what was read (task T18).

Scores on the 30% demo and the 20% "precise match": a kitchen writes its order on paper. Scores on the 20%
"guardrails": the upload is untrusted, held in memory, refused before any model call when it cannot be one,
and the route is rate limited as a model call. The parser here is a fake: the agent package is tested apart.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, uploads
from tta.api.limits import MAX_BODY_BYTES, RateLimit
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import Reading, ReadingSource
from tta.contracts.common import AuditReader, Identity, Unit
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.request import PurchaseRequest, RequestLine

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
ROUTE = "/v1/requests/read-image"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + bytes(64)
LINES = ["Tilaus", "Maito laktoositon 1000 l — ma"]
TEXT = "\n".join(LINES)
TYPED = PurchaseRequest(
    needed_by=date(2026, 11, 16),
    lines=(RequestLine(text=TEXT, product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                       quantity=Decimal(1000), unit=Unit.L),),
)
READING = Reading(
    request=TYPED, source=ReadingSource.MODEL, model="fake-model",
    sentence="Read from a photo: transcribed by fake-model, then read by fake-model.",
)


class PhotoParser:
    """A parser that can read a photo: it keeps what it was sent and answers with fixed lines."""

    model_id = "fake-model"

    def __init__(self, error: Exception | None = None, answer: Any = None) -> None:
        self.sent: list[tuple[bytes, str, str]] = []
        self._error = error
        self._answer = answer if answer is not None else (list(LINES), READING)

    def read(self, text: str, identity: Identity) -> Reading:
        return READING

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return TYPED

    def read_image(self, image: bytes, media_type: str, identity: Identity) -> tuple[list[str], Reading]:
        self.sent.append((image, media_type, identity.id))
        if self._error is not None:
            raise self._error
        return self._answer


class TextParser:
    """A parser of the port before task T18: it reads text and cannot be shown a photo."""

    model_id = "fake-model"

    def read(self, text: str, identity: Identity) -> Reading:
        return READING

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return TYPED


@pytest.fixture
def client_with(settings: Settings, catalog: ProductCatalog) -> Iterator[Callable[..., TestClient]]:
    opened: list[TestClient] = []

    def make(**parts: Any) -> TestClient:
        client = TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog, **parts)),
                            raise_server_exceptions=False)
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


def _photo(data: bytes = PNG, name: str = "list.png", media_type: str = "image/png") -> dict[str, Any]:
    return {"image": (name, data, media_type)}


# --- the answer -------------------------------------------------------------------------------------------


def test_a_photo_is_answered_with_its_transcription_its_typed_request_and_who_read_it(
    client_with: Callable[..., TestClient], auth: Auth
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(), headers=auth("agent_hotel"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"transcription", "request", "reading"}
    assert body["transcription"] == LINES
    assert PurchaseRequest.model_validate(body["request"]) == TYPED
    assert Reading.model_validate(body["reading"]) == READING
    assert (response.headers["TTA-Read-By"], response.headers["TTA-Reading-Source"]) == ("fake-model", "model")
    assert parser.sent == [(PNG, "image/png", "agent:hotel-kitchen")]  # the bytes as sent, the type as declared


def test_the_photo_route_takes_a_photo_larger_than_the_gateways_64_kb_body_limit(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)
    photo = PNG + bytes(2 * 1024 * 1024)

    accepted = client.post(ROUTE, files=_photo(photo), headers=auth("agent_hotel"))
    other_route = client.post("/v1/requests/parse", content=json.dumps({"text": "x" * MAX_BODY_BYTES}),
                              headers={**auth("agent_hotel"), "Content-Type": "application/json"})

    assert accepted.status_code == 200 and parser.sent[0][0] == photo
    assert_problem(other_route, "invalid-request", 413)  # every other route keeps its limit


def test_a_body_over_the_upload_limit_is_refused_with_413_before_the_parser_is_asked(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(PNG + bytes(uploads.MAX_UPLOAD_BODY_BYTES)), headers=auth("agent_hotel"))

    assert_problem(response, "invalid-request", 413)
    assert parser.sent == []


def test_a_photo_over_5_mb_in_a_body_under_the_limit_is_refused_before_the_parser_is_asked(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(PNG + bytes(uploads.MAX_IMAGE_BYTES)), headers=auth("agent_hotel"))

    body = assert_problem(response, "invalid-request", 422)
    assert "larger than 5 MB" in body["detail"]
    assert parser.sent == []


@pytest.mark.parametrize(
    "send",
    [
        {"json": {"image": "aGVsbG8="}},
        {"data": {"text": "1000 l milk"}, "files": {"note": ("note.txt", b"", "text/plain")}},
        {"files": [("image", ("a.png", PNG, "image/png")), ("image", ("b.png", PNG, "image/png"))]},
        {"files": {"photo": ("list.png", PNG, "image/png")}},
        {"content": b"--x\r\nnot a form", "headers": {"Content-Type": "multipart/form-data; boundary=x"}},
        {"content": b"", "headers": {"Content-Type": "multipart/form-data"}},
    ],
    ids=["json", "no-image-field", "two-images", "wrong-field", "broken-form", "no-boundary"],
)
def test_a_request_that_is_not_one_photo_in_a_form_is_refused_before_the_parser_is_asked(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem, send: dict[str, Any]
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)
    headers = {**auth("agent_hotel"), **send.pop("headers", {})}

    response = client.post(ROUTE, headers=headers, **send)

    body = assert_problem(response, "invalid-request", 422)
    assert "multipart/form-data" in body["detail"]
    assert parser.sent == []


def test_an_empty_photo_field_is_handed_on_and_refused_by_the_parser(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem
) -> None:
    parser = PhotoParser(error=InvalidRequest("The upload is empty.", missing=["image"]))
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(b""), headers=auth("agent_hotel"))

    assert assert_problem(response, "invalid-request", 422)["missing"] == ["image"]


# --- who may, and when not ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("who", "status"), [("hotel_purchasing", 403), ("supplier", 403), (None, 401)])
def test_only_a_buyers_agent_may_send_a_photo(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem, who: str | None, status: int
) -> None:
    parser = PhotoParser()
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(), headers=auth(who) if who else {})

    assert_problem(response, "not-authorised", status)
    assert parser.sent == []


@pytest.mark.parametrize("parser", [TextParser(), None], ids=["text-only-parser", "no-parser"])
def test_a_gateway_that_cannot_read_a_photo_answers_supplier_unavailable(
    client_with: Callable[..., TestClient], auth: Auth, assert_problem: Problem, parser: Any
) -> None:
    client = client_with(request_parser=parser)

    response = client.post(ROUTE, files=_photo(), headers=auth("agent_hotel"))

    body = assert_problem(response, "supplier-unavailable", 503)
    assert "POST /v1/offers" in body["detail"]


def test_a_photo_is_rate_limited_as_a_model_call(
    settings: Settings, catalog: ProductCatalog, auth: Auth, assert_problem: Problem
) -> None:
    parts = build_parts(settings, catalog=catalog, request_parser=PhotoParser(),
                        rate_limit=RateLimit(calls=1, window_seconds=60))
    with TestClient(create_app(settings, parts=parts)) as client:
        first = client.post(ROUTE, files=_photo(), headers=auth("agent_hotel"))
        second = client.post("/v1/requests/parse", json={"text": "1000 l milk"}, headers=auth("agent_hotel"))

    assert first.status_code == 200
    assert_problem(second, "rate-limited", 429)  # one window for every model call


def test_a_photo_that_cannot_be_read_is_refused_and_recorded_as_a_request_received(
    settings: Settings, catalog: ProductCatalog, auth: Auth, assert_problem: Problem, agent_hotel: Identity
) -> None:
    refusal = InvalidRequest("Line 1 does not say how much is needed.", missing=["lines[0].quantity"])
    parts = build_parts(settings, catalog=catalog, request_parser=PhotoParser(error=refusal))
    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.post(ROUTE, files=_photo(), headers=auth("agent_hotel"))
        events = parts.audit.view(AuditReader.BUYER, profile_id="hotel-kitchen").events

    assert assert_problem(response, "invalid-request", 422)["missing"] == ["lines[0].quantity"]
    (received,) = [event for event in events if event.type.endswith("request.received")]
    assert "photo" in received.sentence.lower() or "photo" in json.dumps(received.model_dump(mode="json")).lower()


def test_a_parser_that_answers_something_other_than_a_reading_is_a_fault_of_ours(
    settings: Settings, catalog: ProductCatalog, agent_hotel: Identity
) -> None:
    parts = build_parts(settings, catalog=catalog, request_parser=PhotoParser(answer=(LINES, TYPED)))

    with pytest.raises(TypeError):
        parts.service.read_image(agent_hotel, PNG, "image/png")
    parts.close()


def test_the_service_answers_the_lines_and_the_reading(
    settings: Settings, catalog: ProductCatalog, agent_hotel: Identity
) -> None:
    parts = build_parts(settings, catalog=catalog, request_parser=PhotoParser())

    assert parts.service.read_image(agent_hotel, PNG, "image/png") == (tuple(LINES), READING)
    with pytest.raises(SupplierUnavailable):
        build_parts(settings, catalog=catalog).service.read_image(agent_hotel, PNG, "image/png")
    parts.close()


# --- the document ------------------------------------------------------------------------------------------


def test_the_openapi_document_describes_the_upload_and_the_answer(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    operation = document["paths"][ROUTE]["post"]

    assert operation["operationId"] == "read_image" and operation["tags"] == ["Buyer agent"]
    assert operation["security"] == [{"bearerAuth": []}]
    form = operation["requestBody"]["content"]["multipart/form-data"]
    assert form["schema"]["required"] == ["image"]
    assert form["schema"]["properties"]["image"]["contentMediaType"] == "application/octet-stream"
    assert form["encoding"]["image"]["contentType"] == "image/jpeg, image/png, image/webp, image/heic, image/heif"
    answer = operation["responses"]["200"]
    assert set(answer["headers"]) == {"TTA-Read-By", "TTA-Reading-Source"}
    schema_name = answer["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    properties = document["components"]["schemas"][schema_name]["properties"]
    assert set(properties) == {"transcription", "request", "reading"}
    # FastAPI names a model's answer schema "<name>-Output" when the model is also a request body elsewhere.
    assert properties["request"]["$ref"].rsplit("/", 1)[-1] in ("PurchaseRequest", "PurchaseRequest-Output")
    assert properties["reading"]["$ref"].rsplit("/", 1)[-1] in ("Reading", "Reading-Output")
    assert {"401", "403", "413", "422", "429", "503"} <= set(operation["responses"])
    assert "5 MB" in operation["description"]


# --- the form, read in memory -------------------------------------------------------------------------------


def _form(*parts: tuple[str, str | None, bytes]) -> tuple[bytes, str]:
    """A multipart body of (field, file name or None, content) parts, and its Content-Type."""
    boundary = "t18-boundary"
    body = b""
    for name, filename, content in parts:
        disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
        body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\n\r\n".encode() + content + b"\r\n"
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def test_the_form_gives_the_photo_and_its_text_fields() -> None:
    body, content_type = _form(("csrf", None, b"token"), ("image", "list.png", PNG), ("text", None, "äö".encode()))

    upload = uploads.parse_form(body, content_type)

    assert (upload.image, upload.media_type) == (PNG, "")  # no declared type: the parser's first-bytes check decides
    assert upload.fields == {"csrf": "token", "text": "äö"}
    assert "PNG" not in repr(upload)


@pytest.mark.parametrize(
    "parts",
    [
        tuple(("field", None, b"x") for _ in range(uploads.MAX_PARTS)) + (("image", "a.png", PNG),),
        (("image", "a.png", PNG), ("text", None, b"x" * (uploads.MAX_FIELD_BYTES + 1))),
    ],
    ids=["too-many-parts", "text-field-too-long"],
)
def test_a_form_with_too_many_parts_or_too_long_a_field_is_refused(parts: tuple[Any, ...]) -> None:
    with pytest.raises(InvalidRequest, match="multipart/form-data"):
        uploads.parse_form(*_form(*parts))


def test_a_body_sent_without_a_length_is_still_read_only_up_to_the_cap() -> None:
    import asyncio

    from starlette.requests import Request

    from tta.api.errors import BodyTooLarge

    chunk = bytes(1024 * 1024)
    messages = [{"type": "http.request", "body": chunk, "more_body": True}] * 6
    messages.append({"type": "http.request", "body": b"", "more_body": False})

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    scope = {"type": "http", "method": "POST", "path": ROUTE, "headers": [
        (b"content-type", b"multipart/form-data; boundary=x"),
    ]}

    with pytest.raises(BodyTooLarge):
        asyncio.run(uploads.read_upload(Request(scope, receive)))
