"""What the model is shown of each answer of the gateway, and what the trace keeps (SPEC section 11).

One summary serves both, so the trace holds exactly what the model saw. A summary is made of the gateway's
own values and sentences. Product names are in it as data: they come from the product file and are never
part of an instruction. Money and quantities leave as JSON numbers, as everywhere in the interface.
"""

from __future__ import annotations

from collections import Counter

from tta.contracts.common import JsonDict
from tta.contracts.errors import TtaError
from tta.contracts.offer import Offer, OfferLine, OfferOption
from tta.contracts.order import Order
from tta.contracts.policy import Authority

AUTHORITY_SENTENCES = 2  # the first two of the gateway's summary: who may order alone, and the limits
_PROFILE_FIELDS = {
    "profile_id", "display_name", "auto_order_enabled", "max_order_net_eur", "max_daily_net_eur", "min_fill_ratio",
    "excluded_allergens", "allergen_strictness", "substitution_without_approval", "require_confirmed",
}
_OPTION_FIELDS = {"option_id", "kind", "rank", "title", "summary", "fill_ratio", "valid_until"}
_LINE_FIELDS = {"product_id", "name", "quantity", "sales_unit", "unit_net_price", "net"}
_ORDER_FIELDS = {"order_id", "offer_id", "option_id", "status", "placed_by", "approval_id", "status_sentence"}


def authority_summary(authority: Authority) -> JsonDict:
    return {
        **authority.profile.model_dump(mode="json", include=_PROFILE_FIELDS),
        "summary": list(authority.summary),
        "note": authority.note,
    }


def authority_sentence(authority: Authority) -> str | None:
    return " ".join(authority.summary[:AUTHORITY_SENTENCES]) or None


def _line_summary(line: OfferLine) -> JsonDict:
    return {
        **line.model_dump(mode="json", include=_LINE_FIELDS),
        "availability": line.availability.state.value,
        "availability_sentence": line.availability.sentence,
    }


def _option_summary(option: OfferOption) -> JsonDict:
    decision = option.decision
    return {
        **option.model_dump(mode="json", include=_OPTION_FIELDS),
        **option.totals.model_dump(mode="json", include={"net", "gross", "currency", "is_ceiling"}),
        "verdict": decision.verdict.value if decision else None,
        "decision": decision.sentence if decision else None,
        "required_roles": [role.value for role in decision.required_roles] if decision else [],
        "lines": [_line_summary(line) for line in option.lines],
    }


def offer_summary(offer: Offer) -> JsonDict:
    """The options whole enough to choose from; the excluded products as counts by reason."""
    by_reason = Counter(exclusion.reason.value for exclusion in offer.excluded)
    return {
        "offer_id": offer.offer_id,
        "source": offer.source.value,
        "time_now": offer.time_now.isoformat(),
        "options": [_option_summary(option) for option in offer.options],
        "excluded": {"count": len(offer.excluded), "by_reason": dict(by_reason)},
        "notes": list(offer.notes),
    }


def offer_sentence(offer: Offer) -> str | None:
    """The first option's sentence and its verdict; with no option, the gateway's notes saying why."""
    if not offer.options:
        return " ".join(offer.notes) or None
    top = offer.options[0]
    return f"{top.summary} {top.decision.sentence}" if top.decision else top.summary


def order_summary(order: Order) -> JsonDict:
    return {
        **order.model_dump(mode="json", include=_ORDER_FIELDS),
        "verdict": order.decision.verdict.value,
        "required_roles": [role.value for role in order.decision.required_roles],
        **order.option.totals.model_dump(mode="json", include={"net", "currency"}),
    }


def refusal(slug: str, detail: str) -> JsonDict:
    return {"error": slug, "detail": detail}


def gateway_refusal(error: TtaError) -> JsonDict:
    """A typed error of the gateway, by its problem type and its own sentence."""
    return refusal(error.slug, error.detail)
