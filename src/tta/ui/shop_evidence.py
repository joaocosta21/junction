"""The manufacturer's page beside an allergen question that is asked on the result, before any approval exists.

Scores on the 20% "autonomy and controls": where one person holds every role (the hotel, the bakery), the allergen
question is asked on the offer itself, so there is no approval yet to carry the web evidence. The person still
decides with the page in front of them: the same `Evidence` an approval carries (`tta.evidence`), for the products
of the option whose data does not rule out an excluded allergen (rule P-04).

Read from the recordings only (`fixtures/evidence/`): this route never asks Context.dev, whatever key is set, and
writes nothing. A product with no recorded page says so. Evidence changes no status and no decision.
"""

from __future__ import annotations

from tta.api.sandbox import KITCHEN_AGENT, Sandbox
from tta.config import Settings
from tta.contracts.errors import NotFound, TtaError
from tta.contracts.order import Evidence
from tta.contracts.product import Product
from tta.evidence.cache import EvidenceCache
from tta.evidence.finder import RECORDINGS_FOLDER, EvidenceFinder

NO_SUCH_OPTION = "This offer has no option {option_id}."


class _BookCatalog:
    """The products as this book's gateway answers them: all the finder asks of a catalog."""

    def __init__(self, book: Sandbox) -> None:
        self._book = book

    def get_product(self, product_id: str) -> Product | None:
        try:
            return self._book.service.get_product(KITCHEN_AGENT, product_id)
        except TtaError:
            return None


def recorded_evidence(book: Sandbox, settings: Settings, offer_id: str, option_id: str) -> tuple[Evidence, ...]:
    """What the recorded manufacturer pages say about the products of one option of an offer of this book that
    rule P-04 sends to a person; empty when the option asks no allergen question. Raises `NotFound` for an offer
    of another book or an option the offer does not have."""
    offer = book.service.get_offer(KITCHEN_AGENT, offer_id)
    option = offer.option(option_id)
    if option is None:
        raise NotFound(NO_SUCH_OPTION.format(option_id=option_id))
    if option.decision is None:
        return ()
    # `answers=None`: only recorded answers are read, and nobody is asked. The cache's own folder is the
    # recordings', which a finder without answers never writes to.
    recordings = settings.tta_fixtures_dir / RECORDINGS_FOLDER
    finder = EvidenceFinder(catalog=_BookCatalog(book), cache=EvidenceCache(recordings), answers=None)  # type: ignore[arg-type]
    return finder.for_approval(option, option.decision)
