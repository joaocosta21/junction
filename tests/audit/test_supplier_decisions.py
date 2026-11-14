"""Valio Aimo's view of the log (package S4, `P9b-booth-answers.md` B13-1): every rule that fired with its reason,
the logic, and the products considered and left out. Limit amounts and allergen codes are masked, the role stands
for the approver's name, notes and the buyer's own words stay out.

Scores on the 20% "how decisions are logged and auditable" and on the brief's audit trail "for both buyer and
Valio Aimo".
"""

from __future__ import annotations

from decimal import Decimal

from tta.audit import AuditTrail
from tta.audit.readers import NOT_SHOWN_OR_COUNTED, shown_facts, shown_sentence, supplier_actor
from tta.audit.views import project
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    AuditReader,
    ExclusionReason,
    OrderStatus,
    Unit,
    Verdict,
)
from tta.contracts.offer import Exclusion
from tta.contracts.policy import FiredRule
from tta.contracts.request import PurchaseRequest, RequestLine

MANAGER = "the buyer's purchasing manager"
UNCONFIRMED = "1,000 pcs of 464306 for €1,010.00 net"
PARTIAL = "698 pcs of 463380 and 51 pcs of 462775 for €1,980.77 net"
F01 = "F-01, a fixed rule (rule F-01), on product 464306: approval by the buyer's purchasing manager."
P01 = (
    "P-01, a rule the buyer set (rule P-01; the amount is not shown): approval by the buyer's purchasing manager."
)
P03 = (
    "P-03, a rule the buyer set (rule P-03; the buyer's minimum is not shown): "
    "approval by the buyer's purchasing manager."
)


def _excluded(product_id: str, reason: ExclusionReason) -> Exclusion:
    return Exclusion(product_id=product_id, name=f"Product {product_id}", request_line_index=0, reason=reason,
                     sentence="Declares milk (AM).")


def test_valio_reads_every_rule_that_fired_with_its_reason_its_outcome_and_the_logic(
    trail: AuditTrail, samples
) -> None:
    option = samples.unconfirmed_option()

    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_1", option=option))

    assert event.data.supplier_sentence == (
        f"The buyer's rules were checked for option opt_2: {MANAGER} must approve this order. "
        f"Rules that applied: {F01} {P01} The strictest outcome among the rules that applied decides."
    )
    assert "€750" not in event.data.supplier_sentence and "750" not in str(event.data.supplier_facts)


def test_valio_reads_a_buyer_s_rule_when_it_is_the_only_one_that_fired(trail: AuditTrail, samples) -> None:
    option = samples.partial_option()

    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_1", option=option))

    assert event.data.supplier_sentence == (
        f"The buyer's rules were checked for option opt_1: {MANAGER} must approve this order. "
        f"Rules that applied: {P01} {P03} The strictest outcome among the rules that applied decides."
    )


def test_valio_reads_that_no_rule_applied_when_the_agent_may_order_alone(trail: AuditTrail, samples) -> None:
    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_2", option=samples.ward_option()))

    assert event.data.supplier_sentence == (
        "The buyer's rules were checked for option opt_1: the agent may place this order within its authority. "
        "No rule applied."
    )


def test_a_rule_about_an_excluded_allergen_is_named_without_the_allergen_and_without_the_product(
    trail: AuditTrail, samples
) -> None:
    declared = FiredRule(
        rule_id="F-02", title="A line declares an excluded allergen", fixed=True, verdict=Verdict.BLOCK,
        sentence="463380 declares milk (AM), which the profile excludes.", facts={"allergen": "AM"},
        product_id="463380",
    )
    unstated = FiredRule(
        rule_id="P-04", title="A line does not rule out an excluded allergen", fixed=False,
        verdict=Verdict.APPROVAL, approver_role=ApproverRole.DIETITIAN,
        sentence="462775 states nothing about gluten (AW).", facts={"allergen": "AW"}, product_id="462775",
    )
    option = samples.option("opt_1", samples.partial_option().lines, samples.decision(declared, unstated))

    event = trail.record(AuditEventType.ORDER_BLOCKED, samples.gateway,
                         AuditContext(offer_id="off_1", option=option))
    checked = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                           AuditContext(offer_id="off_1", option=option))

    blocked = (
        "F-02, a fixed rule (a line declares an excluded allergen; which allergen and which product are not "
        "shown): the order cannot be placed."
    )
    assert event.data.supplier_sentence == (
        f"The buyer's rules blocked the order of option opt_1 of offer off_1. Nothing was ordered. "
        f"Rule that applied: {blocked}"
    )
    assert checked.data.supplier_sentence == (
        "The buyer's rules were checked for option opt_1: this order cannot be placed. "
        f"Rules that applied: {blocked} "
        "P-04, a rule the buyer set (a line does not rule out an excluded allergen; which allergen and which "
        "product are not shown): approval by the buyer's dietitian. "
        "The strictest outcome among the rules that applied decides."
    )
    assert checked.data.supplier_facts["decision"]["rules"] == [
        {"rule_id": "F-02", "title": "A line declares an excluded allergen", "fixed": True, "verdict": "BLOCK",
         "approver_role": None, "product_id": None},
        {"rule_id": "P-04", "title": "A line does not rule out an excluded allergen", "fixed": False,
         "verdict": "APPROVAL", "approver_role": "dietitian", "product_id": None},
    ]
    shown = f"{checked.data.supplier_sentence} {checked.data.supplier_facts}"
    assert [word for word in ("'AM'", "'AW'", "(AM)", "(AW)", "milk (", "gluten") if word in shown] == []


def test_the_decision_facts_list_each_rule_by_id_title_kind_outcome_role_and_product(
    trail: AuditTrail, samples
) -> None:
    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_1", option=samples.unconfirmed_option()))

    assert event.data.supplier_facts["decision"] == {
        "verdict": "APPROVAL",
        "rule_ids": ["F-01", "P-01"],
        "rules": [
            {"rule_id": "F-01", "title": "Rule F-01", "fixed": True, "verdict": "APPROVAL",
             "approver_role": "purchasing_manager", "product_id": "464306"},
            {"rule_id": "P-01", "title": "Rule P-01", "fixed": False, "verdict": "APPROVAL",
             "approver_role": "purchasing_manager", "product_id": None},
        ],
        "required_roles": ["purchasing_manager"],
        "evaluated_at": "2026-11-14T02:52:00+02:00",
    }


def test_valio_reads_the_products_considered_and_left_out_by_reason(trail: AuditTrail, samples) -> None:
    offer = samples.hotel_offer()

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert event.data.supplier_sentence == (
        "The gateway built offer off_1 from a recorded copy of Valio Aimo's data: "
        "2 options from 35 candidates. "
        f"Option 1 (best confirmed): {PARTIAL}, covering 74.9% of the request. "
        f"Option 2 (alternative, quantity not confirmed): {UNCONFIRMED}, covering the full quantity. "
        "Left out for a reason in Valio Aimo's own data: 1 past the closing time for ordering (471690); "
        f"1 sold in portion packs, which the request does not ask for (463203). {NOT_SHOWN_OR_COUNTED}"
    )
    assert event.data.supplier_facts["offer"]["left_out"] == [
        {"product_id": "463203", "name": "Portion milk", "request_line_index": 0, "reason": "PORTION_PACK"},
        {"product_id": "471690", "name": "Oat drink", "request_line_index": 0, "reason": "CUTOFF_PASSED"},
    ]


def _ward_offer_leaving_out(samples, declared: int, not_stated: int):
    """The ward's plant-drink offer with this many products left out for each of the two allergen reasons."""
    excluded = (
        *(_excluded(f"47{number:04}", ExclusionReason.CUTOFF_PASSED) for number in range(12)),
        *(_excluded(f"48{number:04}", ExclusionReason.NOT_DELIVERABLE) for number in range(6)),
        *(_excluded(f"49{number:04}", ExclusionReason.ALLERGEN_DECLARED) for number in range(declared)),
        *(_excluded(f"50{number:04}", ExclusionReason.ALLERGEN_NOT_STATED) for number in range(not_stated)),
    )
    return samples.ward_offer().model_copy(update={"excluded": excluded, "candidates_considered": 51})


def test_products_left_out_for_an_allergen_are_neither_listed_nor_counted(trail: AuditTrail, samples) -> None:
    """Review finding M1: 18 declaring and 5 stating nothing, per product type, name the allergens to whoever has
    the catalog. Valio Aimo reads the reasons about its own data, no total, and one sentence without a number."""
    offer = _ward_offer_leaving_out(samples, declared=18, not_stated=5)

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert event.data.supplier_sentence.endswith(
        "covering the full quantity. Left out for a reason in Valio Aimo's own data: "
        "6 that cannot be delivered (480000, 480001, 480002, 480003, 480004 and 480005); "
        "12 past the closing time for ordering (470000, 470001, 470002, 470003, 470004, 470005, 470006, 470007, "
        "470008, 470009 and 2 more). "
        "Products left out for a requirement of the buyer's, if any, are not shown or counted."
    )
    facts = event.data.supplier_facts["offer"]
    assert facts["excluded_by_reason"] == {"CUTOFF_PASSED": 12, "NOT_DELIVERABLE": 6}
    assert len(facts["left_out"]) == 18
    assert {entry["reason"] for entry in facts["left_out"]} == {"CUTOFF_PASSED", "NOT_DELIVERABLE"}
    shown = f"{event.data.supplier_sentence} {event.data.supplier_facts}"
    never = ("490000", "500004", "(AM)", "Declares milk", "41", "23", "allergen")
    assert [word for word in never if word in shown] == []
    # the buyer keeps every count
    assert event.data.facts["offer"]["excluded_by_reason"] == {
        "ALLERGEN_DECLARED": 18, "ALLERGEN_NOT_STATED": 5, "CUTOFF_PASSED": 12, "NOT_DELIVERABLE": 6,
    }
    assert "41 products excluded with a reason" in event.data.sentence


def test_valio_reads_the_same_offer_whatever_the_buyer_excludes_and_whether_it_excludes_anything(
    trail: AuditTrail, samples
) -> None:
    written = [
        trail.record(AuditEventType.OFFER_CREATED, samples.gateway,
                     AuditContext(offer=_ward_offer_leaving_out(samples, declared, not_stated)))
        for declared, not_stated in ((18, 5), (21, 6), (18, 0), (0, 0))
    ]

    assert len({event.data.supplier_sentence for event in written}) == 1
    assert len({str(event.data.supplier_facts) for event in written}) == 1
    assert len({event.data.sentence for event in written}) == 4  # the buyer's own sentence says how many


STORED_BEFORE_THE_FIX = (
    "The gateway built offer off_2 from a recorded copy of Valio Aimo's data: 1 option from 51 candidates. "
    "Option 1 (best confirmed): 200 pcs of 464013 for €402.00 net, covering the full quantity. "
    "{total} products were considered and left out: 6 that cannot be delivered (468417 and 474957); "
    "12 past the closing time for ordering (469040, 470611 and 10 more); "
    "{declared} declaring an allergen the buyer excludes (which allergen and which products are not shown); "
    "{not_stated} stating nothing about an allergen the buyer excludes (which allergen and which products are not "
    "shown)."
)


def test_an_event_stored_before_the_fix_is_read_without_the_counts_it_holds(trail: AuditTrail, samples, store) -> None:
    """The stored row keeps its facts and its hash; the supplier's reader masks the two counts and the total."""
    def facts(declared: int, not_stated: int) -> dict:
        return {"offer": {"offer_id": "off_2", "candidates_considered": 51, "left_out": [], "excluded_by_reason": {
            "ALLERGEN_DECLARED": declared, "ALLERGEN_NOT_STATED": not_stated, "CUTOFF_PASSED": 12,
            "NOT_DELIVERABLE": 6}}}

    one = STORED_BEFORE_THE_FIX.format(total=41, declared=18, not_stated=5)
    other = STORED_BEFORE_THE_FIX.format(total="1,044", declared="1,021", not_stated=6)

    assert shown_sentence(one) == shown_sentence(other) == (
        "The gateway built offer off_2 from a recorded copy of Valio Aimo's data: 1 option from 51 candidates. "
        "Option 1 (best confirmed): 200 pcs of 464013 for €402.00 net, covering the full quantity. "
        "Left out for a reason in Valio Aimo's own data (products left out for a requirement of the buyer's, "
        "if any, are not shown or counted): 6 that cannot be delivered (468417 and 474957); "
        "12 past the closing time for ordering (469040, 470611 and 10 more)."
    )
    assert shown_facts(facts(18, 5)) == shown_facts(facts(21, 6))
    assert shown_facts(facts(18, 5))["offer"]["excluded_by_reason"] == {"CUTOFF_PASSED": 12, "NOT_DELIVERABLE": 6}
    only_masked = (
        "no option fits the request; 12 candidates. 2 products were considered and left out: 2 declaring an "
        "allergen the buyer excludes (which allergen and which products are not shown)."
    )
    assert shown_sentence(only_masked) == (
        "no option fits the request; 12 candidates. Left out for a reason in Valio Aimo's own data (products left "
        "out for a requirement of the buyer's, if any, are not shown or counted): none."
    )
    untouched = {"decision": {"verdict": "AUTO"}, "offer": {"excluded_by_reason": {"CUTOFF_PASSED": 1}}}
    assert shown_facts(untouched) is untouched and shown_facts({}) == {}
    assert shown_facts({"offer": "x"}) == {"offer": "x"}

    # through the trail: the event as stored is not changed, the chain still verifies, the view is masked
    written = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=samples.ward_offer()))
    old = written.model_copy(update={"data": written.data.model_copy(update={
        "supplier_sentence": one, "supplier_facts": facts(18, 5)})})
    seen = project(old, AuditReader.SUPPLIER)
    assert "18 declaring" not in seen.sentence and "41 products" not in seen.sentence
    assert "ALLERGEN_DECLARED" not in str(seen.facts) and old.data.supplier_facts == facts(18, 5)
    assert project(old, AuditReader.BUYER).facts == old.data.facts


def test_a_missing_allergen_fact_does_not_name_its_product_and_a_missing_price_fact_does(
    trail: AuditTrail, samples
) -> None:
    """Python review P14: F-03 on a line because the allergen outcome is missing hints at an exclusion, as F-02
    and P-04 would. A missing fact about Valio Aimo's own data keeps its product."""
    allergen = samples.rule(
        "F-03", "The allergen check of 470001 is missing, so rule P-04 cannot be checked.", product_id="470001",
        role=ApproverRole.DIETITIAN,
        facts={"missing_fact": "line.allergen_outcomes", "reason": "not stated", "needed_by": ["F-02", "P-04"]},
    )
    needed_by_an_allergen_rule = samples.rule(
        "F-03", "A fact of 470003 is missing.", product_id="470003", role=ApproverRole.DIETITIAN,
        facts={"missing_fact": "line.some_fact", "reason": "not stated", "needed_by": ["P-04"]},
    )
    price = samples.rule(
        "F-03", "The price of 470002 is missing, so rule P-01 cannot be checked.", product_id="470002",
        facts={"missing_fact": "line.net", "reason": "not stated", "needed_by": ["P-01"]},
    )
    lines = (samples.line("470001", "10", "2.00"), samples.line("470002", "10", "2.00"))
    option = samples.option("opt_1", lines, samples.decision(allergen, needed_by_an_allergen_rule, price), "20")

    event = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                         AuditContext(offer_id="off_1", option=option))

    assert (
        "F-03, a fixed rule (rule F-03; a product is not shown where the missing fact is about a requirement of "
        "the buyer's): approval by the buyer's dietitian. "
        "F-03, a fixed rule (rule F-03), on product 470002: approval by the buyer's purchasing manager."
    ) in event.data.supplier_sentence
    # the two firings that hide their product are one entry: how many lines they are is not Valio Aimo's to read
    assert [rule["product_id"] for rule in event.data.supplier_facts["decision"]["rules"]] == [None, "470002"]
    # the line itself is in the option Valio Aimo reads; what is hidden is that this rule fired on it
    shown = f"{event.data.supplier_sentence} {event.data.supplier_facts['decision']}"
    assert "470001" not in shown and "470003" not in shown and "allergen" not in shown
    assert "470001" in str(event.data.facts["decision"])  # the buyer keeps it


def test_valio_aimo_s_own_token_is_named_as_such_and_not_as_a_human_at_the_buyer(trail: AuditTrail, samples) -> None:
    """Python review P13: the supplier's token refused on an approval read "A human at the buyer"."""
    reader = Actor(kind=ActorKind.HUMAN, id="supplier:valio-aimo", role="supplier", display_name="Valio Aimo reader")

    event = trail.record(AuditEventType.AUTHORISATION_REFUSED, reader, AuditContext(approval_id="apr_1"))
    seen = trail.view(AuditReader.SUPPLIER).events[-1]

    assert event.data.supplier_sentence == (
        "Valio Aimo's reader was refused on approval apr_1: this caller may not decide it."
    )
    assert seen.actor == Actor(
        kind=ActorKind.HUMAN, id="supplier-reader", role="supplier", display_name="Valio Aimo's reader",
    )
    assert "supplier:valio-aimo" not in f"{seen.sentence} {seen.actor}"


def test_an_offer_with_no_option_still_says_what_was_left_out(trail: AuditTrail, samples) -> None:
    offer = samples.hotel_offer().model_copy(update={"options": (), "notes": ("Nothing excludes AM.",)})

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert event.data.supplier_sentence == (
        "The gateway built offer off_1 from a recorded copy of Valio Aimo's data: "
        "no option fits the request; 35 candidates. "
        "Left out for a reason in Valio Aimo's own data: 1 past the closing time for ordering (471690); "
        f"1 sold in portion packs, which the request does not ask for (463203). {NOT_SHOWN_OR_COUNTED}"
    )


def test_valio_reads_the_claims_and_labels_asked_for_and_none_of_the_buyer_s_words(
    trail: AuditTrail, samples
) -> None:
    organic = RequestLine(
        text="50 kg of organic oats, no nuts please", name_terms=("oats",), product_type="oats",
        required_claims=("FREE_FROM_GLUTEN", "no nuts please"), required_labels=("EU_ORGANIC_FARMING",),
        quantity=Decimal("50"), unit=Unit.KG, exclude_allergens=("AN",),
    )
    context = AuditContext(profile_id="hotel-kitchen", offer_id="off_1",
                           request=PurchaseRequest(lines=(samples.hotel_request().lines[0], organic)))

    event = trail.record(AuditEventType.REQUEST_PARSED, samples.gateway, context)

    assert event.data.supplier_sentence == (
        "The request was read as: 1,000 litres of product type lactose_free_milk with claim FREE_FROM_LACTOSE; "
        "50 kg of product type oats with claim FREE_FROM_GLUTEN (1 more requirement is in the buyer's own words "
        "and is not shown) carrying label EU_ORGANIC_FARMING."
    )
    lines = event.data.supplier_facts["request"]["lines"]
    assert lines[0]["required_claims"] == ["FREE_FROM_LACTOSE"] and lines[0]["required_labels"] == []
    assert lines[1]["required_claims"] == ["FREE_FROM_GLUTEN"]
    assert lines[1]["required_labels"] == ["EU_ORGANIC_FARMING"]
    shown = f"{event.data.supplier_sentence} {event.data.supplier_facts}"
    assert [word for word in ("nuts", "organic oats", "'AN'", "exclude", "name_terms") if word in shown] == []


def test_the_role_stands_for_the_approver_s_name_from_the_request_to_the_order(hotel_flow: AuditTrail) -> None:
    supplier = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events
    requested, decided, confirmed = supplier[5], supplier[6], supplier[7]

    assert requested.sentence == (
        "The agent could not place order ord_1 alone under the buyer's rules. "
        f"The order ({PARTIAL}) was sent to {MANAGER} for approval. Rules that applied: {P01} {P03}"
    )
    assert decided.sentence == (
        "The buyer's purchasing manager approved order ord_1 and chose another option of the same offer: "
        f"opt_2 ({UNCONFIRMED}) instead of opt_1. This approval accepts rules F-01 and P-01."
    )
    assert confirmed.sentence.startswith(f"Order ord_1 is ordered, with approval by {MANAGER}: {UNCONFIRMED}.")
    assert (decided.actor.id, decided.actor.role, decided.actor.display_name) == (
        "buyer-human", "purchasing_manager", "The buyer's purchasing manager",
    )
    assert decided.rule_ids == ("F-01", "P-01") and requested.rule_ids == ("P-01", "P-03")
    assert decided.facts["approval_decision"]["roles"] == ["purchasing_manager"]
    assert requested.facts["approval"]["required_roles"] == ["purchasing_manager"]
    shown = " ".join(f"{event.sentence} {event.facts} {event.actor}" for event in supplier)
    assert [word for word in ("Maija", "Virtanen", "human:maija", "Weekly volume", "750") if word in shown] == []


def test_an_approval_that_leaves_a_role_missing_says_which_role_and_no_name(trail: AuditTrail, samples) -> None:
    roles = (ApproverRole.PURCHASING_MANAGER, ApproverRole.DIETITIAN)
    approval = samples.approval(ApprovalStatus.PENDING, (samples.approve(),), roles=roles)
    order = samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL)

    event = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija,
                         AuditContext(order=order, approval=approval, approval_decision=samples.approve()))

    assert event.data.supplier_sentence == (
        "The buyer's purchasing manager approved order ord_1. This approval accepts rules P-01 and P-03. "
        "The order still needs approval by the buyer's dietitian."
    )


def test_a_human_is_shown_by_the_roles_the_gateway_knows_and_by_nothing_else() -> None:
    def human(role: str | None) -> Actor:
        return Actor(kind=ActorKind.HUMAN, id="human:maija", role=role, display_name="Maija Virtanen")

    assert supplier_actor(human("purchasing_manager, finance")) == Actor(
        kind=ActorKind.HUMAN, id="buyer-human", role="purchasing_manager, finance",
        display_name="The buyer's purchasing manager, finance",
    )
    for role in (None, "Maija's own title"):
        assert supplier_actor(human(role)) == Actor(
            kind=ActorKind.HUMAN, id="buyer-human", display_name="A human at the buyer",
        )


def test_a_rule_that_asks_for_nobody_says_so_and_an_offer_that_left_nothing_out_adds_nothing(
    trail: AuditTrail, samples
) -> None:
    noted = samples.rule("P-07", "A deposit of €0.40 is not in the total.", verdict=Verdict.AUTO, role=None)
    option = samples.option("opt_1", (samples.line("464056", "200", "2.14"),), samples.decision(noted), "200")
    offer = samples.ward_offer().model_copy(update={"excluded": (), "options": (option,)})

    checked = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                           AuditContext(offer_id="off_2", option=option))
    built = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert checked.data.supplier_sentence == (
        "The buyer's rules were checked for option opt_1: the agent may place this order within its authority. "
        "Rule that applied: P-07, a rule the buyer set (rule P-07): no approval is needed. "
        "The strictest outcome among the rules that applied decides."
    )
    assert built.data.supplier_sentence.endswith(
        "covering the full quantity. No product was left out for a reason in Valio Aimo's own data. "
        f"{NOT_SHOWN_OR_COUNTED}"
    )
    assert built.data.supplier_facts["offer"]["left_out"] == []
