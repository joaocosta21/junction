# STAND-1 — questions

## For Valio: is a customer's order history readable?
**Context:** Your example scenario asks for "standing order drift detection: the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it." Learning the usual order needs that kitchen's past orders.
**We did:** Looked for order history in the mock: it has the price and availability endpoints only, and no order endpoint (by design, as agreed).
**We got:** No history at all, so the gateway keeps its own: each renewal it places joins the history, and the demonstration starts with six made-up weeks, marked `synthetic` wherever they appear.
**Example to show:** Standing order `so_demo_hotel_milk`, 100 L of 469363 a week: six synthetic weeks (96 to 104 L, median 100 L, €2.48 from tonight's capture), then a renewal at 290 L that rule P-08 sends to the purchasing manager.
**Ask:** "In production, would a customer's own past orders (per product: date, quantity, net price) be readable through an API, so the history is yours rather than ours? Is building it from the gateway's own orders until then expected, or did we miss a source?"
**If no answer, we build:** the history from the gateway's own renewals only, synthetic rows labelled as such.

## For the team: tolerance values
**Context:** P-08 compares each line's quantity and unit price with the median of its last 6 renewals; fewer than 3 past renewals is too short to judge.
**We did:** Set the tolerance to 25% for hotel-kitchen and 10% for allergy-ward (ours, illustrative, like every profile value); one tolerance for quantity and price.
**We got:** 290 L against a median of 100 L (190%) goes to the purchasing manager; 125 L (exactly 25%) does not.
**Example to show:** `src/tta/policy/profiles/*.yaml`, `standing_order_drift_ratio`.
**Ask:** "Are 25% and 10% the values we want to show, and is one tolerance for quantity and price enough, or should price get its own (prices rarely move 25%)?"
**If no answer, we build:** one tolerance, as now.
