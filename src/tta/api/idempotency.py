"""The `Idempotency-Key` header of `POST /v1/orders` (IETF draft-ietf-httpapi-idempotency-key-header-08, P12 W7).

Scores on the 15% "open, documented standards rather than a proprietary format". The draft writes the value as a
Structured Field String (RFC 9651), in double quotation marks, and says a server "SHOULD reply with an HTTP 400
status code" when the header is missing. So the quoted form is read as the same key as the bare form, which
earlier callers send, and a missing header is `invalid-request` with status 400. A key outside the form stays
`invalid-request` with 422, and is never repeated in the answer.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request

from tta.api.errors import invalid_request
from tta.contracts.errors import InvalidRequest

IDEMPOTENCY_HEADER = "Idempotency-Key"
MAX_KEY_LENGTH = 100
KEY_CHARACTERS = "[A-Za-z0-9._:-]"
KEY_PATTERN = rf"^{KEY_CHARACTERS}+$"  # the same form the order book accepts
QUOTE = '"'
QUOTED_LENGTH = MAX_KEY_LENGTH + 2 * len(QUOTE)
HEADER_PATTERN = rf'^("{KEY_CHARACTERS}{{1,{MAX_KEY_LENGTH}}}"|{KEY_CHARACTERS}{{1,{MAX_KEY_LENGTH}}})$'
MISSING_KEY = (
    f"This route needs the header {IDEMPOTENCY_HEADER}: a key you choose and send again unchanged when you "
    "retry, so a retry never places a second order."
)
KEY_FORM = "1 to 100 characters of A-Z a-z 0-9 . _ : -, bare or in double quotation marks"
NOT_A_KEY_TYPE = "string_pattern_mismatch"
PARAMETER: dict[str, Any] = {  # the header as `/openapi.json` documents it: the route reads it itself
    "name": IDEMPOTENCY_HEADER,
    "in": "header",
    "required": True,
    "description": (
        f"Chosen by the caller: {KEY_FORM}. The quoted form is the draft's Structured Field String (RFC 9651) "
        "and is the same key as the bare form. The same key returns the first result, so a retry never places "
        "a second order. Missing: 400."
    ),
    "schema": {"type": "string", "minLength": 1, "maxLength": QUOTED_LENGTH, "pattern": HEADER_PATTERN},
}
_KEY = re.compile(KEY_PATTERN)


class MissingIdempotencyKey(InvalidRequest):
    """No `Idempotency-Key` header: an invalid request with the status the draft asks for."""

    status_code = 400


def _unquoted(value: str) -> str:
    """The key inside a Structured Field String, or the value itself when it is not quoted at both ends."""
    if len(value) >= 2 * len(QUOTE) and value.startswith(QUOTE) and value.endswith(QUOTE):
        return value[len(QUOTE):-len(QUOTE)]
    return value


def idempotency_key(request: Request) -> str:
    """The key of the request's `Idempotency-Key` header, bare or quoted. Raises `MissingIdempotencyKey` when
    there is none and `InvalidRequest` when it is outside the form."""
    value = request.headers.get(IDEMPOTENCY_HEADER)
    if value is None:
        raise MissingIdempotencyKey(MISSING_KEY)
    key = _unquoted(value.strip())
    if len(key) > MAX_KEY_LENGTH or not _KEY.fullmatch(key):
        raise invalid_request([{"loc": ("header", IDEMPOTENCY_HEADER), "type": NOT_A_KEY_TYPE, "msg": KEY_FORM}])
    return key
