"""How the order was decided, read from the facts of the supplier's view of the trail (P9b B13-2)."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from tta.api.sandbox import KITCHEN_AGENT
from tta.api.wiring import Parts
from tta.audit.readers import REASONS_OF_THE_BUYER
from tta.contracts.audit import AuditView
from tta.contracts.common import ApproverRole, AuditReader, ExclusionReason, Unit, Verdict
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.ui.supplier_view import supplier_decision


def _audit(*facts: dict[str, Any]) -> Any:
    """A trail whose events carry these facts, oldest first: the page reads only `events[].facts` and `.id`."""
    return SimpleNamespace(events=[SimpleNamespace(id=f"evt_{n}", facts=one) for n, one in enumerate(facts)])


DECISION = {
    "verdict": "APPROVAL",
    "rules": [
        {"rule_id": "P-01", "title": "The order is above the spend limit per order", "fixed": False,
         "verdict": "APPROVAL", "approver_role": "purchasing_manager", "product_id": None},
        {"rule_id": "F-01", "title": "A quantity is not confirmed", "fixed": True, "verdict": "APPROVAL",
         "approver_role": "purchasing_manager", "product_id": "464306"},
        {"rule_id": "F-01", "title": "A quantity is not confirmed", "fixed": True, "verdict": "APPROVAL",
         "approver_role": "purchasing_manager", "product_id": "473609"},
    ],
}
OFFER = {
    "excluded_by_reason": {"ALLERGEN_DECLARED": 2, "CUTOFF_PASSED": 1, "NOT_DELIVERABLE": 12},
    "left_out": [{"product_id": "471690", "name": "Oat drink", "reason": "CUTOFF_PASSED"}]
    + [{"product_id": f"4700{n:02d}", "name": None, "reason": "NOT_DELIVERABLE"} for n in range(12)],
}


def test_a_rule_that_fired_on_two_lines_is_one_row_with_both_products_and_what_is_masked() -> None:
    found = supplier_decision(_audit({"offer": OFFER}, {"decision": DECISION}))

    assert found is not None and found.verdict is Verdict.APPROVAL
    assert [(row.rule_id, row.product_ids) for row in found.rules] == [("P-01", ()), ("F-01", ("464306", "473609"))]
    assert found.rules[0].masked == "the amount is not shown" and found.rules[1].masked is None
    assert found.rules[0].approver_role is ApproverRole.PURCHASING_MANAGER


def test_products_left_out_come_by_reason_and_a_reason_of_the_buyer_s_gives_no_row_and_no_count() -> None:
    """Review finding M1. The facts here are those of an event stored before the fix: they still hold the count."""
    found = supplier_decision(_audit({"offer": OFFER}, {"decision": DECISION}))

    assert found is not None
    rows = {row.reason: row for row in found.left_out}
    assert list(rows) == [ExclusionReason.NOT_DELIVERABLE, ExclusionReason.CUTOFF_PASSED]
    assert (len(rows[ExclusionReason.NOT_DELIVERABLE].products), rows[ExclusionReason.NOT_DELIVERABLE].more) == (10, 2)
    assert found.not_shown == "Products left out for a requirement of the buyer's, if any, are not shown or counted."


def test_a_trail_without_a_decision_or_with_one_that_cannot_be_read_shows_none() -> None:
    assert supplier_decision(_audit({"offer": OFFER})) is None
    assert supplier_decision(_audit({"decision": {"verdict": "MAYBE"}})) is None


def test_an_offer_fact_that_cannot_be_read_leaves_the_decision_and_no_product_list() -> None:
    found = supplier_decision(_audit({"offer": {"left_out": "not a list"}}, {"decision": DECISION}))

    assert found is not None and found.rules and found.left_out == ()


# --- the leak test (security review, finding M1) ----------------------------------------------------------
# The same request twice, in two order books whose buyer differs only in what it excludes. Valio Aimo's whole view
# of the two logs (every sentence, fact, rule id and actor) is compared as text, apart from ids, hashes and times.

MONDAY = date(2026, 11, 16)
WARD, HOTEL = "allergy-ward", "hotel-kitchen"
MILK, GLUTEN, TREE_NUTS, SOY = "AM", "AW", "AN", "AY"
AN_ID = re.compile(r"\b(off|ord|apr)_[0-9a-f]+")
A_TIME = re.compile(r"\d{4}-\d\d-\d\dT[0-9:.]+(Z|[+-]\d\d:\d\d)")
LEFT_OUT_CLAUSE = re.compile(r"(Left out for a reason in Valio Aimo's own data: .*?|No product was left out for a "
                             r"reason in Valio Aimo's own data)\. Products left out for a requirement")
OF_THE_BUYER = {reason.value for reason in REASONS_OF_THE_BUYER}


def _plant_drink(litres: int, confirmed_only: bool, exclude: tuple[str, ...] = ()) -> PurchaseRequest:
    line = RequestLine(text=f"{litres} litres of a milk substitute by Monday", product_type="plant_drink",
                       quantity=Decimal(litres), unit=Unit.L, exclude_allergens=exclude)
    return PurchaseRequest(needed_by=MONDAY, require_confirmed=confirmed_only, lines=(line,))


WARD_200_L = _plant_drink(200, confirmed_only=True)  # scenario 2: the ward's request


def _logs(parts: Parts, key: str, start: str, change: dict[str, Any], request: PurchaseRequest) -> tuple[Any, Any]:
    """Offer and order in a book of its own, whose buyer is a copy of `start` with `change`. Valio Aimo's view of
    the offer's events and the buyer's."""
    book = parts.sandboxes.open(key)
    book.kitchen.start_from(start)
    book.kitchen.set_up({**book.kitchen.settings, **change})
    offer = book.service.create_offer(KITCHEN_AGENT, request)
    book.service.place_order(KITCHEN_AGENT, offer.offer_id, offer.options[0].option_id, f"leak-test-{key}")
    read = book.service.get_audit
    return (read(KITCHEN_AGENT, AuditReader.SUPPLIER, offer_id=offer.offer_id),
            read(KITCHEN_AGENT, AuditReader.BUYER, offer_id=offer.offer_id))


def _events(view: AuditView) -> list[dict[str, Any]]:
    """Every event of a view without its id, hash and time, and with every id and time inside it made the same."""
    dumped = json.dumps([event.model_dump(mode="json", exclude={"id", "hash", "time"}) for event in view.events],
                        sort_keys=True, ensure_ascii=False)
    same: list[dict[str, Any]] = json.loads(A_TIME.sub("<time>", AN_ID.sub(r"\1_<id>", dumped)))
    return same


def _as_text(view: AuditView) -> str:
    return json.dumps(_events(view), sort_keys=True, ensure_ascii=False, indent=1)


def _left_out(buyer: AuditView) -> dict[str, int]:
    """Reason -> how many products were left out for it, from the buyer's own facts, which hold every reason."""
    offer = next(event.facts["offer"] for event in buyer.events if event.type.endswith("offer.created"))
    counts: dict[str, int] = offer["excluded_by_reason"]
    return counts


STRICTNESS_ONLY = {
    "the ward's 200 L, confirmed data only": (WARD, {}, WARD_200_L),
    "a hotel that excludes tree nuts, 80 L": (HOTEL, {"excluded_allergens": [TREE_NUTS]}, _plant_drink(80, False)),
}


@pytest.mark.parametrize("case", list(STRICTNESS_ONLY))
def test_valio_reads_the_same_log_whether_the_buyers_allergen_rule_is_strict_or_declared_only(
    parts: Parts, case: str
) -> None:
    start, change, request = STRICTNESS_ONLY[case]

    strict, _ = _logs(parts, "strict", start, {**change, "allergen_strictness": "STRICT"}, request)
    declared, _ = _logs(parts, "declared", start, {**change, "allergen_strictness": "DECLARED_ONLY"}, request)

    assert _as_text(strict) == _as_text(declared)


# Two buyers that differ only in the allergens excluded, where the offer holds the same products for both. The
# counts the buyer reads differ: the ward 18 declaring and 5 stating nothing against 21 and 6 (the reviewer's
# figures); the hotel 3 declaring against 13.
EXCLUSIONS_ONLY = {
    "the ward's 200 L, tree nuts excluded as well": (
        (WARD, {"excluded_allergens": [MILK, GLUTEN]}, WARD_200_L),
        (WARD, {"excluded_allergens": [MILK, GLUTEN, TREE_NUTS]}, WARD_200_L),
    ),
    "a hotel request of 80 L that excludes tree nuts, or tree nuts and soy": (
        (HOTEL, {}, _plant_drink(80, False, exclude=(TREE_NUTS,))),
        (HOTEL, {}, _plant_drink(80, False, exclude=(TREE_NUTS, SOY))),
    ),
}


def _without_the_products_left_out(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The events without the list of products left out for a reason in Valio Aimo's own data, its counts and
    the part of the sentence that prints them."""
    def offer_without(facts: dict[str, Any]) -> dict[str, Any]:
        if "offer" not in facts:
            return facts
        kept = {key: value for key, value in facts["offer"].items() if key not in ("left_out", "excluded_by_reason")}
        return {**facts, "offer": kept}

    return [{**event, "facts": offer_without(event["facts"]),
             "sentence": LEFT_OUT_CLAUSE.sub("<left out>. Products left out for a requirement", event["sentence"])}
            for event in events]


@pytest.mark.parametrize("case", list(EXCLUSIONS_ONLY))
def test_valio_reads_no_count_of_the_products_left_out_for_what_the_buyer_excludes(parts: Parts, case: str) -> None:
    """What still differs is named exactly: a product that Valio Aimo's own data would leave out as well (its
    closing time has passed, it cannot be delivered) is judged on the buyer's allergen first, so it goes missing
    from Valio Aimo's list when the buyer excludes its allergen. Nothing else differs, and no count of the masked
    products is anywhere. Closing that needs the offer to say both reasons (hand-back of FX-M1, for the offers lane);
    the test below is the strict form and is expected to fail until then."""
    one, other = EXCLUSIONS_ONLY[case]
    (first, first_buyer), (second, second_buyer) = _logs(parts, "one", *one), _logs(parts, "other", *other)

    buyers = [_left_out(first_buyer), _left_out(second_buyer)]
    # the buyer keeps every count
    assert buyers[0] != buyers[1] and all(OF_THE_BUYER & set(counts) for counts in buyers)
    supplier = [_events(first), _events(second)]
    assert _without_the_products_left_out(supplier[0]) == _without_the_products_left_out(supplier[1])
    for events, counts in zip(supplier, buyers, strict=True):
        offers = [event["facts"]["offer"] for event in events if "offer" in event["facts"]]
        assert offers and all(OF_THE_BUYER.isdisjoint(offer["excluded_by_reason"]) for offer in offers)
        assert all(OF_THE_BUYER.isdisjoint(entry["reason"] for entry in offer["left_out"]) for offer in offers)
        for offer in offers:  # what Valio Aimo is told is true of its own data: the buyer reads the same counts
            assert offer["excluded_by_reason"] == {r: n for r, n in counts.items() if r not in OF_THE_BUYER}
        text = json.dumps(events, ensure_ascii=False)
        masked = sum(number for reason, number in counts.items() if reason in OF_THE_BUYER)
        assert f"{sum(counts.values())} product" not in text and "allergen the buyer excludes" not in text
        assert not re.search(rf"\b{masked} (products? )?(declaring|stating|left out|for an allergen)", text)
    # the residue: products missing from one list are exactly as many as moved to the masked reasons
    listed = [{entry["product_id"] for event in events if "offer" in event["facts"]
               for entry in event["facts"]["offer"]["left_out"]} for events in supplier]
    assert listed[1] < listed[0]
    moved = sum(buyers[0][r] for r in buyers[0] if r not in OF_THE_BUYER) - sum(
        buyers[1][r] for r in buyers[1] if r not in OF_THE_BUYER)
    assert len(listed[0] - listed[1]) == moved > 0


@pytest.mark.xfail(strict=True, reason=(
    "A product left out for the buyer's allergen is not also listed under the reason Valio Aimo's own data gives "
    "(closing time passed, cannot be delivered): the offer records one reason per product, the allergen first "
    "(tta.offers.candidates). Valio Aimo, who knows its own data, can see which of its products are missing from "
    "the list. Needs the second reason from the offers lane; see the hand-back of FX-M1."
))
@pytest.mark.parametrize("case", list(EXCLUSIONS_ONLY))
def test_valio_reads_the_same_log_whatever_the_buyer_excludes(parts: Parts, case: str) -> None:
    one, other = EXCLUSIONS_ONLY[case]

    (first, _), (second, _) = _logs(parts, "one", *one), _logs(parts, "other", *other)

    assert _as_text(first) == _as_text(second)
