"""Free text becomes the typed request (SPEC sections 3 and 11; task T10).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". The model's answer
is a proposal held to a JSON Schema; this module validates it and turns it into the contract model.
What the text does not say (a quantity, a unit) is reported as `invalid-request` and never filled in. An answer
that does not validate is asked for once more, then refused.

An exclusion with no allergen rule at all (none in the text, none in the buyer's profile) is read as STRICT, and
the reading's sentence says so (replan P4 M3, decided 14 Nov 2026; it used to be a 422). STRICT is the safe
reading: it can only send more products to a person, never fewer. Valio Aimo, 14 Nov 2026: when the data leaves a
doubt, the safe product wins.

The answer is also held to the text itself, without a model (`tta.agent.textcheck`, task FIX-9): each quantity
must be a number the text gives, each unit one it names, `needed_by` the date the calendar rule gives for the
day it names (none when it names none), every allergen it excludes must be excluded, `require_confirmed` true
only when it asks for confirmed data, a product number a whole token of it, and a `prefer` other than the default
PRICE or a certificate label one it has a word for (task FALLBACK-1). A disagreement is a fault like
any other, named by its field: "the reading did not match the text". It is never corrected here. A text that
names no number, or no unit word, has its quantity or its unit reported as missing.

`read` says who read the text: the model just now, a recording of it, or a person (`tta.contracts.agent.Reading`).
`read_image` reads a photo of an order list: transcribed first, then read by `read` (`tta.agent.photo`, task T18).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError

from tta.agent.brands import NO_BRANDS, Brands
from tta.agent.days import helsinki_date
from tta.agent.faults import MAX_ANSWERS, NOT_JSON, Fault, validation_faults
from tta.agent.labels import reading_sentence
from tta.agent.model import AgentModel, ExtractCall
from tta.agent.notes import NO_USE_NAMED, with_notes
from tta.agent.photo import read_photo
from tta.agent.prompts import parser_instruction
from tta.agent.purpose import formula_matters
from tta.agent.schema import CLAIM_CODES, EXCLUDABLE_ALLERGEN_CODES, LABEL_CODES, checked_keys, proposal_schema
from tta.agent.textcheck import TextFacts
from tta.allergens import describe, normalise_code, parent_of
from tta.contracts.agent import Reading, ReadingSource
from tta.contracts.common import AllergenStrictness, Identity, PackPreference, Preference, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Clock
from tta.contracts.request import MAX_TEXT_LENGTH, PurchaseRequest

EMPTY_TEXT = "The text is empty: say what is needed and how much."
TEXT_TOO_LONG = "The text is longer than {limit:,} characters, the most that is read."
NOTHING_TO_ORDER = (
    "The text names nothing to order. Say what is needed and how much, for example "
    "200 litres of oat drink by Monday."
)
NO_PRODUCT = "Line {line} does not say which product is needed."
NO_QUANTITY = "Line {line} does not say how much is needed: the quantity is missing. A quantity is never guessed."
NO_UNIT = "Line {line} gives a quantity with no unit. Say litres, kilograms or sales units."
SAFE_READING = "No allergen rule was given"  # how the sentence below starts: the fallback keeps it
STRICT_ASSUMED = (
    SAFE_READING + " for {allergens}: read as strict, the safe reading. A product with no allergen statement "
    "goes to a person."
)
NOT_READ = (
    "The request could not be read into a typed request: after {answers} answers of the model, {faults}. "
    "Send the typed request to POST /v1/offers instead."
)
NOT_A_KEY = "not a key of the product-type table"
NOT_A_CLAIM = "not a nutritional claim code of the catalog"
NOT_AN_ALLERGEN = "not an allergen code a buyer can exclude"
NOT_A_LABEL = "not a certificate label code of the catalog"
BEFORE_TODAY = "before today ({today})"
NOT_MATCHED = "the reading did not match the text: {why}"
NO_SUCH_NUMBER = "the text gives no such number"
ANOTHER_UNIT = "the text names another unit"
ANOTHER_DAY = "the text names another day"
NO_DAY = "the text names no day"
A_DAY_LEFT_OUT = "the text names a day the reading leaves out"
EXCLUSION_LEFT_OUT = "the text excludes an allergen the reading leaves out"
NOT_ASKED_CONFIRMED = "the text does not ask for confirmed data"
NOT_IN_TEXT = "a product number that is not in the text"
NO_SUCH_LABEL = "the text names no such label"
NO_SUCH_PREFERENCE = "the text names no such preference"

logger = logging.getLogger(__name__)


class _Proposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LineProposal(_Proposal):
    """One line of the model's answer. `None` means the text does not say."""

    product_type: str | None
    product_ids: tuple[str, ...]
    name_terms: tuple[str, ...]
    required_claims: tuple[str, ...]
    quantity: Decimal | None
    unit: Unit | None
    exclude_allergens: tuple[str, ...]
    allergen_strictness: AllergenStrictness | None
    pack: PackPreference | None
    # The schema requires both fields below; a recording made before they existed (task FALLBACK-1) says neither.
    required_labels: tuple[str, ...] = ()
    # True only when the text names a use for which the formula matters ("for whipping"). A recording made before
    # the field existed (wave 2) does not say it.
    keep_formula: bool | None = None


class RequestProposal(_Proposal):
    needed_by: date | None
    require_confirmed: bool
    lines: tuple[LineProposal, ...]
    prefer: Preference | None = None


@dataclass(frozen=True)
class _Read:
    """A request read from one answer, and the allergens whose rule was read as STRICT because none was given."""

    request: PurchaseRequest
    read_as_strict: tuple[str, ...] = ()


@dataclass(frozen=True)
class Missing:
    """Something the buyer's text does not say and the typed request needs."""

    path: str
    sentence: str


def _proposal(answer: str) -> RequestProposal | tuple[Fault, ...]:
    try:
        data = json.loads(answer, parse_float=Decimal)  # a quantity is never a float
    except ValueError:
        return (Fault("answer", NOT_JSON),)
    if not isinstance(data, dict):
        return (Fault("answer", NOT_JSON),)
    try:
        return RequestProposal.model_validate(data)
    except ValidationError as error:
        return validation_faults(error)


def _mismatch(path: str, why: str) -> Fault:
    return Fault(path, NOT_MATCHED.format(why=why))


def _covered(code: str, excluded: set[str]) -> bool:
    """The text's exclusion is in the reading, itself or through its family (tree nuts cover almonds)."""
    family = parent_of(code)
    return code in excluded or (family is not None and family in excluded)


def _text_faults(at: str, line: LineProposal, facts: TextFacts) -> list[Fault]:
    """Where the line disagrees with the text. A quantity or a unit the text does not give at all is left to
    `_line_missing`, which reports it as missing."""
    faults = []
    if line.quantity is not None and facts.numbers and line.quantity not in facts.numbers:
        faults.append(_mismatch(f"{at}.quantity", NO_SUCH_NUMBER))
    if line.unit is not None and facts.units and line.unit not in facts.units:
        faults.append(_mismatch(f"{at}.unit", ANOTHER_UNIT))
    excluded = {normalise_code(code) for code in line.exclude_allergens}
    if not all(_covered(code, excluded) for code in facts.excluded):
        faults.append(_mismatch(f"{at}.exclude_allergens", EXCLUSION_LEFT_OUT))
    if any(product_id not in facts.id_tokens for product_id in line.product_ids):
        faults.append(_mismatch(f"{at}.product_ids", NOT_IN_TEXT))
    if any(label not in facts.labels for label in line.required_labels):
        faults.append(_mismatch(f"{at}.required_labels", NO_SUCH_LABEL))
    return faults


def _line_faults(index: int, line: LineProposal, facts: TextFacts, keys: Sequence[str]) -> list[Fault]:
    at = f"lines[{index}]"
    faults = []
    if line.product_type is not None and line.product_type not in keys:
        faults.append(Fault(f"{at}.product_type", NOT_A_KEY))
    if any(claim not in CLAIM_CODES for claim in line.required_claims):
        faults.append(Fault(f"{at}.required_claims", NOT_A_CLAIM))
    if any(normalise_code(code) not in EXCLUDABLE_ALLERGEN_CODES for code in line.exclude_allergens):
        faults.append(Fault(f"{at}.exclude_allergens", NOT_AN_ALLERGEN))
    if any(label not in LABEL_CODES for label in line.required_labels):
        faults.append(Fault(f"{at}.required_labels", NOT_A_LABEL))
    return faults + _text_faults(at, line, facts)


def _request_faults(proposal: RequestProposal, facts: TextFacts, today: date) -> list[Fault]:
    faults = []
    needed_by = proposal.needed_by
    if needed_by is None and facts.dates:
        faults.append(_mismatch("needed_by", A_DAY_LEFT_OUT))
    elif needed_by is not None and needed_by not in facts.dates:
        faults.append(_mismatch("needed_by", ANOTHER_DAY if facts.dates else NO_DAY))
    if needed_by is not None and needed_by < today:
        faults.append(Fault("needed_by", BEFORE_TODAY.format(today=today.isoformat())))
    if proposal.require_confirmed and not facts.asks_for_confirmed:
        faults.append(_mismatch("require_confirmed", NOT_ASKED_CONFIRMED))
    prefer = proposal.prefer
    if prefer not in (None, Preference.PRICE) and prefer not in facts.preferences:  # PRICE is the default
        faults.append(_mismatch("prefer", NO_SUCH_PREFERENCE))
    return faults


def _faults(
    proposal: RequestProposal, facts: TextFacts, today: date, keys: Sequence[str], text: str
) -> tuple[Fault, ...]:
    """What the schema cannot hold the model to: our tables, the buyer's text and the clock."""
    lines = [fault for index, line in enumerate(proposal.lines) for fault in _line_faults(index, line, facts, keys)]
    names_a_use = formula_matters(text)
    formula = [_mismatch(f"lines[{index}].keep_formula", NO_USE_NAMED)
               for index, line in enumerate(proposal.lines) if line.keep_formula and not names_a_use]
    return (*_request_faults(proposal, facts, today), *lines, *formula)


def _line_missing(index: int, line: LineProposal, facts: TextFacts) -> list[Missing]:
    at, number = f"lines[{index}]", index + 1
    missing = []
    if line.product_type is None and not line.product_ids and not line.name_terms:
        missing.append(Missing(f"{at}.product_type", NO_PRODUCT.format(line=number)))
    if line.quantity is None or not facts.numbers:  # a text with no number gives no quantity, whatever was read
        missing.append(Missing(f"{at}.quantity", NO_QUANTITY.format(line=number)))
    elif line.unit is None or not facts.units:
        missing.append(Missing(f"{at}.unit", NO_UNIT.format(line=number)))
    return missing


def _has_no_rule(line: LineProposal, profile_strictness: AllergenStrictness | None) -> bool:
    return bool(line.exclude_allergens) and line.allergen_strictness is None and profile_strictness is None


def _safely_strict(
    proposal: RequestProposal, profile_strictness: AllergenStrictness | None
) -> tuple[RequestProposal, tuple[str, ...]]:
    """The proposal with STRICT on every line that excludes an allergen under no rule at all, and those allergens'
    codes, each once."""
    lines = tuple(
        line.model_copy(update={"allergen_strictness": AllergenStrictness.STRICT})
        if _has_no_rule(line, profile_strictness) else line
        for line in proposal.lines
    )
    codes = [normalise_code(code) for line in proposal.lines if _has_no_rule(line, profile_strictness)
             for code in line.exclude_allergens]
    return proposal.model_copy(update={"lines": lines}), tuple(dict.fromkeys(codes))


def strict_assumed(codes: Sequence[str]) -> str:
    """"No allergen rule was given for cereals containing gluten (AW): read as strict, the safe reading. …"."""
    return STRICT_ASSUMED.format(allergens=", ".join(describe(code) for code in codes))


def _typed(proposal: RequestProposal, text: str) -> PurchaseRequest | tuple[Fault, ...]:
    """The contract model, which refuses what the schema does not: long or quoted terms, quantities out of range."""
    lines = [
        {
            "text": text,  # the buyer's own words, set here and never by the model
            **line.model_dump(exclude={"exclude_allergens", "pack", "keep_formula"}),
            **({"keep_formula": True} if line.keep_formula else {}),  # it can only add the check
            "exclude_allergens": tuple(dict.fromkeys(normalise_code(code) for code in line.exclude_allergens)),
            **({} if line.pack is None else {"pack": line.pack}),  # left out, the contract's default applies
        }
        for line in proposal.lines
    ]
    try:
        return PurchaseRequest.model_validate({
            "needed_by": proposal.needed_by, "require_confirmed": proposal.require_confirmed, "lines": lines,
            **({} if proposal.prefer is None else {"prefer": proposal.prefer}),  # left out, PRICE applies
        })
    except ValidationError as error:
        return validation_faults(error)


class ModelRequestParser:
    """Implements the `RequestParser` port over any `AgentModel`: the Gemini model or the recorded one."""

    def __init__(
        self,
        *,
        model: AgentModel,
        clock: Clock,
        product_type_keys: Sequence[str],
        profile_strictness: Callable[[str], AllergenStrictness | None],
        brands: Brands = NO_BRANDS,
    ) -> None:
        self._model = model
        self._clock = clock
        self._keys = checked_keys(product_type_keys)
        self._schema = proposal_schema(self._keys)
        self._profile_strictness = profile_strictness
        self._brands = brands  # the brands the reading's sentence names as required (`tta.agent.notes`)

    @property
    def model_id(self) -> str:
        return self._model.model_id

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        """The typed request of `read`."""
        return self.read(text, identity).request

    def read(self, text: str, identity: Identity) -> Reading:
        """The typed request and who read it. Raises `InvalidRequest` naming what the text does not say, or what
        in the model's answer did not validate after one more try; `SupplierUnavailable` when the model cannot
        be reached."""
        words = text.strip()
        if not words:
            raise InvalidRequest(EMPTY_TEXT)
        if len(words) > MAX_TEXT_LENGTH:
            raise InvalidRequest(TEXT_TOO_LONG.format(limit=MAX_TEXT_LENGTH))
        today = helsinki_date(self._clock.now())  # "by Monday" is resolved against the data clock's day
        read = self._ask(words, today, identity)
        answer = self._model.answer_source(words)
        sentence = reading_sentence(answer)
        if read.read_as_strict:
            sentence = f"{sentence} {strict_assumed(read.read_as_strict)}"
        return Reading(
            request=read.request, source=answer.source, model=answer.model, recorded_at=answer.recorded_at,
            sentence=with_notes(
                sentence, read.request, words, self._brands, by_rules=answer.source is ReadingSource.RULE_BASED
            ),
        )

    def read_image(self, image: bytes, media_type: str, identity: Identity) -> tuple[list[str], Reading]:
        """The lines read in a photo of an order list, and the reading of those lines (`tta.agent.photo`).
        `media_type` is what the sender declared; it is not trusted: the image's first bytes decide."""
        return read_photo(model=self._model, image=image, identity=identity, read=self.read)

    def _ask(self, words: str, today: date, identity: Identity) -> _Read:
        call = ExtractCall(
            system=parser_instruction(today, self._keys), text=words, schema=self._schema,
            profile_id=identity.profile_id, today=today,
        )
        facts = TextFacts.of(words, today)
        faults: tuple[Fault, ...] = ()
        for answer_number in range(1, MAX_ANSWERS + 1):
            read = self._read(self._model.extract(call), words, facts, today, identity)
            if isinstance(read, _Read):
                return read
            faults = read
            logger.info("Answer %d of the model did not validate: %s", answer_number, "; ".join(map(str, faults)))
        raise InvalidRequest(
            NOT_READ.format(answers=MAX_ANSWERS, faults="; ".join(map(str, faults))),
            faults=[fault.path for fault in faults],
        )

    def _read(
        self, answer: str, text: str, facts: TextFacts, today: date, identity: Identity
    ) -> _Read | tuple[Fault, ...]:
        """The typed request, or the faults of this answer. Raises `InvalidRequest` for what the text lacks."""
        proposal = _proposal(answer)
        if not isinstance(proposal, RequestProposal):
            return proposal
        faults = _faults(proposal, facts, today, self._keys, text)
        if faults:
            return faults
        self._refuse_what_is_missing(proposal, facts)
        profile_id = identity.profile_id
        strictness = self._profile_strictness(profile_id) if profile_id is not None else None
        proposal, read_as_strict = _safely_strict(proposal, strictness)
        typed = _typed(proposal, text)
        return _Read(typed, read_as_strict) if isinstance(typed, PurchaseRequest) else typed

    def _refuse_what_is_missing(self, proposal: RequestProposal, facts: TextFacts) -> None:
        if not proposal.lines:
            raise InvalidRequest(NOTHING_TO_ORDER, missing=["lines"])
        missing = [item for index, line in enumerate(proposal.lines) for item in _line_missing(index, line, facts)]
        if missing:
            raise InvalidRequest(
                " ".join(item.sentence for item in missing), missing=[item.path for item in missing]
            )
