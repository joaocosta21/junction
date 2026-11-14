"""How single facts are read and written: allergen families, substitutes, numbers in a decision."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.allergen import AllergenCheck, AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine
from tta.policy.facts import Missing, read_fact, read_profile_fact
from tta.policy.rulebook import FactType
from tta.policy.sentences import format_fact, to_json
from tta.policy.text import as_sentence, format_limit, format_money, format_number, format_ratio, join_words


def test_a_finding_about_a_family_member_names_the_code_it_was_stated_for(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    findings = (
        AllergenFinding(excluded_code="AM", relation=AllergenRelation.FREE_FROM, outcome=AllergenOutcome.PASS,
                        sentence="Free from milk."),
        AllergenFinding(excluded_code="AW", relation=AllergenRelation.CONTAINS, matched_code="GO",
                        outcome=AllergenOutcome.TO_HUMAN, sentence="Declares oats; a no-gluten buyer needs a human."),
    )
    check = AllergenCheck(outcome=AllergenOutcome.TO_HUMAN, strictness=AllergenStrictness.STRICT,
                          findings=findings, all_explicit=True)
    option = make_option((make_line("473609", "Oat drink gluten-free", allergen_check=check),))

    decision = engine.evaluate(option, ward, make_context())

    # SPEC section 6: declared oats under a "no gluten" exclusion go to a human; the policy does not
    # turn the CONTAINS relation into a block of its own.
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-04",)
    assert decision.fired[0].facts["line.allergens_to_human"] == ["AW (contains, stated for GO)"]
    assert decision.fired[0].facts["line.allergen_outcomes"] == ["TO_HUMAN", "PASS"]


def test_a_check_that_rejects_without_saying_which_allergen_still_blocks(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    check = AllergenCheck(outcome=AllergenOutcome.REJECT, strictness=AllergenStrictness.STRICT, all_explicit=False)

    decision = engine.evaluate(make_option((make_line(allergen_check=check),)), hotel, make_context())

    assert decision.verdict is Verdict.BLOCK
    assert decision.fired[0].sentence.endswith("declares an allergen this buyer excludes: not listed.")


def test_a_substitute_whose_original_has_no_name_is_named_by_its_id(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_substitute: Callable,
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    substitute = make_substitute().model_copy(update={"original_name": None})
    option = make_option((make_line("471690", "Oat drink", substitute=substitute, allergen_check=check),))

    decision = engine.evaluate(option, ward, make_context())

    assert decision.rule_ids == ("P-05",)
    assert decision.fired[0].sentence == (
        "Oat drink (471690) replaces 473609, a substitute that profile allergy-ward does not accept without a human."
    )
    assert decision.fired[0].facts["line.substitute_scope"] == "LISTED_BY_SUPPLIER"
    assert decision.fired[0].facts["profile.substitution_scopes_allowed"] == []
    assert decision.fired[0].facts["profile.substitution_without_approval"] == "NONE"


def test_f05_follows_the_verdict_of_the_substitution_rule_and_lists_what_it_found(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_substitute: Callable,
) -> None:
    failing = make_substitute(added=(("AW", AllergenRelation.MAY_CONTAIN),))
    passing = failing.model_copy(update={
        "allergen_check": failing.allergen_check.model_copy(update={"passes": True}),
    })

    blocked = engine.evaluate(make_option((make_line(substitute=failing),)), hotel, make_context())
    allowed = engine.evaluate(make_option((make_line(substitute=passing),)), hotel, make_context())

    assert blocked.verdict is Verdict.BLOCK and blocked.rule_ids == ("F-05",)
    assert blocked.fired[0].facts["line.substitute_added_allergens"] == ["AW (may contain)"]
    assert allowed.verdict is Verdict.AUTO


def test_facts_about_a_substitute_are_missing_on_a_line_that_replaces_nothing(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    from tta.policy.facts import OrderScope

    line = make_line()
    scope = OrderScope(make_option((line,)), hotel, make_context(), {})

    assert isinstance(read_fact("line.substitute_scope", scope, line), Missing)
    assert isinstance(read_fact("line.substitute_original", scope, line), Missing)
    assert read_fact("line.substitute_added_allergens", scope, line) == ()
    assert read_fact("line.substitute_adds_allergen", scope, line) is False
    assert isinstance(read_fact("line.name", scope), Missing)  # a line fact without a line is never guessed
    assert isinstance(read_fact("order.stale_reason", scope), Missing)
    assert isinstance(read_fact("no.such_fact", scope), Missing)


def test_profile_facts_can_be_read_without_an_option(hotel: BuyerProfile, ward: BuyerProfile) -> None:
    assert read_profile_fact("profile.max_order_net_eur", hotel, {}) == Decimal(750)
    assert read_profile_fact("profile.allergen_strictness", ward, {}) == "STRICT"
    assert isinstance(read_profile_fact("profile.allergen_strictness", hotel, {}), Missing)
    assert isinstance(read_profile_fact("option.net_eur", hotel, {}), Missing)


def test_numbers_read_as_people_write_them() -> None:
    assert format_money(Decimal("1980.770")) == "1,980.77" and format_money(Decimal(428)) == "428.00"
    assert format_limit(Decimal(750)) == "750" and format_limit(Decimal("1500.00")) == "1,500"
    assert format_limit(Decimal("750.5")) == "750.50"
    assert format_ratio(Decimal("0.749")) == "74.9%" and format_ratio(Decimal("0.9")) == "90%"
    assert format_ratio(Decimal(1)) == "100%" and format_ratio(Decimal(0)) == "0%"
    assert format_number(Decimal("1000")) == "1,000" and format_number(Decimal("12.50")) == "12.5"


def test_words_join_and_clauses_become_sentences() -> None:
    assert join_words([]) == "" and join_words(["a"]) == "a"
    assert join_words(["a", "b"]) == "a and b" and join_words(["a", "b", "c"]) == "a, b and c"
    assert as_sentence("the total is high") == "The total is high."
    assert as_sentence("Already a sentence.") == "Already a sentence." and as_sentence("  ") == ""


def test_facts_are_written_to_a_decision_as_plain_json_values() -> None:
    assert to_json(Decimal("1980.774"), FactType.MONEY) == 1980.77
    assert to_json(Decimal("0.74949"), FactType.RATIO) == 0.7495
    assert to_json(Decimal("698"), FactType.NUMBER) == 698.0
    assert to_json(("AM", "AW"), FactType.LIST) == ["AM", "AW"]
    assert to_json(Missing("not given"), FactType.BOOL) is None
    assert to_json(Missing("partly", known=("REJECT",)), FactType.LIST) == ["REJECT"]
    assert format_fact(Missing("not given"), FactType.MONEY) == "not known"
    assert format_fact(True, FactType.BOOL) == "yes" and format_fact(False, FactType.BOOL) == "no"
    assert format_fact((), FactType.LIST) == "not listed"


@pytest.mark.parametrize(
    ("ratio", "text"),
    [
        ("0.9996", "99.9%"), ("0.99999", "99.9%"), ("0.9995", "99.9%"), ("0.999", "99.9%"), ("0.99", "99%"),
        ("0.8999", "89.9%"), ("0.7495", "74.9%"), ("0.749", "74.9%"), ("0.9", "90%"), ("0.5", "50%"),
        ("1", "100%"), ("1.0000", "100%"), ("0", "0%"),
    ],
)
def test_a_ratio_is_rounded_down_so_that_one_below_1_never_prints_as_100_percent(ratio: str, text: str) -> None:
    assert format_ratio(Decimal(ratio)) == text


def test_p03_never_says_that_100_percent_is_below_the_100_percent_minimum(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    option = make_option((make_line(allergen_check=check),), fill_ratio="0.9996")

    decision = engine.evaluate(option, ward, make_context())

    assert decision.rule_ids == ("P-03",)
    assert decision.fired[0].sentence == "Only 99.9% of the requested quantity is covered, below the 100% minimum."
