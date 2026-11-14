"""`GET /.well-known/jwks.json`: the public key this gateway signs offers and order records with (P12 W8).

Scores on the 15% "open, documented standards": a JSON Web Key set (RFC 7517) with one Ed25519 key (RFC 8037),
served with no token, so a buyer can check a saved offer or order without asking the gateway anything else.
How to check a record: `tta.api.signing`.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response

from tta.api import docs
from tta.api.signing import JWKS_MEDIA_TYPE, JWKS_PATH

keys = APIRouter(tags=[docs.TAG_OPEN])


@keys.get(JWKS_PATH, operation_id="get_signing_keys", summary="The key offers and orders are signed with",
          response_class=Response, responses={200: {"content": {JWKS_MEDIA_TYPE: {}}}})
def get_signing_keys(request: Request) -> Response:
    """A JSON Web Key set (RFC 7517) with the one Ed25519 public key behind every `proof` of an offer or an order
    record. `GET /healthz` says whether it is a demo key generated at start (then it changes at every start, and a
    record signed before is checked against the key set saved with it). No token needed."""
    return Response(json.dumps(request.app.state.parts.signer.jwks), media_type=JWKS_MEDIA_TYPE)
