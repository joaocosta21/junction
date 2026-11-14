"""Web evidence for an approval that waits on a missing allergen statement (task S2).

Scores on the 20% controls (the dietitian decides with something in front of them) and on the brief's trust
protocol: Valio Aimo's data says nothing, so the claim stays unknown; what a manufacturer's page says is shown
beside it, labelled as not Valio data. Evidence never changes a status or a verdict: the finder only reads.

A line gets evidence when rule P-04 sent it to the dietitian and one of its findings is "no statement" or
"undeclared". Each product is looked up once: the stored answer first, then the recordings, then Context.dev.
Every case in which nothing can be shown is an `Evidence` with `found=False` and a sentence that says why.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Protocol

from tta.config import Settings
from tta.contracts.common import AllergenOutcome, AllergenRelation
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.order import Evidence
from tta.contracts.policy import PolicyDecision
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.evidence import wording
from tta.evidence.answers import AnswerRecord, AnswersClient, EvidenceUnavailable
from tta.evidence.cache import EvidenceCache
from tta.evidence.reading import read_answer

logger = logging.getLogger(__name__)

# The rule that sends a product to the dietitian when it does not rule out an excluded allergen
# (src/tta/policy/rules.yaml); it names the product it fired on.
ALLERGEN_TO_HUMAN_RULE = "P-04"
# The statements that leave the allergen unknown: nothing to read in Valio's data, so something to look up.
UNSTATED = frozenset({AllergenRelation.NOT_STATED, AllergenRelation.UNDECLARED})
MAX_PRODUCTS_PER_APPROVAL = 3  # each lookup can take up to 40 seconds
CACHE_FOLDER = "evidence"
RECORDINGS_FOLDER = "evidence"


class AnswerSource(Protocol):
    """What the finder asks: `AnswersClient`, or a stand-in in a test."""

    def ask(self, product: Product) -> AnswerRecord: ...


def _leaves_an_allergen_unstated(line: OfferLine) -> bool:
    check = line.allergen_check
    if check is None:
        return False
    return any(
        finding.outcome is AllergenOutcome.TO_HUMAN and finding.relation in UNSTATED for finding in check.findings
    )


def products_needing_evidence(option: OfferOption, decision: PolicyDecision) -> tuple[str, ...]:
    """The products of the option that P-04 sent to a human for an allergen they state nothing about."""
    fired = {rule.product_id for rule in decision.fired if rule.rule_id == ALLERGEN_TO_HUMAN_RULE and rule.product_id}
    chosen = (
        line.product_id for line in option.lines
        if line.product_id in fired and _leaves_an_allergen_unstated(line)
    )
    return tuple(dict.fromkeys(chosen))


def _none_found(product_id: str, reason: str) -> Evidence:
    return Evidence(product_id=product_id, found=False, sentence=wording.not_found(product_id, reason))


class EvidenceFinder:
    """Finds, stores and reads web evidence. `answers` is `None` when no key is set: then only stored and
    recorded answers are read."""

    def __init__(self, *, catalog: Catalog, cache: EvidenceCache, answers: AnswerSource | None) -> None:
        self._catalog = catalog
        self._cache = cache
        self._answers = answers
        self._lock = threading.Lock()  # one lookup at a time, so two approvals never pay for the same product

    def find_evidence(self, product: Product) -> Evidence:
        """What the manufacturer's page says about this product, or why nothing can be shown."""
        try:
            with self._lock:
                record = self._cache.get(product.id) or self._asked(product)
        except EvidenceUnavailable as unavailable:
            logger.warning("No web evidence for product %s: %s", product.id, unavailable.reason)
            return _none_found(product.id, unavailable.reason)
        return read_answer(record, product)

    def for_approval(self, option: OfferOption, decision: PolicyDecision) -> tuple[Evidence, ...]:
        """One evidence per product that needs it, in the order of the option's lines. Never raises for a lookup
        that fails: the approval goes on, and the evidence says what happened."""
        wanted = products_needing_evidence(option, decision)
        return tuple(
            self._for_id(product_id) if index < MAX_PRODUCTS_PER_APPROVAL
            else _none_found(product_id, wording.TOO_MANY.format(limit=MAX_PRODUCTS_PER_APPROVAL))
            for index, product_id in enumerate(wanted)
        )

    def close(self) -> None:
        close = getattr(self._answers, "close", None)
        if callable(close):
            close()

    def _asked(self, product: Product) -> AnswerRecord:
        if self._answers is None:
            raise EvidenceUnavailable(wording.NO_KEY)
        record = self._answers.ask(product)
        self._cache.put(record)  # stored whatever it says: it cost credits, and asking again costs as much
        return record

    def _for_id(self, product_id: str) -> Evidence:
        product = self._catalog.get_product(product_id)
        if product is None:
            return _none_found(product_id, wording.NOT_IN_CATALOG)
        try:
            return self.find_evidence(product)
        except (OSError, ValueError) as error:  # a cache that cannot be written, or data that cannot be read
            logger.error("Web evidence for product %s failed: %s", product_id, type(error).__name__, exc_info=error)
            return _none_found(product_id, wording.LOOKUP_FAILED)


def build_evidence_finder(settings: Settings, data_dir: Path, catalog: Catalog) -> EvidenceFinder | None:
    """The finder of the gateway, or `None` when no Context.dev key is set. Answers are stored under
    `<data_dir>/evidence/`; the recordings in `<fixtures>/evidence/` answer the demo products."""
    if not settings.has_context_dev_key:
        return None
    cache = EvidenceCache(data_dir / CACHE_FOLDER, recorded=settings.tta_fixtures_dir / RECORDINGS_FOLDER)
    return EvidenceFinder(catalog=catalog, cache=cache, answers=AnswersClient(settings))
