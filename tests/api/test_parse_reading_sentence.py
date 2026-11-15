"""`POST /v1/requests/parse` carries what the reader says of its own reading to a REST caller (lane FIX-A2, item 6).

Scores on the 20% "solving the problem": the reader now says, for example, that "50 packs" was read as 50 sales
units and that 5 kg of milk was read by weight. The shop page shows the whole reading; over REST the route
answered the typed request alone, so an agent never saw the sentence. It travels as the other reading facts do,
in a response header, and the body's shape does not change.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import unquote

from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import Reading, ReadingSource
from tta.contracts.common import Identity, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

Auth = Callable[..., dict[str, str]]
HEADER = "TTA-Reading-Sentence"
TYPED = PurchaseRequest(
    needed_by=date(2026, 11, 16),
    lines=(RequestLine(text="50 packs of oat drink", product_type="plant_drink", quantity=Decimal(50),
                       unit=Unit.UNIT),),
)
PACKS = (
    '"50 packs" is read as 50 sales units. A sales unit is the pack Valio Aimo sells a product in: one carton or '
    "one case, as the product says."
)
BEYOND_ASCII = 'Read by fixed rules.\r\nX-Injected: 1\t“crème fraîche” is read as 100% cream … for a café'


class Reader:
    """A parser whose reading says a sentence of the test's own."""

    def __init__(self, sentence: str) -> None:
        self._sentence = sentence

    def read(self, text: str, identity: Identity) -> Reading:
        return Reading(request=TYPED, source=ReadingSource.RULE_BASED, model="rule-based", sentence=self._sentence)

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return TYPED


def _parse(settings: Settings, catalog: ProductCatalog, auth: Auth, sentence: str) -> Any:
    parts = build_parts(settings, catalog=catalog, request_parser=Reader(sentence))
    with TestClient(create_app(settings, parts=parts)) as client:
        return client.post("/v1/requests/parse", json={"text": "50 packs of oat drink"}, headers=auth("agent_hotel"))


def test_the_readers_sentence_reaches_a_rest_caller_and_the_body_is_the_typed_request_alone(
    settings: Settings, catalog: ProductCatalog, auth: Auth
) -> None:
    answer = _parse(settings, catalog, auth, PACKS)

    assert answer.status_code == 200
    assert answer.headers[HEADER] == PACKS  # printable ASCII travels as written
    assert unquote(answer.headers[HEADER]) == PACKS
    assert (answer.headers["TTA-Read-By"], answer.headers["TTA-Reading-Source"]) == ("rule-based", "rule-based")
    assert answer.json() == TYPED.model_dump(mode="json")  # the body's shape did not change


def test_a_sentence_beyond_printable_ascii_is_one_header_line_that_decodes_to_the_sentence(
    settings: Settings, catalog: ProductCatalog, auth: Auth
) -> None:
    answer = _parse(settings, catalog, auth, BEYOND_ASCII)

    carried = answer.headers[HEADER]
    assert answer.status_code == 200 and "x-injected" not in answer.headers
    assert carried.isascii() and carried.isprintable()
    # Percent-decoding gives the sentence back, on one line: runs of white space are one space.
    assert unquote(carried) == " ".join(BEYOND_ASCII.split())
    assert "100%25 cream" in carried  # a percent sign of the sentence is itself encoded


def test_a_very_long_sentence_is_shortened_and_says_so(
    settings: Settings, catalog: ProductCatalog, auth: Auth
) -> None:
    answer = _parse(settings, catalog, auth, "A note of the reader. " * 200)

    carried = unquote(answer.headers[HEADER])
    assert answer.status_code == 200
    assert len(carried) <= 1000 and carried.endswith(" [shortened]")
    assert carried.startswith("A note of the reader. A note of the reader.")
