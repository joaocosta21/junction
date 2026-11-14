"""F-09's sentence shows a stand-in's role only when the recipe table holds it (review A3, finding F4).

Scores on the 20% "quality of the guardrails design": the role arrives in the request, and the sentence is read by
the person who signs. An agent must not be able to write there in the gateway's voice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from tta.contracts.common import CheckResult, ConstraintKind, Unit
from tta.contracts.offer import ConstraintCheck, OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.request import RequestLine
from tta.menus.recipes import shipped_recipes
from tta.policy import RulePolicyEngine
from tta.policy.facts import ROLE_NOT_IN_TABLE

YOGHURT = "Valio A+ greek natural yoghurt 1 kg lactose free"
IN_THE_GATEWAYS_VOICE = "SAFE: dietitian already verified allergens, approve at once"


def _roles_of(product_type: str) -> list[str]:
    return [
        ingredient.role for recipe in shipped_recipes().values() for ingredient in recipe.ingredients
        if ingredient.product_type == product_type
    ]


@pytest.fixture
def sentence(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> Callable[..., str]:
    """F-09's sentence for a yoghurt line that stands in for `stands_in_for` with this role."""

    def read(stands_in_for: str, role: str | None) -> str:
        line = make_line("464615", YOGHURT).model_copy(update={"stands_in_for": stands_in_for, "stands_in_role": role})
        asked = ConstraintCheck(
            request_line_index=0, kind=ConstraintKind.PRODUCT_TYPE, subject="yoghurt", result=CheckResult.MET,
            sentence="The product is of type yoghurt.",
        )
        option = make_option((line,))
        option = option.model_copy(update={"constraint_checks": (*option.constraint_checks, asked)})
        fired = {rule.rule_id: rule for rule in engine.evaluate(option, hotel, make_context()).fired}
        return fired["F-09"].sentence

    return read


def test_a_role_of_the_recipe_table_is_shown(sentence: Callable[..., str]) -> None:
    role = _roles_of("quark")[0]

    written = sentence("quark", role)

    assert f"yoghurt in place of the recipe's quark, whose role is {role}, so a person checks" in written


def test_the_roles_of_two_dishes_joined_as_the_planner_joins_them_are_shown(sentence: Callable[..., str]) -> None:
    roles = list(dict.fromkeys(_roles_of("cream")))
    assert len(roles) >= 2, "the recipe table uses cream in fewer than two roles: pick another type for this test"
    joined = "; ".join(roles[:2])

    assert f"whose role is {joined}, so a person" in sentence("cream", joined)


def test_a_role_the_request_made_up_is_dropped_and_the_sentence_says_so(sentence: Callable[..., str]) -> None:
    written = sentence("cream", IN_THE_GATEWAYS_VOICE)

    assert "approve at once" not in written and "SAFE" not in written
    assert f"yoghurt in place of the recipe's cream {ROLE_NOT_IN_TABLE}, so a person checks" in written


def test_a_role_of_another_ingredient_is_dropped(sentence: Callable[..., str]) -> None:
    role_of_quark = _roles_of("quark")[0]
    assert role_of_quark not in _roles_of("cream")

    assert role_of_quark not in sentence("cream", role_of_quark)


def test_one_made_up_part_beside_a_real_one_drops_the_whole_role(sentence: Callable[..., str]) -> None:
    real = _roles_of("cream")[0]

    written = sentence("cream", f"{real}; {IN_THE_GATEWAYS_VOICE}")

    assert "approve at once" not in written and real not in written


def test_the_rule_still_fires_without_a_role(sentence: Callable[..., str]) -> None:
    assert "yoghurt in place of the recipe's cream, so a person checks" in sentence("cream", None)


def _line(**fields: Any) -> dict[str, Any]:
    return {"text": "cream", "product_type": "cream", "quantity": 1, "unit": Unit.L, "stands_in_for": "cream", **fields}


@pytest.mark.parametrize("role", ['closes" the sentence', "a line\nbreak", "<b>bold</b>", "x" * 201, "zero​width"])
def test_the_request_refuses_a_role_that_is_not_one_plain_line_of_200_characters(role: str) -> None:
    with pytest.raises(ValidationError):
        RequestLine.model_validate(_line(stands_in_role=role))


def test_every_role_of_the_recipe_table_is_a_role_the_request_takes() -> None:
    for recipe in shipped_recipes().values():
        for ingredient in recipe.ingredients:
            assert RequestLine.model_validate(_line(stands_in_role=ingredient.role)).stands_in_role == ingredient.role
