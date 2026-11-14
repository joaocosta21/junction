"""The facts of an event, for each reader. Compact on purpose: an event names the offer, order and approval by
id and keeps the figures a decision rested on, not a copy of every object (CloudEvents asks for small events).

Values keep the form the API gives them (SPEC section 2). The supplier's facts are built from an allow-list:
a field reaches Valio Aimo only when it is named here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic_core import to_jsonable_python

from tta.audit.phrases import code_shaped
from tta.audit.scope import Scope
from tta.audit.supplier_decisions import decision_facts, left_out_counts, left_out_facts
from tta.contracts.audit import AuditContext
from tta.contracts.common import ClaimName, Contract, JsonDict
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
OFFER_KEYS = ("offer_id", "agent_id", "created_at", "source", "time_now", "time_basis", "candidates_considered")
ORDER_KEYS = (
    "order_id", "offer_id", "option_id", "agent_id", "status", "placed_by", "created_at", "updated_at", "source",
    "record_note", "reliance",
)
BUYER_ORDER_KEYS = (*ORDER_KEYS, "approval_id", "status_sentence")
SUPPLIER_REQUEST_KEYS = ("needed_by", "require_confirmed")
# Product ids and product types, and the claims and labels asked for where they are codes of Valio Aimo's own
# lists (`_supplier_request`). A name term is the buyer's own wording ("without peanuts") and is never listed.
SUPPLIER_REQUEST_LINE_KEYS = ("product_type", "product_ids", "quantity", "unit", "pack")
SUPPLIER_REQUEST_CODE_KEYS = ("required_claims", "required_labels")
# The roles are shown; the approver's id, name and note are not (`tta.audit.readers`).
SUPPLIER_APPROVAL_KEYS = ("approval_id", "status", "required_roles", "created_at", "valid_until")
SUPPLIER_APPROVAL_DECISION_KEYS = ("decision", "roles", "option_id", "decided_at")
# Not the product: evidence is attached for a product P-04 fired on, which Valio Aimo is not shown.
SUPPLIER_EVIDENCE_KEYS = ("found",)
# Facts a caller may add that describe a lookup in Valio Aimo's own data. Every other caller fact is buyer-only.
SUPPLIER_CALLER_KEYS = ("products_looked_up", "product_ids", "source", "time_now", "time_basis")
# A caller fact that is a whole view written for Valio Aimo: its keys become the supplier's facts as given, and it
# is left out of the buyer's, who has the full facts beside it. Only the suggestion events write one
# (`tta.suggestions.events`, which builds that view from an allow-list of its own).
SUPPLIER_VIEW = "supplier_view"


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
    reasons = Counter(exclusion.reason.value for exclusion in offer.excluded)
    return _present({
        **_pick(_dump(offer), OFFER_KEYS),
        "options": [_option(option, for_buyer) for option in offer.options],
        # The buyer reads every count. Valio Aimo reads the counts of the reasons about its own data and no
        # other: a count of products left out for an allergen, with the catalog, names the allergen.
        "excluded_by_reason": dict(sorted(reasons.items())) if for_buyer else left_out_counts(offer),
        "left_out": None if for_buyer else left_out_facts(offer),
        "notes": list(offer.notes) if for_buyer else None,
    })


def _order(order: Order | None, for_buyer: bool) -> JsonDict | None:
    if order is None:
        return None
    picked = _pick(_dump(order), BUYER_ORDER_KEYS if for_buyer else ORDER_KEYS)
    return {**picked, "option": _option(order.option, for_buyer)}


def _supplier_request(request: PurchaseRequest | None) -> JsonDict | None:
    """What was asked of Valio Aimo's data: no buyer's words or name terms, and no allergen exclusion."""
    if request is None:
        return None
    dumped = request.model_dump(mode="json")
    lines = [
        {**_pick(line, SUPPLIER_REQUEST_LINE_KEYS),
         **{key: list(code_shaped(line[key])) for key in SUPPLIER_REQUEST_CODE_KEYS}}
        for line in dumped["lines"]
    ]
    return {**_pick(dumped, SUPPLIER_REQUEST_KEYS), "lines": lines}


def buyer_facts(context: AuditContext, scope: Scope) -> JsonDict:
    """Everything the buyer may see. A fact added by the caller never replaces an object recorded here; the view a
    caller wrote for Valio Aimo is not repeated."""
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
    from_caller = {key: value for key, value in context.facts.items() if key != SUPPLIER_VIEW}
    return to_jsonable_python({**from_caller, **recorded})


def supplier_facts(context: AuditContext, scope: Scope) -> JsonDict:
    """The subset Valio Aimo may see: its own data, what was offered and ordered, and how the order was decided."""
    verdict = decision_facts(scope.decision) if scope.decision is not None else None
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
    view = context.facts.get(SUPPLIER_VIEW)
    written = view if isinstance(view, dict) else {}
    return to_jsonable_python({**written, **from_caller, **recorded})
