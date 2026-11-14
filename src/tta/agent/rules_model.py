"""The rule-based reader behind the `AgentModel` interface, and the fixed run it makes (task FALLBACK-1).

Scores on the 30% "working end-to-end demo" and the 20% "decisions logged and auditable": the parser and the loop
run on it unchanged, so its reading passes the same text check and conversion as a model's, and every reading and
trace names it `rule-based`, never a model.
- `extract` answers with the proposal of `tta.agent.rules_reader`, a quantity as the text of its digits (the
  parser reads it as a `Decimal`; it never passes through a float). A text the rules cannot read raises
  `NotReadByRules`.
- `next_turn` is the fixed sequence of the hand-built recordings (`fixtures/agent/run-brief.json`): turn 1
  `get_authority`, turn 2 `create_offer`, turn 3 `place_order` on the option ranked 1 of that offer, read from its
  result. When the offer has no option, or it was refused, nothing is ordered and the run ends.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

from tta.agent.brands import NO_BRANDS, Brands, catalog_brands
from tta.agent.model import AnswerSource, ExtractCall, FunctionCall, ModelTurn, TurnCall
from tta.agent.rules_reader import MAY_FOLLOW, RuleReader, type_names
from tta.agent.tools import CREATE_OFFER, GET_AUTHORITY, OPTION_ID, PLACE_ORDER
from tta.catalog import load_product_types
from tta.contracts.agent import ReadingSource
from tta.contracts.common import JsonDict
from tta.contracts.product import Product

RULE_BASED_MODEL_ID = "rule-based"
AUTHORITY_TURN, OFFER_TURN, ORDER_TURN = 1, 2, 3
FUNCTION_RESULT = "function_result"  # a history step that holds the gateway's answer (`tta.agent.runner`)
NO_DAY_GIVEN = "The rule-based reader needs the date the request is read on."


def _turn(number: int, name: str, arguments: JsonDict) -> ModelTurn:
    call = FunctionCall(id=f"rules-{number}-1", name=name, arguments=arguments)
    step = {"type": "function_call", "id": call.id, "name": name, "arguments": arguments}
    return ModelTurn(steps=(step,), calls=(call,))


def _result(step: JsonDict) -> JsonDict:
    """The gateway's answer in a history step, read back from the JSON text the runner wrote."""
    texts = [item.get("text") for item in step.get("result") or () if isinstance(item, dict)]
    try:
        value = json.loads("".join(text for text in texts if isinstance(text, str)))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def top_option(history: Sequence[JsonDict]) -> str | None:
    """The option_id of the option ranked 1 of the offer `create_offer` returned, or `None` when it returned
    none or was refused."""
    for step in reversed(history):
        if step.get("type") != FUNCTION_RESULT or step.get("name") != CREATE_OFFER:
            continue
        if step.get("is_error"):
            return None
        options = _result(step).get("options")
        ranked = [option for option in options if isinstance(option, dict)] if isinstance(options, list) else []
        first = min(ranked, key=lambda option: option.get("rank", 0), default=None)
        option_id = first.get(OPTION_ID) if first is not None else None
        return option_id if isinstance(option_id, str) else None
    return None


def brands_for(products: Iterable[Product], product_type_keys: Sequence[str]) -> Brands:
    """The brands of these products a buyer may name, less every word the rules already read."""
    return catalog_brands(products, type_names(load_product_types(), product_type_keys), MAY_FOLLOW)


class RuleModel:
    """Implements `AgentModel` with fixed rules. It calls nothing and holds no state."""

    def __init__(self, reader: RuleReader) -> None:
        self._reader = reader

    @classmethod
    def for_keys(cls, product_type_keys: Sequence[str], brands: Brands = NO_BRANDS) -> RuleModel:
        """The rules over the product-type table of the catalog package, for these keys, and the brands a line
        may name (`brands_for`); with none, a brand word is read as any other word."""
        return cls(RuleReader(type_names(load_product_types(), product_type_keys), brands))

    @property
    def model_id(self) -> str:
        return RULE_BASED_MODEL_ID

    @property
    def recorded(self) -> bool:
        """False: nothing is served from a recording. The trace names the rules, not a model."""
        return False

    def label_for(self, request_text: str) -> str:
        return RULE_BASED_MODEL_ID

    def answer_source(self, request_text: str) -> AnswerSource:
        return AnswerSource(ReadingSource.RULE_BASED, RULE_BASED_MODEL_ID)

    def extract(self, call: ExtractCall) -> str:
        """The proposal as JSON text. Raises `NotReadByRules` for a text the rules cannot read."""
        if call.today is None:
            raise ValueError(NO_DAY_GIVEN)
        return json.dumps(self._reader.proposal(call.text, call.today), ensure_ascii=False)

    def next_turn(self, call: TurnCall) -> ModelTurn:
        if call.turn == AUTHORITY_TURN:
            return _turn(call.turn, GET_AUTHORITY, {})
        if call.turn == OFFER_TURN:
            return _turn(call.turn, CREATE_OFFER, {})
        option_id = top_option(call.history) if call.turn == ORDER_TURN else None
        return ModelTurn() if option_id is None else _turn(call.turn, PLACE_ORDER, {OPTION_ID: option_id})
