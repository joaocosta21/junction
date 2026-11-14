"""One allergen rule per excluded allergen (`allergen_strictness_by_code`).

Scores on the 20% "autonomy and controls" and the 20% "precisely matches what the buyer asked": a kitchen keeps
peanuts out as an allergy that must be confirmed (STRICT) and sesame out as an ingredient (DECLARED_ONLY), and
the same product with no statement about either goes to the dietitian for the first and passes, shown as
unverified, for the second. A request can make an allergen's rule stricter and never weaker.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from tta.allergens import check_exclusions
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenOutcome, AllergenStrictness, Unit
from tta.contracts.policy import BuyerProfile
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import allergen_rules, need_for
from tta.policy import RulePolicyEngine

STRICT = AllergenStrictness.STRICT
DECLARED_ONLY = AllergenStrictness.DECLARED_ONLY

Build = Callable[..., tuple[AllergenStatement, ...]]


def _profile(**change: Any) -> BuyerProfile:
    data: dict[str, Any] = {
        "profile_id": "test-kitchen",
        "display_name": "Test kitchen",
        "auto_order_enabled": True,
        "max_order_net_eur": 500,
        "max_daily_net_eur": 1000,
        "min_fill_ratio": 1,
        "excluded_allergens": ("AP", "AS"),
        "allergen_strictness": DECLARED_ONLY,
        "allergen_strictness_by_code": {"AP": STRICT},
        "substitution_without_approval": "NONE",
        "variable_weight": "APPROVAL",
        "deposits": "APPROVAL",
    }
    return BuyerProfile.model_validate({**data, **change})


def test_each_allergen_is_checked_under_its_own_rule(statements: Build) -> None:
    silent = statements()  # says nothing about peanuts or sesame

    check = check_exclusions(silent, ["AP", "AS"], DECLARED_ONLY, by_code={"AP": STRICT})

    by_code = {finding.excluded_code: finding for finding in check.findings}
    assert (by_code["AP"].outcome, by_code["AP"].strictness) == (AllergenOutcome.TO_HUMAN, STRICT)
    assert (by_code["AS"].outcome, by_code["AS"].strictness) == (AllergenOutcome.PASS, DECLARED_ONLY)
    assert check.outcome is AllergenOutcome.TO_HUMAN
    assert check.strictness is STRICT  # the strictest rule any allergen was checked under


def test_with_a_rule_for_every_allergen_no_general_rule_is_needed(statements: Build) -> None:
    check = check_exclusions(statements(), ["AS"], None, by_code={"AS": DECLARED_ONLY})
    assert check.outcome is AllergenOutcome.PASS


def test_an_allergen_with_no_rule_at_all_reads_strict(statements: Build) -> None:
    """Review P4, item M3: an exclusion nobody gave a rule for gets the safe one."""
    check = check_exclusions(statements(), ["AP", "AS"], None, by_code={"AP": DECLARED_ONLY})

    by_code = {finding.excluded_code: finding for finding in check.findings}
    assert (by_code["AP"].outcome, by_code["AP"].strictness) == (AllergenOutcome.PASS, DECLARED_ONLY)
    assert (by_code["AS"].outcome, by_code["AS"].strictness) == (AllergenOutcome.TO_HUMAN, STRICT)


def test_a_declared_allergen_is_rejected_under_either_rule(statements: Build) -> None:
    contains = statements(("AS", "CONTAINS"))
    check = check_exclusions(contains, ["AS"], STRICT, by_code={"AS": DECLARED_ONLY})
    assert check.outcome is AllergenOutcome.REJECT


def test_the_profile_gives_each_excluded_allergen_its_rule() -> None:
    profile = _profile()

    assert profile.strictness_for("AP") is STRICT
    assert profile.strictness_for("AS") is DECLARED_ONLY
    assert profile.codes_under(STRICT) == ("AP",)
    assert profile.codes_under(DECLARED_ONLY) == ("AS",)


def test_a_rule_for_an_allergen_the_profile_does_not_exclude_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not exclude: AM"):
        _profile(allergen_strictness_by_code={"AM": STRICT})


def test_a_request_can_make_an_allergens_rule_stricter_never_weaker() -> None:
    profile = _profile()

    assert allergen_rules(profile, ("AP", "AS"), STRICT) == {"AP": STRICT, "AS": STRICT}
    assert allergen_rules(profile, ("AP", "AS"), DECLARED_ONLY) == {"AP": STRICT, "AS": DECLARED_ONLY}


def test_a_request_line_carries_the_rule_of_each_allergen() -> None:
    line = RequestLine(
        text="milk",
        product_type="milk",
        quantity=Decimal(10),
        unit=Unit.L,
        exclude_allergens=("AE",),
        allergen_strictness=DECLARED_ONLY,
    )
    request = PurchaseRequest(needed_by=date(2026, 11, 16), lines=(line,))

    need = need_for(0, line, request, _profile())

    assert need.excluded == ("AP", "AS", "AE")
    assert dict(need.strictness_by_code) == {"AP": STRICT, "AS": DECLARED_ONLY, "AE": DECLARED_ONLY}
    assert need.strictness is STRICT


def test_the_authority_names_the_allergens_under_each_rule() -> None:
    authority = RulePolicyEngine.from_files().describe_authority(_profile())

    sentence = next(rule.sentence for rule in authority.rules if rule.rule_id == "P-04")
    assert "under rule STRICT: AP" in sentence
    assert "Under rule DECLARED_ONLY: AS" in sentence
