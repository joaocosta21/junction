"""The facts of an event, for each reader. Compact on purpose: an event names the offer, order and approval by
id and keeps the figures a decision rested on, not a copy of every object (CloudEvents asks for small events).

Values keep the form the API gives them (SPEC section 2). The supplier's facts are built from an allow-list:
a field reaches Valio Aimo only when it is named here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic_core import to_jsonable_python

from tta.audit.readers import supplier_rule_ids
from tta.audit.scope import Scope
from tta.contracts.audit import AuditContext
from tta.contracts.common import ClaimName, Contract, ExclusionReason, JsonDict
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import Order
from tta.contracts.request import PurchaseRequest

OPTION_KEYS = ("option_id", "kind", "rank", "fill_ratio", "valid_until", "totals", "coverage")
BUYER_OPTION_KEYS = (*OPTION_KEYS, "title", "summary", "constraint_checks")
LINE_KEYS = (
    "product_id", "name", "quantity", "sales_unit", "covers", "unit_net_price", "tax_rate", "net", "tax", "gross",
    "price_valid_to", "variable_weight", "has_deposits", "country_of_origin",
)
AVAILABILITY_KEYS = ("state", "usable_amount", "available_date", "closing_time", "logistic_model")
OFFER_KEYS = ("offer_id", "agent_id", "created_at", "source", "time_now", "candidates_considered")
ORDER_KEYS = (
    "order_id", "offer_id", "option_id", "agent_id", "status", "placed_by", "created_at", "updated_at", "source",
    "record_note", "reliance",
)
BUYER_ORDER_KEYS = (*ORDER_KEYS, "approval_id", "status_sentence")
SUPPLIER_REQUEST_KEYS = ("needed_by", "require_confirmed")
# Product ids and product types only. A name term or a required claim is the buyer's own wording and can
# reveal an exclusion ("without peanuts"), so neither is listed.
SUPPLIER_REQUEST_LINE_KEYS = ("product_type", "product_ids", "quantity", "unit", "pack")
SUPPLIER_APPROVAL_KEYS = ("approval_id", "status", "created_at", "valid_until")
SUPPLIER_APPROVAL_DECISION_KEYS = ("decision", "option_id", "decided_at")
SUPPLIER_EVIDENCE_KEYS = ("product_id", "found")
# Reasons that exist only because of the buyer's allergen exclusions: never counted for the supplier.
BUYER_ONLY_EXCLUSION_REASONS = (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED)
# Facts a caller may add that describe a lookup in Valio Aimo's own data. Every other caller fact is buyer-only.
SUPPLIER_CALLER_KEYS = ("products_looked_up", "product_ids", "source", "time_now")


def _dump(model: Contract | None) -> JsonDict | None:
    return None if model is None else model.model_dump(mode="json")


def _pick(values: JsonDict | None, keys: Sequence[str]) -> JsonDict | None:
    return None if values is None else {key: values[key] for key in keys if key in values}


def _present(facts: JsonDict) -> JsonDict:
    return {key: value for key, value in facts.items() if value is not None}


def _line(line: JsonDict, for_buyer: bool) -> JsonDict:
    claims = {
        claim["claim"]: claim["status"]
        for claim in line["claims"]
        if for_buyer or claim["claim"] != ClaimName.ALLERGENS.value
    }
    substitute = line.get("substitute")
    allergen_check = line.get("allergen_check") if for_buyer else None
    return _present({
        **_pick(line, LINE_KEYS),
        "availability": _pick(line["availability"], AVAILABILITY_KEYS),
        "claims": claims,
        "substitute_for": substitute["original_id"] if substitute else None,
        "allergen_outcome": allergen_check["outcome"] if allergen_check else None,
    })


def _option(option: OfferOption | None, for_buyer: bool) -> JsonDict | None:
    if option is None:
        return None
    dumped = option.model_dump(mode="json")
    picked = _pick(dumped, BUYER_OPTION_KEYS if for_buyer else OPTION_KEYS)
    return {**picked, "lines": [_line(line, for_buyer) for line in dumped["lines"]]}


def _offer(offer: Offer | None, for_buyer: bool) -> JsonDict | None:
    if offer is None:
        return None
    reasons = Counter(
        exclusion.reason.value
        for exclusion in offer.excluded
        if for_buyer or exclusion.reason not in BUYER_ONLY_EXCLUSION_REASONS
    )
    return _present({
        **_pick(_dump(offer), OFFER_KEYS),
        "options": [_option(option, for_buyer) for option in offer.options],
        "excluded_by_reason": dict(sorted(reasons.items())),
        "notes": list(offer.notes) if for_buyer else None,
    })


def _order(order: Order | None, for_buyer: bool) -> JsonDict | None:
    if order is None:
        return None
    picked = _pick(_dump(order), BUYER_ORDER_KEYS if for_buyer else ORDER_KEYS)
    return {**picked, "option": _option(order.option, for_buyer)}


def _supplier_request(request: PurchaseRequest | None) -> JsonDict | None:
    """What was asked of Valio Aimo's data: no buyer's words, name terms or claims, and no allergen exclusion."""
    if request is None:
        return None
    dumped = request.model_dump(mode="json")
    lines = [_pick(line, SUPPLIER_REQUEST_LINE_KEYS) for line in dumped["lines"]]
    return {**_pick(dumped, SUPPLIER_REQUEST_KEYS), "lines": lines}


def buyer_facts(context: AuditContext, scope: Scope) -> JsonDict:
    """Everything the buyer may see. A fact added by the caller never replaces an object recorded here."""
    recorded = _present({
        "request": _dump(context.request),
        "profile": _dump(context.profile),
        "offer": _offer(context.offer, for_buyer=True),
        "option": _option(context.option, for_buyer=True),
        "decision": _dump(scope.decision),
        "order": _order(context.order, for_buyer=True),
        "approval": _dump(context.approval),
        "approval_decision": _dump(context.approval_decision),
        "revalidation": _dump(context.revalidation),
        "evidence": _dump(context.evidence),
    })
    return to_jsonable_python({**context.facts, **recorded})


def supplier_facts(context: AuditContext, scope: Scope) -> JsonDict:
    """The subset Valio Aimo may see: its own data, what was offered and ordered, and how the order was decided."""
    decision = scope.decision
    verdict = None
    if decision is not None:
        verdict = {
            "verdict": decision.verdict.value,
            "rule_ids": list(supplier_rule_ids(decision.rule_ids)),
            "evaluated_at": decision.evaluated_at,
        }
    recorded = _present({
        "request": _supplier_request(context.request),
        "offer": _offer(context.offer, for_buyer=False),
        "option": _option(context.option, for_buyer=False),
        "decision": verdict,
        "order": _order(context.order, for_buyer=False),
        "approval": _pick(_dump(context.approval), SUPPLIER_APPROVAL_KEYS),
        "approval_decision": _pick(_dump(context.approval_decision), SUPPLIER_APPROVAL_DECISION_KEYS),
        "revalidation": _dump(context.revalidation),
        "evidence": _pick(_dump(context.evidence), SUPPLIER_EVIDENCE_KEYS),
    })
    from_caller = {key: context.facts[key] for key in SUPPLIER_CALLER_KEYS if key in context.facts}
    return to_jsonable_python({**from_caller, **recorded})
