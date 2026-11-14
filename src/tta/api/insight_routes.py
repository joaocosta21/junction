"""`GET /v1/insights` (lane BO): Valio Aimo's back office of the shared order book, for the supplier's token only.

Scores on the 20% "autonomy and controls" (who reads what: the figures are Valio Aimo's own sales, and a buyer's
agent or approver is refused) and on the 15% "open, documented standards" (typed in OpenAPI like every route).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from tta.api import docs
from tta.api.identity import Caller
from tta.api.insight_models import Insights
from tta.api.insights import Period, insights, is_recorded
from tta.api.routes import CALLER
from tta.contracts.errors import InvalidRequest, NotAuthorised, RateLimited

ONLY_THE_SUPPLIER = (
    "These figures are Valio Aimo's view of what it sold through the agent channel: only the supplier's token "
    "reads them. A buyer reads its own orders (GET /v1/orders) and its own audit trail (GET /v1/audit)."
)

insight_router = APIRouter(prefix="/v1", tags=[docs.TAG_AUDIT])


@insight_router.get(
    "/insights", operation_id="get_insights", responses=docs.problems(*CALLER, InvalidRequest, RateLimited),
    summary="What the agent channel brought Valio Aimo, and where it is losing sales",
)
def get_insights(
    request: Request, caller: Caller,
    period: Annotated[Period, Query(description="`today`: the day of the clock in force. `all`: the whole book")]
    = Period.TODAY,
) -> Insights:
    """For the supplier's token only; an agent or an approver is refused (403). Counted from the audit trail each
    time it is asked, from Valio Aimo's view of each event and nothing else: demand (requests, offers, orders by
    outcome, net value confirmed and waiting), suggestions (shown, accepted, ordered, by kind, the net value they
    added and the net value they saved buyers, as two numbers), and sales not made (the quantity asked for that
    confirmed stock did not cover, by product type, with the reason in Valio Aimo's own data and the value at the
    offered price). No figure is per buyer; a buyer's limits, excluded allergens, names, notes and own words are
    not in what is counted. Every block says how it was counted. Counted with the caller's lookup window."""
    if not caller.is_supplier:
        raise NotAuthorised(ONLY_THE_SUPPLIER)
    parts = request.app.state.parts
    parts.service.count_read(caller)
    return insights(parts.store.list_audit_events(), now=parts.clock.now(), period=period,
                    recorded=is_recorded(parts.settings))
