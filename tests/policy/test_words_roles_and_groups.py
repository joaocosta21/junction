"""The owner's critique of the rules, 14 Nov 2026: words a person reads, who signs, and the five ideas.

* A sentence names an allergen in words and the customer by its name: never a code, "this buyer" or "this
  profile". The codes stay in the facts written next to the sentence.
* A lost dietary claim (F-08) goes to the dietitian where the customer names one; the roles a fixed rule may ask
  are pinned in code, like its verdict.
* Every fixed rule belongs to exactly one of five plain statements (`tta.policy.rule_groups`).
* F-05 stays a block for every customer ("still need to be overly cautious with the allergens").
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

from tta.allergens.codes import ALLERGEN_CODES
from tta.contracts.common import AllergenRelation, ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.offers.substitutes import DIETARY_CLAIMS
from tta.policy import RULES_PATH, PolicyLoadError, RulePolicyEngine, load_rulebook, parse_rulebook, rule_groups
from tta.policy.allergen_words import CLAIM_WORDS, allergen_words, claim_words
from tta.policy.groups import groups_of
from tta.policy.human_approval import AUTHORITY_OFF, AUTHORITY_ON
from tta.policy.validation import FIXED_RULES, RULE_GROUPS

NOT_A_PERSONS_WORDS = ("this buyer", "this profile", "the buyer's", "STRICT", "DECLARED_ONLY")
A_CODE = re.compile(r"\b(?:" + "|".join(sorted(ALLERGEN_CODES)) + r")\b")


# --- words -----------------------------------------------------------------------------------------------------

def test_allergens_and_claims_are_said_in_words() -> None:
    assert allergen_words(["AN", "AP", "AS"]) == "tree nuts, peanuts and sesame seeds"
    assert allergen_words(["AM"]) == "milk" and allergen_words([]) == "no allergen"
    # A code the table does not hold has no word: it is not hidden.
    assert allergen_words(["ZZ"]) == "an allergen the catalog's table does not name (ZZ)"
    assert claim_words(["FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN"]) == "lactose-free and gluten-free"
    assert set(CLAIM_WORDS) == set(DIETARY_CLAIMS)  # every claim the offer lists as lost has its word


def test_no_text_of_the_rules_file_calls_the_customer_this_buyer_or_names_an_allergen_by_its_code() -> None:
    rulebook = load_rulebook(RULES_PATH)
    texts = [rule.message for rule in rulebook.rules]
    texts += [text.text for rule in rulebook.rules for text in rule.authority]
    texts += [rule.title for rule in rulebook.rules] + [text.text for text in rulebook.authority.summary]
    texts += [*rulebook.decision_sentences.values(), *rulebook.groups.values(), AUTHORITY_OFF, AUTHORITY_ON]
    texts += [rule.text for rule in rulebook.access_rules]

    for text in texts:
        assert not [word for word in NOT_A_PERSONS_WORDS if word in text], text
    # The list facts hold codes ("AN (contains)"): a sentence reads the *_said fact, the list goes in `records`.
    code_facts = (
        "profile.excluded_allergens}", "profile.strict_allergens}", "profile.declared_only_allergens}",
        "line.allergens_declared}", "line.allergens_to_human}", "line.substitute_added_allergens}",
        "line.substitute_claims_lost}",
    )
    for text in texts:
        assert not [fact for fact in code_facts if "{" + fact in text], text


@pytest.mark.parametrize("profile_id", ["hotel-kitchen", "school-kitchen", "allergy-ward", "bakery-cafe"])
def test_the_authority_of_every_customer_reads_without_a_code(engine: RulePolicyEngine, profile_id: str) -> None:
    authority = engine.describe_authority(engine.get_profile(profile_id))

    for sentence in (*(rule.sentence for rule in authority.rules), *authority.summary):
        assert not A_CODE.search(sentence), sentence
        assert not [word for word in NOT_A_PERSONS_WORDS if word in sentence], sentence
    said = {rule.rule_id: rule.sentence for rule in authority.rules}
    name = authority.profile.display_name
    assert said["F-10"].startswith(f"The agent prepares the order, a person confirms it: {name}")


def test_the_school_reads_its_allergens_in_words(engine: RulePolicyEngine) -> None:
    school = engine.describe_authority(engine.get_profile("school-kitchen"))
    said = {rule.rule_id: rule.sentence for rule in school.rules}

    assert said["F-02"] == (
        "Kilo School excludes tree nuts, peanuts and sesame seeds. A product that contains one of them can never be "
        "ordered, even with approval."
    )
    assert said["P-04"] == (
        "Kilo School excludes tree nuts, peanuts and sesame seeds, and each must be confirmed absent: a product that "
        "may contain one, leaves it undeclared or says nothing about it goes to the dietitian."
    )


def test_a_member_of_an_excluded_family_is_named_with_the_family(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], make_allergen_check: Callable,
) -> None:
    """The ward excludes cereals containing gluten; the product declares wheat."""
    from tta.allergens import check_exclusions
    from tta.contracts.allergen import AllergenStatement
    from tta.contracts.common import AllergenStrictness

    statements = (
        AllergenStatement(code="UW", relation=AllergenRelation.CONTAINS),
        AllergenStatement(code="AM", relation=AllergenRelation.FREE_FROM),
    )
    check = check_exclusions(statements, ("AM", "AW"), AllergenStrictness.STRICT)

    line = make_line("400010", "Wheat roll", allergen_check=check)
    decision = engine.evaluate(make_option((line,)), ward, make_context())

    f02 = next(rule for rule in decision.fired if rule.rule_id == "F-02")
    assert decision.verdict is Verdict.BLOCK
    assert f02.sentence == (
        "Wheat roll (400010) contains wheat (counted under cereals containing gluten), which is excluded for City "
        "Hospital, Ward 4, so it cannot be ordered."
    )
    assert f02.facts["line.allergens_declared"] == ["AW (contains, stated for UW)"]  # the codes, for the auditor


# --- F-05 stays a block ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("profile_id", ["hotel-kitchen", "school-kitchen", "allergy-ward", "bakery-cafe"])
@pytest.mark.parametrize("alone", [False, True])
def test_a_substitute_that_adds_an_allergen_is_blocked_for_every_customer_whatever_it_sets(
    profile_id: str, alone: bool, engine: RulePolicyEngine, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_substitute: Callable[..., SubstituteInfo], make_allergen_check: Callable,
) -> None:
    profile = engine.get_profile(profile_id).model_copy(update={"auto_order_enabled": alone})
    clean = make_allergen_check(dict.fromkeys(profile.excluded_allergens, AllergenRelation.FREE_FROM))
    adds = make_substitute(added=(("AE", AllergenRelation.MAY_CONTAIN),))  # eggs: no shipped customer excludes them
    check = clean if profile.excluded_allergens else None
    line = make_line("471881", "Oat drink", substitute=adds, allergen_check=check)

    decision = engine.evaluate(make_option((line,)), profile, make_context())

    f05 = next(rule for rule in decision.fired if rule.rule_id == "F-05")
    assert decision.verdict is Verdict.BLOCK and decision.required_roles == ()
    assert f05.verdict is Verdict.BLOCK and f05.approver_role is None and f05.fixed
    assert f05.sentence == (
        "Oat drink (471881) would replace Oddlygood Barista oat drink (473609) and declares that it may contain "
        "eggs, which the product asked for does not, so it cannot be ordered as a substitute. Ask for it by name if "
        "you want it."
    )
    assert FIXED_RULES["F-05"].verdict is Verdict.BLOCK and FIXED_RULES["F-05"].other_roles == ()


def test_a_rules_file_that_lets_a_person_approve_an_added_allergen_does_not_load(
    rules_data: Callable[[], dict[str, Any]]
) -> None:
    data = rules_data()
    f05 = next(rule for rule in data["rules"] if rule["id"] == "F-05")
    f05.update({"verdict": "APPROVAL", "approver_role": "dietitian"})

    with pytest.raises(PolicyLoadError) as error:
        parse_rulebook(data)

    assert "F-05: the verdict of a fixed rule is set in code: BLOCK, not APPROVAL" in str(error.value)


# --- who signs ---------------------------------------------------------------------------------------------------

def test_the_roles_a_fixed_rule_may_ask_are_pinned_in_code(rules_data: Callable[[], dict[str, Any]]) -> None:
    """F-08 may ask the dietitian and nobody else; no other fixed rule may name another role."""
    to_dietitian = [{"when": {"all": [{"fact": "profile.names_dietitian", "op": "is_true"}]}, "role": "dietitian"}]
    to_finance = [{"when": {"all": [{"fact": "profile.names_dietitian", "op": "is_true"}]}, "role": "finance"}]
    cases = {
        ("F-08", None): "F-08: the other roles a fixed rule may ask are set in code: dietitian, not none",
        ("F-08", "finance"): "F-08: the other roles a fixed rule may ask are set in code: dietitian, not finance",
        ("F-01", "dietitian"): "F-01: the other roles a fixed rule may ask are set in code: none, not dietitian",
    }
    for (rule_id, role), problem in cases.items():
        data = rules_data()
        rule = next(rule for rule in data["rules"] if rule["id"] == rule_id)
        rule.pop("approver_role_when", None)
        if role is not None:
            rule["approver_role_when"] = to_finance if role == "finance" else to_dietitian

        with pytest.raises(PolicyLoadError) as error:
            parse_rulebook(data)

        assert problem in str(error.value)


def test_another_role_is_named_only_by_a_rule_that_asks_for_a_person_and_reads_declared_facts(
    rules_data: Callable[[], dict[str, Any]]
) -> None:
    data = rules_data()
    rules = {rule["id"]: rule for rule in data["rules"] if rule["id"] != "F-07"}
    rules["P-01"]["approver_role_when"] = [
        {"when": {"all": [{"fact": "line.has_deposits", "op": "is_true"}]}, "role": "finance"},
        {"when": {"all": [{"fact": "profile.no_such_fact", "op": "is_true"}]}, "role": "finance"},
    ]

    with pytest.raises(PolicyLoadError) as error:
        parse_rulebook(data)

    assert "P-01: an order rule cannot read the line fact 'line.has_deposits'" in str(error.value)
    assert "P-01: approver_role_when: undeclared fact 'profile.no_such_fact'" in str(error.value)


def test_a_profile_rule_may_name_another_role_and_the_first_entry_that_holds_signs(
    engine: RulePolicyEngine, hotel: BuyerProfile, rules_data: Callable[[], dict[str, Any]],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    data = rules_data()
    p01 = next(rule for rule in data["rules"] if rule["id"] == "P-01")
    p01["approver_role_when"] = [
        {"when": {"all": [{"fact": "profile.names_dietitian", "op": "is_false"}]}, "role": "dietitian"},
        {"when": {"all": [{"fact": "option.net_eur", "op": "gt", "value": 1000}]}, "role": "finance"},
    ]
    changed = RulePolicyEngine(parse_rulebook(data), [hotel])

    small = changed.evaluate(make_option(net="800.00"), hotel, make_context())
    large = changed.evaluate(make_option(net="1200.00"), hotel, make_context())

    assert small.required_roles == (ApproverRole.PURCHASING_MANAGER,)  # no entry holds: the rule's own role
    assert large.required_roles == (ApproverRole.FINANCE,)
    assert large.fired[0].facts["profile.names_dietitian"] is True  # what decided who signs is written down


def test_the_allergen_questions_go_to_the_dietitian(engine: RulePolicyEngine) -> None:
    """P-04 as before, the missing allergen check as before, and now F-08. A block has nobody to ask."""
    rulebook = load_rulebook(RULES_PATH)
    by_id = {rule.id: rule for rule in rulebook.rules}

    assert by_id["P-04"].approver_role is ApproverRole.DIETITIAN and not by_id["P-04"].approver_role_when
    assert rulebook.facts["line.allergen_outcomes"].missing_role is ApproverRole.DIETITIAN
    assert [entry.role for entry in by_id["F-08"].approver_role_when] == [ApproverRole.DIETITIAN]
    assert by_id["F-02"].approver_role is None and by_id["F-05"].approver_role is None
    assert "dietary claim" in rulebook.roles[ApproverRole.DIETITIAN].decides


# --- the five ideas ----------------------------------------------------------------------------------------------

def test_the_fixed_rules_are_five_plain_statements() -> None:
    groups = rule_groups()

    assert [(group.statement, group.rule_ids) for group in groups] == [
        ("An allergen you exclude is never ordered.", ("F-02",)),
        ("Anything Valio Aimo's data does not confirm goes to a person.", ("F-01", "F-03", "F-07")),
        ("A substitute that is not a like-for-like replacement goes to a person.",
         ("F-05", "F-08", "F-09", "F-11", "F-12")),
        ("An offer that is out of date cannot be ordered.", ("F-04",)),
        ("The agent never approves.", ("F-06",)),
    ]
    assert tuple(group.key for group in groups) == RULE_GROUPS


def test_every_fixed_rule_belongs_to_exactly_one_group() -> None:
    rulebook = load_rulebook(RULES_PATH)
    grouped = [rule_id for group in groups_of(rulebook) for rule_id in group.rule_ids]

    assert sorted(grouped) == sorted(rulebook.fixed_rule_ids)  # each once, none left out
    assert set(FIXED_RULES) | {"F-06"} == set(grouped)
    assert all(rule.group is None for rule in rulebook.rules if not rule.fixed)


def test_a_rules_file_whose_fixed_rule_has_no_group_or_an_unknown_one_does_not_load(
    rules_data: Callable[[], dict[str, Any]]
) -> None:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "F-01: a fixed rule belongs to one group, and it names none": lambda rules: rules["F-01"].pop("group"),
        "F-06: a fixed rule belongs to one group, and it names none": lambda rules: rules["F-06"].pop("group"),
        "F-04: unknown group 'safety'": lambda rules: rules["F-04"].update(group="safety"),
        "groups.out_of_date_offer: no fixed rule belongs to it": lambda rules: rules["F-04"].update(
            group="unconfirmed_goes_to_a_person"
        ),
        "P-01: a profile rule names no group; the groups are the fixed rules": lambda rules: rules["P-01"].update(
            group="out_of_date_offer"
        ),
    }
    for problem, change in cases.items():
        data = rules_data()
        change({rule["id"]: rule for rule in (*data["rules"], *data["access_rules"]) if rule["id"] != "F-07"})

        with pytest.raises(PolicyLoadError) as error:
            parse_rulebook(data)

        assert problem in str(error.value), problem


def test_the_two_entries_of_one_rule_name_the_same_group_and_the_five_keys_are_pinned(
    rules_data: Callable[[], dict[str, Any]]
) -> None:
    split = rules_data()
    next(rule for rule in split["rules"] if rule["id"] == "F-07")["group"] = "out_of_date_offer"
    sixth = rules_data()
    sixth["groups"]["spend"] = "Spend stays within your limits."

    for data, problem in (
        (split, "F-07: the entries of one rule must name the same group"),
        (sixth, "groups must be exactly, in this order: excluded_allergen_never_ordered"),
    ):
        with pytest.raises(PolicyLoadError) as error:
            parse_rulebook(data)

        assert problem in str(error.value)
