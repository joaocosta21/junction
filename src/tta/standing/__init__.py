"""Standing orders: a kitchen's recurring order, renewed through the normal offer and order flow, with its drift
from the history checked by rule P-08 before the agent may renew it alone (task STAND-1).

    standing = StandingOrders(store=store, audit=audit, gateway=service, clock=clock)
    standing.create(agent, NewStandingOrder(name=..., request=...))
    standing.renew(agent, standing_order_id, RenewStandingOrder(quantities=(Decimal(290),)))
        -> the stored request with `standing_order_id` set -> create_offer -> place_order on the top option
        -> APPROVAL: waits for a human · the renewal joins the history once an order exists

`history.standing_history` is what the offer builder and the order book pass into the policy context.
"""

from tta.standing.history import history_lookup, standing_history
from tta.standing.service import StandingOrders

__all__ = ["StandingOrders", "history_lookup", "standing_history"]
