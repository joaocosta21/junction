"""The policy hash: SHA-256 of the canonical rules plus the profile in force."""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.contracts.policy import BuyerProfile
from tta.policy import PROFILES_DIR, RULES_PATH, RulePolicyEngine

HASH_FORMAT = re.compile(r"sha256:[0-9a-f]{64}")


def test_the_hash_is_a_labelled_sha256(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    assert HASH_FORMAT.fullmatch(engine.policy_hash(hotel))


def test_the_hash_is_stable_across_runs(engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile) -> None:
    again = RulePolicyEngine.from_files()

    assert again.policy_hash(again.get_profile("hotel-kitchen")) == engine.policy_hash(hotel)
    assert again.policy_hash(again.get_profile("allergy-ward")) == engine.policy_hash(ward)
    assert engine.policy_hash(hotel) == engine.policy_hash(hotel)


def test_each_profile_has_its_own_hash(engine: RulePolicyEngine, hotel: BuyerProfile, ward: BuyerProfile) -> None:
    assert engine.policy_hash(hotel) != engine.policy_hash(ward)


def test_the_hash_changes_when_a_limit_changes(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    raised = hotel.model_copy(update={"max_order_net_eur": Decimal(751)})
    lowered_fill = hotel.model_copy(update={"min_fill_ratio": Decimal("0.89")})

    assert engine.policy_hash(raised) != engine.policy_hash(hotel)
    assert engine.policy_hash(lowered_fill) != engine.policy_hash(hotel)


def test_the_hash_ignores_how_a_number_is_written(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    same_value = hotel.model_copy(update={"max_order_net_eur": Decimal("750.00")})

    assert engine.policy_hash(same_value) == engine.policy_hash(hotel)


def test_the_hash_ignores_key_order_and_comments_but_not_content(
    engine: RulePolicyEngine, hotel: BuyerProfile, rules_data: Callable[[], dict[str, Any]],
    write_yaml: Callable[[str, Any], Path],
) -> None:
    data = rules_data()
    reordered = write_yaml("reordered.yaml", dict(reversed(list(data.items()))))
    changed_data = rules_data()
    changed_data["rules"][0]["message"] += " today"
    changed = write_yaml("changed.yaml", changed_data)

    same = RulePolicyEngine.from_files(reordered, PROFILES_DIR)
    different = RulePolicyEngine.from_files(changed, PROFILES_DIR)

    assert RULES_PATH.read_text(encoding="utf-8").lstrip().startswith("#")  # the shipped file carries comments
    assert same.policy_hash(hotel) == engine.policy_hash(hotel)
    assert different.policy_hash(hotel) != engine.policy_hash(hotel)


def test_every_decision_carries_the_hash_of_the_policy_in_force(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable, make_context: Callable,
) -> None:
    stricter = hotel.model_copy(update={"max_order_net_eur": Decimal(50)})

    first = engine.evaluate(make_option(), hotel, make_context())
    second = engine.evaluate(make_option(), stricter, make_context())

    assert first.policy_hash == engine.policy_hash(hotel)
    assert second.policy_hash == engine.policy_hash(stricter) != first.policy_hash


@pytest.mark.parametrize("scope", ["line", "order"])
def test_the_hash_covers_both_parts_of_f07(
    scope: str, engine: RulePolicyEngine, hotel: BuyerProfile, rules_data: Callable[[], dict[str, Any]],
    write_yaml: Callable[[str, Any], Path],
) -> None:
    data = rules_data()
    part = next(rule for rule in data["rules"] if rule["id"] == "F-07" and rule["scope"] == scope)
    part["justification"] += " Reworded."

    reworded = RulePolicyEngine.from_files(write_yaml("reworded.yaml", data), PROFILES_DIR)

    assert reworded.policy_hash(hotel) != engine.policy_hash(hotel)
