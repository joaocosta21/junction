"""Free text becomes the typed request (SPEC sections 3 and 11; task T10).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". The model's answer
is a proposal held to a JSON Schema; this module validates it and turns it into the contract model.
What the text does not say (a quantity, a unit, how strict an allergen exclusion is) is reported as
`invalid-request` and never filled in. An answer that does not validate is asked for once more, then refused.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from tta.agent.model import AgentModel, ExtractCall
from tta.agent.prompts import parser_instruction
from tta.agent.schema import CLAIM_CODES, EXCLUDABLE_ALLERGEN_CODES, checked_keys, proposal_schema
from tta.allergens import describe, normalise_code
from tta.contracts.common import AllergenStrictness, Identity, PackPreference, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Clock
from tta.contracts.request import MAX_TEXT_LENGTH, PurchaseRequest

MAX_ANSWERS = 2  # the first answer, and one more when it does not validate

EMPTY_TEXT = "The text is empty: say what is needed and how much."
TEXT_TOO_LONG = "The text is longer than {limit:,} characters, the most that is read."
NOTHING_TO_ORDER = (
    "The text names nothing to order. Say what is needed and how much, for example "
    "200 litres of oat drink by Monday."
)
NO_PRODUCT = "Line {line} does not say which product is needed."
NO_QUANTITY = "Line {line} does not say how much is needed: the quantity is missing. A quantity is never guessed."
NO_UNIT = "Line {line} gives a quantity with no unit. Say litres, kilograms or sales units."
NO_STRICTNESS = (
    "Line {line} excludes {allergens} and does not say how strictly, and {profile} sets no allergen "
    "strictness. Say STRICT (a product with no allergen statement goes to a human) or DECLARED_ONLY (it "
    "passes, shown as unverified). The strictness is never guessed."
)
NOT_READ = (
    "The request could not be read into a typed request: after {answers} answers of the model, {faults}. "
    "Send the typed request to POST /v1/offers instead."
)
NOT_JSON = "not a JSON object"
UNKNOWN_FIELD = "a field the typed request does not have"
NOT_IN_ANSWER = "missing from the answer"
NOT_VALID = "not a valid value ({code})"
NOT_A_KEY = "not a key of the product-type table"
NOT_A_CLAIM = "not a nutritional claim code of the catalog"
NOT_AN_ALLERGEN = "not an allergen code a buyer can exclude"
NOT_IN_TEXT = "a product number that is not in the text"
BEFORE_TODAY = "before today ({today})"

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


class RequestProposal(_Proposal):
    needed_by: date | None
    require_confirmed: bool
    lines: tuple[LineProposal, ...]


@dataclass(frozen=True)
class Fault:
    """Something wrong with the model's answer. It names a field and a fixed reason, never the model's words."""

    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


@dataclass(frozen=True)
class Missing:
    """Something the buyer's text does not say and the typed request needs."""

    path: str
    sentence: str


def _path(location: Sequence[Any]) -> str:
    """`("lines", 0, "quantity")` as `lines[0].quantity`."""
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
    return path or "answer"


def _validation_faults(error: ValidationError) -> tuple[Fault, ...]:
    """One fault per error, named by where it sits and by pydantic's error code: never by the input."""
    faults = []
    for item in error.errors(include_input=False, include_url=False):
        location, code = item["loc"], item["type"]
        if code == "extra_forbidden":
            faults.append(Fault(_path(location[:-1]), UNKNOWN_FIELD))  # a made-up key is not repeated
        elif code == "missing":
            faults.append(Fault(_path(location), NOT_IN_ANSWER))
        else:
            faults.append(Fault(_path(location), NOT_VALID.format(code=code)))
    return tuple(faults)


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
        return _validation_faults(error)


def _line_faults(index: int, line: LineProposal, text: str, keys: Sequence[str]) -> list[Fault]:
    at = f"lines[{index}]"
    faults = []
    if line.product_type is not None and line.product_type not in keys:
        faults.append(Fault(f"{at}.product_type", NOT_A_KEY))
    if any(claim not in CLAIM_CODES for claim in line.required_claims):
        faults.append(Fault(f"{at}.required_claims", NOT_A_CLAIM))
    if any(normalise_code(code) not in EXCLUDABLE_ALLERGEN_CODES for code in line.exclude_allergens):
        faults.append(Fault(f"{at}.exclude_allergens", NOT_AN_ALLERGEN))
    if any(product_id not in text for product_id in line.product_ids):
        faults.append(Fault(f"{at}.product_ids", NOT_IN_TEXT))
    return faults


def _faults(proposal: RequestProposal, text: str, today: date, keys: Sequence[str]) -> tuple[Fault, ...]:
    """What the schema cannot hold the model to: our tables, the buyer's text and the clock."""
    faults = [fault for index, line in enumerate(proposal.lines) for fault in _line_faults(index, line, text, keys)]
    if proposal.needed_by is not None and proposal.needed_by < today:
        faults.append(Fault("needed_by", BEFORE_TODAY.format(today=today.isoformat())))
    return tuple(faults)


def _line_missing(
    index: int, line: LineProposal, profile_name: str, profile_strictness: AllergenStrictness | None
) -> list[Missing]:
    at, number = f"lines[{index}]", index + 1
    missing = []
    if line.product_type is None and not line.product_ids and not line.name_terms:
        missing.append(Missing(f"{at}.product_type", NO_PRODUCT.format(line=number)))
    if line.quantity is None:
        missing.append(Missing(f"{at}.quantity", NO_QUANTITY.format(line=number)))
    elif line.unit is None:
        missing.append(Missing(f"{at}.unit", NO_UNIT.format(line=number)))
    if line.exclude_allergens and line.allergen_strictness is None and profile_strictness is None:
        allergens = ", ".join(describe(normalise_code(code)) for code in line.exclude_allergens)
        sentence = NO_STRICTNESS.format(line=number, allergens=allergens, profile=profile_name)
        missing.append(Missing(f"{at}.allergen_strictness", sentence))
    return missing


def _typed(proposal: RequestProposal, text: str) -> PurchaseRequest | tuple[Fault, ...]:
    """The contract model, which refuses what the schema does not: long or quoted terms, quantities out of range."""
    lines = [
        {
            "text": text,  # the buyer's own words, set here and never by the model
            **line.model_dump(exclude={"exclude_allergens", "pack"}),
            "exclude_allergens": tuple(dict.fromkeys(normalise_code(code) for code in line.exclude_allergens)),
            **({} if line.pack is None else {"pack": line.pack}),  # left out, the contract's default applies
        }
        for line in proposal.lines
    ]
    try:
        return PurchaseRequest.model_validate(
            {"needed_by": proposal.needed_by, "require_confirmed": proposal.require_confirmed, "lines": lines}
        )
    except ValidationError as error:
        return _validation_faults(error)


class ModelRequestParser:
    """Implements the `RequestParser` port over any `AgentModel`: the Gemini model or the recorded one."""

    def __init__(
        self,
        *,
        model: AgentModel,
        clock: Clock,
        product_type_keys: Sequence[str],
        profile_strictness: Callable[[str], AllergenStrictness | None],
    ) -> None:
        self._model = model
        self._clock = clock
        self._keys = checked_keys(product_type_keys)
        self._schema = proposal_schema(self._keys)
        self._profile_strictness = profile_strictness

    @property
    def model_id(self) -> str:
        return self._model.model_id

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        """Raises `InvalidRequest` naming what the text does not say, or what in the model's answer did not
        validate after one more try; `SupplierUnavailable` when the model cannot be reached."""
        words = text.strip()
        if not words:
            raise InvalidRequest(EMPTY_TEXT)
        if len(words) > MAX_TEXT_LENGTH:
            raise InvalidRequest(TEXT_TOO_LONG.format(limit=MAX_TEXT_LENGTH))
        today = self._clock.now().date()  # "by Monday" is resolved against the data clock
        call = ExtractCall(system=parser_instruction(today, self._keys), text=words, schema=self._schema)
        faults: tuple[Fault, ...] = ()
        for answer_number in range(1, MAX_ANSWERS + 1):
            read = self._read(self._model.extract(call), words, today, identity)
            if isinstance(read, PurchaseRequest):
                return read
            faults = read
            logger.info("Answer %d of the model did not validate: %s", answer_number, "; ".join(map(str, faults)))
        raise InvalidRequest(
            NOT_READ.format(answers=MAX_ANSWERS, faults="; ".join(map(str, faults))),
            faults=[fault.path for fault in faults],
        )

    def _read(self, answer: str, text: str, today: date, identity: Identity) -> PurchaseRequest | tuple[Fault, ...]:
        """The typed request, or the faults of this answer. Raises `InvalidRequest` for what the text lacks."""
        proposal = _proposal(answer)
        if not isinstance(proposal, RequestProposal):
            return proposal
        faults = _faults(proposal, text, today, self._keys)
        if faults:
            return faults
        self._refuse_what_is_missing(proposal, identity)
        return _typed(proposal, text)

    def _refuse_what_is_missing(self, proposal: RequestProposal, identity: Identity) -> None:
        if not proposal.lines:
            raise InvalidRequest(NOTHING_TO_ORDER, missing=["lines"])
        profile_id = identity.profile_id
        strictness = self._profile_strictness(profile_id) if profile_id is not None else None
        profile_name = f"profile {profile_id}" if profile_id is not None else "the caller"
        missing = [
            item
            for index, line in enumerate(proposal.lines)
            for item in _line_missing(index, line, profile_name, strictness)
        ]
        if missing:
            raise InvalidRequest(
                " ".join(item.sentence for item in missing), missing=[item.path for item in missing]
            )
