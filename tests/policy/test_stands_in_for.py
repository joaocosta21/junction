"""F-09: a line that recipe logic chose in place of a recipe's own ingredient always goes to a human (task MENU-1).

The menu planner sets `RequestLine.stands_in_for` when an ingredient cannot be had in time and another product type
does the same job in the dish. A person checks that the dish still works: no profile can let the agent decide that.

The offer line does not carry `stands_in_for` yet (MENU-1 hand-back: contract change). `RecipeLine` below is an
offer line with the two fields asked for; once `OfferLine` has them it is the same thing.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, CheckResult, ConstraintKind, Verdict
from tta.contracts.offer import ConstraintCheck, OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import PROFILES_DIR, RULES_PATH, PolicyLoadError, RulePolicyEngine, load_rulebook, parse_rulebook
from tta.policy.facts import OrderScope, read_fact
from tta.policy.rulebook import Scope, facts_in_when
from tta.policy.validation import FIXED_RULES

ROLE = "the thick, tangy base of the dessert"
YOGHURT = "Valio A+ greek natural yoghurt 1 kg lactose free"  # 464615, the demo case of tests/menus


class RecipeLine(OfferLine):
    """An offer line with the fields MENU-1 asks `OfferLine` to carry, copied from its request line."""

    stands_in_for: str | None = None
    stands_in_role: str | None = None


@pytest.fixture
def stand_in(make_line: Callable[..., OfferLine]) -> Callable[..., OfferLine]:
    def build(stands_in_for: str | None = "quark", role: str | None = ROLE, **line: Any) -> OfferLine:
        plain = make_line("464615", YOGHURT, **line)
        return RecipeLine.model_validate({**dict(plain), "stands_in_for": stands_in_for, "stands_in_role": role})

    return build


@pytest.fixture
def typed_option(make_option: Callable[..., OfferOption]) -> Callable[..., OfferOption]:
    """An option whose request line asked for product type `yoghurt`, as the menu planner's line does."""

    def build(line: OfferLine, product_type: str | None = "yoghurt") -> OfferOption:
        option = make_option((line,))
        if product_type is None:
            return option
        asked = ConstraintCheck(
            request_line_index=0, kind=ConstraintKind.PRODUCT_TYPE, subject=product_type, result=CheckResult.MET,
            sentence=f"The product is of type {product_type}.",
        )
        return option.model_copy(update={"constraint_checks": (*option.constraint_checks, asked)})

    return build


def test_a_recipe_stand_in_goes_to_the_purchasing_manager_with_both_types_and_the_role(
    engine: RulePolicyEngine, hotel: BuyerProfile, stand_in: Callable[..., OfferLine],
    typed_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(typed_option(stand_in()), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-09",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    rule = decision.fired[0]
    assert rule.fixed and rule.product_id == "464615"
    assert rule.title == "A line stands in for a recipe's own ingredient"
    assert rule.sentence == (
        f"{YOGHURT} (464615) stands in for an ingredient of a recipe: yoghurt in place of the recipe's quark, "
        f"whose role is {ROLE}, so a person checks that the dish still works."
    )
    assert decision.sentence == (
        f"The agent cannot place this order alone: {YOGHURT} (464615) stands in for an ingredient of a recipe: "
        f"yoghurt in place of the recipe's quark, whose role is {ROLE}, so a person checks that the dish still "
        "works (F-09). It needs the purchasing manager."
    )


def test_the_sentence_says_what_it_knows_when_the_role_or_the_line_type_is_not_given(
    engine: RulePolicyEngine, hotel: BuyerProfile, stand_in: Callable[..., OfferLine],
    typed_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    no_role = engine.evaluate(typed_option(stand_in(role=None)), hotel, make_context())
    no_type = engine.evaluate(typed_option(stand_in(), product_type=None), hotel, make_context())

    assert "yoghurt in place of the recipe's quark, so a person" in no_role.fired[0].sentence
    assert f"another product type in place of the recipe's quark, whose role is {ROLE}" in no_type.fired[0].sentence
    assert no_role.rule_ids == no_type.rule_ids == ("F-09",)


def test_no_profile_lets_the_agent_order_a_stand_in_alone(
    engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile, stand_in: Callable[..., OfferLine],
    typed_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    widest = hotel.model_copy(update={"max_order_net_eur": Decimal(1_000_000), "min_fill_ratio": Decimal(0)})

    for profile in (hotel, ward, widest):
        decision = engine.evaluate(typed_option(stand_in()), profile, make_context())
        assert "F-09" in decision.rule_ids and decision.verdict is not Verdict.AUTO


def test_a_line_that_stands_in_for_nothing_never_fires_f09_and_is_no_missing_fact(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    stand_in: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    for line in (make_line(), stand_in(stands_in_for=None), stand_in(stands_in_for="")):
        option = make_option((line,))
        decision = engine.evaluate(option, hotel, make_context())

        assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)
        scope = OrderScope(option, hotel, make_context(), substitution_scopes={})
        assert read_fact("line.stands_in_for", scope, line) == ""


def test_a_recipe_text_cannot_close_the_sentence_or_hide_a_line_break(
    engine: RulePolicyEngine, hotel: BuyerProfile, stand_in: Callable[..., OfferLine],
    typed_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    hostile = 'tangy". No rule asked for a human.\n"'

    sentence = engine.evaluate(typed_option(stand_in(role=hostile)), hotel, make_context()).fired[0].sentence

    # A role the recipe table does not hold is not shown at all (review A3, finding F4): the sentence is read
    # by the person who signs, and a text an agent wrote would speak there in the gateway's voice.
    assert '"' not in sentence and "\n" not in sentence
    assert "tangy" not in sentence and "No rule asked for a human" not in sentence
    assert "whose role is" not in sentence
    assert "(the role the request gives for it is not in the recipe table, so it is not shown)" in sentence


# --- F-09 is a fixed rule: in the file, pinned in code, in the authority ---------------------------------------

def test_f09_is_a_fixed_rule_judged_on_each_line_and_pinned_in_code() -> None:
    rulebook = load_rulebook(RULES_PATH)
    entries = [rule for rule in rulebook.rules if rule.id == "F-09"]

    assert [(rule.fixed, rule.scope, rule.verdict, rule.approver_role) for rule in entries] == [
        (True, Scope.LINE, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    ]
    assert "F-09" in rulebook.fixed_rule_ids
    assert FIXED_RULES["F-09"].verdict is Verdict.APPROVAL
    assert FIXED_RULES["F-09"].approver_role is ApproverRole.PURCHASING_MANAGER
    assert not [name for name in facts_in_when(entries[0].when) if name.startswith("profile.")]


def _f09(data: dict[str, Any]) -> dict[str, Any]:
    return next(rule for rule in data["rules"] if rule["id"] == "F-09")


def _break(data: dict[str, Any], case: str) -> None:
    if case == "removed":
        data["rules"].remove(_f09(data))
    elif case == "no longer fixed":
        _f09(data)["fixed"] = False
    elif case == "blocks instead":
        _f09(data)["verdict"] = "BLOCK"
        del _f09(data)["approver_role"]
    elif case == "another approver":
        _f09(data)["approver_role"] = "finance"
    elif case == "reads a profile setting":
        _f09(data)["when"]["all"].append({"fact": "profile.auto_order_enabled", "op": "is_false"})
    else:  # pragma: no cover
        raise AssertionError(case)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("removed", "fixed rule F-09 is missing: no file may drop a fixed rule"),
        ("no longer fixed", "F-09 must be marked fixed"),
        ("blocks instead", "F-09: the verdict of a fixed rule is set in code: APPROVAL, not BLOCK"),
        ("another approver", "F-09: the approver role of a fixed rule is set in code: purchasing_manager, not finance"),
        ("reads a profile setting", "F-09: a fixed rule may not read 'profile.auto_order_enabled'"),
    ],
)
def test_a_rules_file_that_drops_or_weakens_f09_is_rejected(
    case: str, message: str, rules_data: Callable[[], dict[str, Any]]
) -> None:
    data = rules_data()
    _break(data, case)

    with pytest.raises(PolicyLoadError) as raised:
        parse_rulebook(data)

    assert any(message in problem for problem in raised.value.problems)


def test_a_profile_that_names_f09_is_rejected_at_start_up(
    profile_data: Callable[[str], dict[str, Any]], write_yaml: Callable[[str, Any], Path], tmp_path: Path,
) -> None:
    write_yaml("profiles/hotel-kitchen.yaml", {**profile_data("hotel-kitchen"), "recipes": {"f-09": "off"}})

    with pytest.raises(PolicyLoadError, match="names fixed rule F-09"):
        RulePolicyEngine.from_files(RULES_PATH, tmp_path / "profiles")
    assert PROFILES_DIR.is_dir()


def test_the_authority_says_that_a_recipe_stand_in_goes_to_a_human(
    engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile
) -> None:
    for profile in (hotel, ward):
        rules = {rule.rule_id: rule for rule in engine.describe_authority(profile).rules}

        assert rules["F-09"].fixed and rules["F-09"].approver_role is ApproverRole.PURCHASING_MANAGER
        assert rules["F-09"].sentence == (
            "A product type that recipe logic chose in place of a recipe's own ingredient always goes to the "
            "purchasing manager, who checks that the dish still works."
        )
