"""The agent learns where the recipe matters and applies it before the offer is built (lane LF).

Scores on the 20% "solving the problem and user need" (the hotel's cream is an ingredient: nobody has to write "for
baking") and on the 20% "autonomy and controls" (the offer says what the gateway applied and from what, the request
stays as the buyer sent it, the buyer's own decision outranks the rest, and the buyer can switch the mode).
Figures are measured offline at the recording's own clock (Saturday 14 Nov 2026 02:52).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVERS, Sandbox
from tta.api.wiring import Parts
from tta.contracts.common import AuditReader, DecisionKind, Identity, IdentityKind, OrderStatus
from tta.contracts.offer import Offer
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.policy import BuyerProfile, FormulaMode
from tta.contracts.request import PurchaseRequest
from tta.customers.learned import APPLIED_FACT, LearnedSource
from tta.policy import PolicyLoadError, RulePolicyEngine

MONDAY = "2026-11-16"
WHIPPING, ESL, COOKING, HOTEL_MILK = "469346", "464727", "463797", "469363"
HOTEL_AGENT = Identity(kind=IdentityKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent (demo)",
                       profile_id="hotel-kitchen")
SUPPLIER = Identity(kind=IdentityKind.SUPPLIER, id="supplier:valio-aimo", display_name="Valio Aimo")
PARSED = "tta.v1.request.parsed"
LEARNED_NOTE = (
    "Request line 1: You use cream as an ingredient (Arla Pro Cooking cream 10% 1 L UHT lactose free (463797)), so a "
    "substitute for Arla Pro Whipping cream 1 L UHT lactose free (469346) must keep its recipe. Learned from your "
    "customer file, which is synthetic. The gateway applied this; your request did not say it. Change this in "
    "Settings."
)


def _cream(**line: Any) -> PurchaseRequest:
    return PurchaseRequest.model_validate({"needed_by": MONDAY, "lines": [{
        "text": "100 L of whipping cream 469346", "product_ids": [WHIPPING], "quantity": 100, "unit": "L", **line}]})


def _book(parts: Parts, key: str, mode: FormulaMode | None, customer_id: str | None = "hotel-kitchen") -> Sandbox:
    """A private book whose kitchen is the hotel's settings in one mode, standing for a customer file or for none."""
    assert parts.sandboxes is not None
    book = parts.sandboxes.open(key)
    if customer_id is not None:
        book.customer.name(customer_id)
    settings = {**book.kitchen.settings, "formula_matters": mode is FormulaMode.ALWAYS,
                "formula_mode": mode.value if mode else None}
    book.kitchen.set_up(settings)
    return book


def _rules(offer: Offer) -> dict[str, tuple[str, ...]]:
    return {option.kind.value: option.decision.rule_ids for option in offer.options}


def _decide(book: Sandbox, order: Order, kind: DecisionKind, option_id: str | None = None) -> Order:
    """Every role the approval asks for decides, each by the kitchen's approver who holds it."""
    for _ in range(len(KITCHEN_APPROVERS)):
        approval = book.store.get_approval(str(order.approval_id))
        assert approval is not None
        if not approval.roles_missing:
            break
        approver = next(one for one in KITCHEN_APPROVERS if approval.roles_missing[0] in one.roles)
        order = book.service.decide_approval(
            approver, approval.approval_id, DecisionRequest(decision=kind, option_id=option_id))
        if kind is DecisionKind.REJECT:
            break
    return order


# --- the setting -----------------------------------------------------------------------------------------------


def test_the_shipped_profiles_learn_except_the_bakery_which_always_keeps_the_recipe() -> None:
    policy = RulePolicyEngine.from_files()

    modes = {profile_id: policy.get_profile(profile_id).formula_mode for profile_id in policy.profile_ids()}

    assert modes == {"allergy-ward": FormulaMode.LEARN, "bakery-cafe": FormulaMode.ALWAYS,
                     "hotel-kitchen": FormulaMode.LEARN, "school-kitchen": FormulaMode.LEARN}
    assert policy.get_profile("bakery-cafe").formula_matters is True
    assert policy.get_profile("hotel-kitchen").formula_matters is False


def test_a_profile_that_sets_no_mode_reads_as_its_boolean_did(parts: Parts) -> None:
    book = _book(parts, "no-mode", None)
    always = book.kitchen.profile.model_copy(update={"formula_matters": True})

    assert book.kitchen.profile.formula_mode is None
    assert book.kitchen.profile.formula_mode_in_force is FormulaMode.WHEN_ASKED
    assert always.formula_mode_in_force is FormulaMode.ALWAYS


def test_always_alone_sets_the_boolean_and_a_contradiction_is_refused(parts: Parts) -> None:
    book = _book(parts, "modes", FormulaMode.LEARN)
    sent = {name: value for name, value in book.kitchen.settings.items() if name != "formula_matters"}

    always = book.kitchen.set_up({**sent, "formula_mode": "ALWAYS"})
    assert (always.formula_mode, always.formula_matters) == (FormulaMode.ALWAYS, True)

    with pytest.raises(PolicyLoadError, match="formula_mode LEARN and formula_matters true say different things"):
        book.kitchen.set_up({**sent, "formula_mode": "LEARN", "formula_matters": True})
    with pytest.raises(PolicyLoadError, match="formula_mode"):
        book.kitchen.set_up({**sent, "formula_mode": "SOMETIMES"})
    assert BuyerProfile.model_fields["formula_mode"].default is None


# --- LEARN: the hotel's cream is an ingredient -------------------------------------------------------------------


def test_in_learn_mode_the_hotels_whipping_cream_keeps_its_recipe_and_the_offer_says_why(parts: Parts) -> None:
    sent = _cream()

    offer = parts.service.create_offer(HOTEL_AGENT, sent)

    assert offer.request == sent and offer.request.lines[0].keep_formula is None  # as the buyer sent it
    assert all(line.keep_formula is True for option in offer.options for line in option.lines)
    assert _rules(offer) == {"BEST_CONFIRMED": ("P-03",), "SUBSTITUTE": ("F-11", "P-03")}
    best, substitute = offer.options
    assert (best.lines[0].product_id, best.totals.net) == (WHIPPING, Decimal("276.96"))  # 48 of the 100 L
    assert [line.product_id for line in substitute.lines] == [WHIPPING, ESL]
    assert offer.notes[-1] == LEARNED_NOTE


def test_when_asked_mode_applies_nothing_for_the_same_request(parts: Parts) -> None:
    book = _book(parts, "when-asked", FormulaMode.WHEN_ASKED)

    offer = book.service.create_offer(KITCHEN_AGENT, _cream())

    assert all(line.keep_formula is None for option in offer.options for line in option.lines)
    assert _rules(offer) == {"BEST_CONFIRMED": ("P-03",), "SUBSTITUTE": ("P-03",), "ALTERNATIVE_UNCONFIRMED": ("F-01",)}
    assert not any("The gateway applied this" in note for note in offer.notes)


def test_a_book_in_learn_mode_applies_it_like_the_profile_file_does(parts: Parts) -> None:
    book = _book(parts, "learn", FormulaMode.LEARN)

    offer = book.service.create_offer(KITCHEN_AGENT, _cream())

    assert _rules(offer)["SUBSTITUTE"] == ("F-11", "P-03") and offer.notes[-1] == LEARNED_NOTE


def test_a_request_that_says_so_itself_gets_no_note_from_the_gateway(parts: Parts) -> None:
    offer = parts.service.create_offer(HOTEL_AGENT, _cream(keep_formula=True))

    assert _rules(offer)["SUBSTITUTE"] == ("F-11", "P-03")
    assert not any("The gateway applied this" in note for note in offer.notes)


def test_the_trail_keeps_the_request_as_sent_and_says_what_the_gateway_applied(parts: Parts) -> None:
    offer = parts.service.create_offer(HOTEL_AGENT, _cream())

    (parsed,) = [event for event in parts.store.list_audit_events(offer_id=offer.offer_id) if event.type == PARSED]
    (applied,) = parsed.data.facts[APPLIED_FACT]
    assert parsed.data.facts["request"]["lines"][0]["keep_formula"] is None
    assert (applied["line"], applied["product_id"], applied["keep_formula"]) == (1, WHIPPING, True)
    assert (applied["applied_by"], applied["source"], applied["synthetic"]) == ("gateway", "USE", True)
    assert applied["evidence"]["usual_product_ids"] == [COOKING]
    # Valio Aimo's view holds neither the fact nor the note: how a buyer uses a product is the buyer's own.
    assert APPLIED_FACT not in parsed.data.supplier_facts
    supplier = parts.service.get_audit(SUPPLIER, AuditReader.SUPPLIER, offer_id=offer.offer_id)
    assert "ingredient" not in supplier.model_dump_json()
    assert parts.audit.verify_chain().ok


def test_scenario_1_is_unchanged_the_hotel_serves_its_milk(parts: Parts, scenario_1: dict[str, Any]) -> None:
    offer = parts.service.create_offer(HOTEL_AGENT, PurchaseRequest.model_validate(scenario_1))

    best, alternative = offer.options
    assert (best.coverage[0].covered, best.totals.net) == (Decimal(435), Decimal("1083.39"))
    assert alternative.totals.net == Decimal("1010.00")
    assert all(line.keep_formula is None for option in offer.options for line in option.lines)
    assert not any("The gateway applied this" in note for note in offer.notes)


# --- the buyer's own decisions and words, read from the book ---------------------------------------------------


def test_a_rejected_formula_changing_substitute_is_learned_from_the_order_book(parts: Parts) -> None:
    book = _book(parts, "decides", FormulaMode.LEARN, customer_id=None)  # no customer file: no use mark
    first = book.service.create_offer(KITCHEN_AGENT, _cream())
    assert not any("The gateway applied this" in note for note in first.notes)  # nothing to learn from yet
    substitute = next(option for option in first.options if option.kind.value == "SUBSTITUTE")
    order = book.service.place_order(KITCHEN_AGENT, first.offer_id, substitute.option_id, "learn-1")
    assert order.status is OrderStatus.PENDING_APPROVAL

    assert _decide(book, order, DecisionKind.REJECT).status is OrderStatus.REJECTED
    second = book.service.create_offer(KITCHEN_AGENT, _cream())

    assert _rules(second)["SUBSTITUTE"] == ("F-11", "P-03")
    note = second.notes[-1]
    assert note.startswith(
        "Request line 1: You rejected a substitute with different ingredients for Arla Pro Whipping cream 1 L UHT "
        "lactose free (469346) on ")
    assert "synthetic" not in note and note.endswith("Change this in Settings.")


def test_choosing_the_other_option_is_learned_and_two_acceptances_unlearn_it(parts: Parts) -> None:
    book = _book(parts, "chooses", FormulaMode.LEARN, customer_id=None)

    def order_substitute(key: str, choose_best: bool) -> Offer:
        offer = book.service.create_offer(KITCHEN_AGENT, _cream())
        options = {option.kind.value: option.option_id for option in offer.options}
        order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, options["SUBSTITUTE"], key)
        decided = _decide(book, order, DecisionKind.APPROVE, options["BEST_CONFIRMED"] if choose_best else None)
        assert decided.status is OrderStatus.ORDERED, decided.status_sentence
        return book.service.create_offer(KITCHEN_AGENT, _cream())

    after_choice = order_substitute("choose-1", choose_best=True)
    assert "You chose another option over a substitute with different ingredients" in after_choice.notes[-1]

    order_substitute("accept-1", choose_best=False)
    after_two = order_substitute("accept-2", choose_best=False)
    assert not any("The gateway applied this" in note for note in after_two.notes)
    assert _rules(after_two)["SUBSTITUTE"] == ("P-03",)


def test_requests_that_said_so_teach_the_next_ones_and_what_the_gateway_applied_never_counts(parts: Parts) -> None:
    book = _book(parts, "words", FormulaMode.LEARN)
    milk = {"needed_by": MONDAY, "lines": [{"text": "100 L of milk", "product_ids": [HOTEL_MILK], "quantity": 100,
                                            "unit": "L"}]}
    said = PurchaseRequest.model_validate({**milk, "lines": [{**milk["lines"][0], "keep_formula": True}]})
    silent = PurchaseRequest.model_validate(milk)

    before = book.service.create_offer(KITCHEN_AGENT, silent)  # served as it is: nothing applied
    book.service.create_offer(KITCHEN_AGENT, said)
    book.service.create_offer(KITCHEN_AGENT, said)
    after = book.service.create_offer(KITCHEN_AGENT, silent)  # 2 of 3 past requests said so
    again = book.service.create_offer(KITCHEN_AGENT, silent)  # still 2 of 3: a line the gateway taught is not counted

    assert not any("The gateway applied this" in note for note in before.notes)
    assert "2 of your 3 past requests for Arla Semi skimmed milkdrink" in after.notes[-1]
    assert again.notes[-1] == after.notes[-1]  # what was learned from words does not unlearn or teach itself
    (parsed,) = [event for event in book.store.list_audit_events(offer_id=again.offer_id) if event.type == PARSED]
    assert parsed.data.facts["request"]["lines"][0]["keep_formula"] is None
    learned = {each.product_id: each for each in book.service.get_learned(KITCHEN_AGENT).findings}
    assert learned[HOTEL_MILK].source is LearnedSource.WORDS and learned[HOTEL_MILK].matters is True


# --- what the buyer reads about it -------------------------------------------------------------------------------


def test_the_learned_view_names_each_usual_product_its_source_and_the_mode(parts: Parts) -> None:
    view = parts.service.get_learned(HOTEL_AGENT)

    assert (view.mode, view.applied) == (FormulaMode.LEARN, True)
    found = {each.product_id: each for each in view.findings}
    # The beef chuck (466988) is used as an ingredient too, and nothing is learned for it: a raw cut has no recipe
    # of its own to keep (`raw` in product_types.yaml), so only the cooking cream is learned.
    assert {product_id: (each.matters, each.source) for product_id, each in found.items()} == {
        "469363": (False, LearnedSource.USE), "463797": (True, LearnedSource.USE), "464615": (False, LearnedSource.USE),
        "463203": (False, LearnedSource.USE), "466988": (None, LearnedSource.USE)}
    assert "is raw beef chuck, which has no recipe of its own: nothing is learned for it" in found["466988"].sentence
    assert view.summary == (
        "Learned so far: Arla Pro Cooking cream 10% 1 L UHT lactose free (you use it as an ingredient). "
        "From your customer file, which is synthetic."
    )


def test_the_view_shows_what_is_learned_without_applying_it_when_the_mode_is_when_asked(parts: Parts) -> None:
    view = _book(parts, "view", FormulaMode.WHEN_ASKED).service.get_learned(KITCHEN_AGENT)

    assert (view.mode, view.applied) == (FormulaMode.WHEN_ASKED, False)
    assert "shown and not applied" in view.note and len(view.findings) == 5


def test_the_supplier_does_not_read_what_a_buyer_has_taught(parts: Parts) -> None:
    from tta.contracts.errors import NotAuthorised

    with pytest.raises(NotAuthorised):
        parts.service.get_learned(SUPPLIER)
