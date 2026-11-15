"""Review finding C3-F9: what the buyer gives up is said once, and the allergen data is read before the label.

Before, the sentence said the formula twice (spelled out as a reason of the verdict, then as the formula
sentence), and a rice drink whose allergen data says "free from soybeans" was called "not marked soy-free" for
want of the claim FREE_FROM_SOY.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.allergens import statement_for
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation
from tta.contracts.offer import SubstituteQuery
from tta.contracts.product import FormulaCheck, FormulaOutcome, Product
from tta.offers import OfferDeps, find_substitutes
from tta.offers.substitute_trade_off import FORMULA_IN_SHORT, FORMULA_REASON_PREFIX
from tta.offers.substitute_wording import replace_reasons
from tta.offers.substitutes import STATED_BY_ALLERGEN_DATA, claims_lost, claims_not_carried, replace_check
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
OAT_DRINK, RICE_DRINK = "470863", "473424"  # Oatly Oat Drink Semi (FREE_FROM_SOY, VEGAN) and Alpro Rice drink
BARISTA = "473609"


def _product(*claims: str, statements: tuple[tuple[str, AllergenRelation], ...] = ()) -> Product:
    return Product(
        id="1", category="10402", sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1),
        nutritional_claims=claims,
        allergen_statements=tuple(AllergenStatement(code=code, relation=relation) for code, relation in statements),
    )


@pytest.fixture(scope="module")
def demo_deps(deps_for: Callable[..., OfferDeps]) -> OfferDeps:
    return deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))


def test_the_rice_drink_whose_data_says_free_from_soy_has_not_lost_the_soy_free_claim(
    catalog: ProductCatalog,
) -> None:
    oat, rice = catalog.get_product(OAT_DRINK), catalog.get_product(RICE_DRINK)

    assert "FREE_FROM_SOY" in oat.nutritional_claims and "FREE_FROM_SOY" not in rice.nutritional_claims
    assert statement_for(rice.allergen_statements, "AY") is AllergenRelation.FREE_FROM
    assert claims_lost(oat, rice) == ()  # before: ("FREE_FROM_SOY",), said as "not marked soy-free"
    assert "FREE_FROM_SOY" not in claims_not_carried(oat, rice)


def test_only_an_explicit_free_from_statement_of_that_allergen_stands_for_the_claim() -> None:
    soy_free = _product("FREE_FROM_SOY")

    assert STATED_BY_ALLERGEN_DATA == {"FREE_FROM_SOY": "AY", "FREE_FROM_EGGS": "AE"}
    assert claims_lost(soy_free, _product(statements=(("AY", AllergenRelation.FREE_FROM),))) == ()
    # No statement, "may contain", "contains", not declared, or a statement about another allergen: lost.
    assert claims_lost(soy_free, _product()) == ("FREE_FROM_SOY",)
    for relation in (AllergenRelation.MAY_CONTAIN, AllergenRelation.CONTAINS, AllergenRelation.UNDECLARED):
        assert claims_lost(soy_free, _product(statements=(("AY", relation),))) == ("FREE_FROM_SOY",)
    assert claims_lost(soy_free, _product(statements=(("AE", AllergenRelation.FREE_FROM),))) == ("FREE_FROM_SOY",)
    # On conflicting statements the least safe one counts.
    both = (("AY", AllergenRelation.FREE_FROM), ("AY", AllergenRelation.MAY_CONTAIN))
    assert claims_lost(soy_free, _product(statements=both)) == ("FREE_FROM_SOY",)


def test_gluten_wheat_and_lactose_claims_are_never_read_from_the_allergen_data() -> None:
    # The claim promises more than "no such ingredient": the label stays the only proof.
    for claim, code in (("FREE_FROM_GLUTEN", "AW"), ("FREE_FROM_WHEAT", "UW"), ("FREE_FROM_LACTOSE", "ML")):
        stated = _product(statements=((code, AllergenRelation.FREE_FROM),))
        assert claims_lost(_product(claim), stated) == (claim,)


def test_what_is_given_up_says_the_formula_and_each_claim_once(demo_deps: OfferDeps, policy: Any) -> None:
    profile = policy.get_profile("hotel-kitchen")
    seen = 0
    for product_id in (BARISTA, "469363", "469346", "475703", "469890"):
        result = find_substitutes(product_id, profile, demo_deps, SubstituteQuery(quantity=Decimal(10)))
        for candidate in result.candidates:
            seen += 1
            text = candidate.gives_up
            assert text.count(candidate.formula.sentence) == 1
            assert FORMULA_REASON_PREFIX not in text  # the verdict no longer spells the formula out
            for claim in candidate.claims_lost:
                assert text.count(claim) == 1, (candidate.product_id, claim)
    assert seen > 30


def test_the_verdict_names_the_formula_in_short_as_the_check_words_its_reason() -> None:
    # `replace_reasons` (substitute_wording) starts the reason with the prefix this sentence shortens.
    original = Product(id="1", name_en="Kesä oat drink 1 l", brand="Kesä", category="10402", sales_unit="ST",
                       base_unit="ST", allowed_lot_size=Decimal(1))
    other = original.model_copy(update={"id": "2", "name_en": "Talvi oat drink 1 l", "brand": "Talvi"})
    formula = FormulaCheck(outcome=FormulaOutcome.DIFFERENT, sentence="Different contents.",
                           only_in_other=("rapeseed oil",))

    check = replace_check(original, other, formula)

    assert check.reasons == replace_reasons(check, formula, (), listed=False)
    assert check.reasons[0].startswith(FORMULA_REASON_PREFIX)
    assert FORMULA_REASON_PREFIX.rstrip(" (") == FORMULA_IN_SHORT
