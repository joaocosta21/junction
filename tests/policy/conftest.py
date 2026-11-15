"""Builders for the policy tests: offer lines, options, order contexts and the engine over the shipped files.

Every builder is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from tta.allergens import check_exclusions
from tta.contracts.allergen import AllergenCheck, AllergenStatement, SubstituteAllergenCheck
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck, RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    DataSource,
    OptionKind,
    PackSizeSource,
    Unit,
    round_money,
)
from tta.contracts.offer import ConstraintCheck, Coverage, OfferLine, OfferOption, SubstituteInfo, Totals
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import PackSize, ReplaceCheck, ReplaceVerdict
from tta.policy import PROFILES_DIR, RULES_PATH, RulePolicyEngine

# Server time of the demo capture: Saturday 14 Nov 2026, 02:52 (AIMO/build/AGENT-RULES.md).
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))
# The Monday after the capture: the date of the canonical request (AIMO/CHALLENGE.md).
NEEDED_BY = "2026-11-16"
TAX_RATE = Decimal("14")
REQUESTED_LITRES = Decimal(1000)  # the one request line of a test option, which covers `fill_ratio` of it
_UNSET: Any = object()
# The offer's verdict on a substitute that can take the original's place like for like (`tta.offers.substitutes`).
LIKE_FOR_LIKE = ReplaceCheck(
    verdict=ReplaceVerdict.REPLACEABLE,
    sentence="Replaceable: same type, same use, no flavour named, same formula within tolerance.",
)


@pytest.fixture(scope="session")
def now() -> datetime:
    return NOW


@pytest.fixture(scope="session")
def engine() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


@pytest.fixture(scope="session")
def hotel(engine: RulePolicyEngine) -> BuyerProfile:
    return engine.get_profile("hotel-kitchen")


@pytest.fixture(scope="session")
def ward(engine: RulePolicyEngine) -> BuyerProfile:
    return engine.get_profile("allergy-ward")


@pytest.fixture(scope="session")
def rules_data() -> Callable[[], dict[str, Any]]:
    """A fresh, editable copy of the shipped rules file as plain data."""
    return lambda: yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def profile_data() -> Callable[[str], dict[str, Any]]:
    """A fresh, editable copy of one shipped profile file as plain data."""
    return lambda profile_id: yaml.safe_load((PROFILES_DIR / f"{profile_id}.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def write_yaml(tmp_path: Path) -> Callable[[str, Any], Path]:
    def write(name: str, data: Any) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    return write


@pytest.fixture(scope="session")
def make_allergen_check() -> Callable[..., AllergenCheck]:
    def build(
        relations: Mapping[str, AllergenRelation],
        strictness: AllergenStrictness = AllergenStrictness.STRICT,
        outcome: AllergenOutcome | None = None,
    ) -> AllergenCheck:
        """The check the allergen package gives a product that states `relations`, each code being excluded.

        The table of SPEC section 6 is not copied here: `tta.allergens.check_exclusions` applies it, so these
        tests fail when it changes. `outcome` overrides the overall outcome, to build a check that
        contradicts its own findings.
        """
        statements = tuple(
            AllergenStatement(code=code, relation=relation)
            for code, relation in relations.items()
            if relation is not AllergenRelation.NOT_STATED  # no statement is no entry (tta.contracts.allergen)
        )
        check = check_exclusions(statements, tuple(relations), strictness)
        return check if outcome is None else check.model_copy(update={"outcome": outcome})

    return build


@pytest.fixture(scope="session")
def make_substitute() -> Callable[..., SubstituteInfo]:
    def build(
        *, listed: bool = True, category_distance: int = 0, added: Sequence[tuple[str, AllergenRelation]] = (),
        claims_lost: Sequence[str] = (), replaceable: ReplaceCheck | None = LIKE_FOR_LIKE,
        original_net: str | None = _UNSET,
    ) -> SubstituteInfo:
        """A stand-in for 473609. `claims_lost`: nutritional claims of the original that it does not carry.
        `replaceable`: the offer's like-for-like verdict, which every substitute line of an offer carries; rule
        F-12 sends any other verdict to a person, and `None` (a line stored before the verdict existed) too.
        `original_net`: what the product asked for would have cost for the same content (rule P-05). Left out:
        `make_line` reads it as the line's own net, a substitute at the same price. `None`: not known."""
        priced = {} if original_net is _UNSET else {
            "original_net": None if original_net is None else Decimal(original_net)
        }
        return SubstituteInfo(
            **priced,
            original_id="473609",
            original_name="Oddlygood Barista oat drink",
            listed_by_supplier=listed,
            category_distance=category_distance,
            allergen_check=SubstituteAllergenCheck(
                passes=not added,
                added=tuple(AllergenStatement(code=code, relation=relation) for code, relation in added),
                sentence="Adds an allergen the original does not declare." if added else "Adds no allergen.",
            ),
            claims_lost=tuple(claims_lost),
            gives_up="A different brand.",
            replaceable=replaceable,
        )

    return build


@pytest.fixture(scope="session")
def make_line() -> Callable[..., OfferLine]:
    def build(
        product_id: str = "463380",
        name: str = "Arla Café milk 1 L UHT",
        *,
        quantity: str = "100",
        unit_net_price: str = "2.65",
        state: AvailabilityState = AvailabilityState.CONFIRMED,
        price_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        quantity_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        delivery_date_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        allergens_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        origin_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        allergen_check: AllergenCheck | None = None,
        variable_weight: bool | None = False,
        has_deposits: bool = False,
        substitute: SubstituteInfo | None = None,
    ) -> OfferLine:
        """A line with all five claims of SPEC section 4, each CONFIRMED. `None` for a claim leaves it out."""
        units = Decimal(quantity)
        net = round_money(units * Decimal(unit_net_price))
        tax = round_money(net * TAX_RATE / 100)
        confirmed = state is AvailabilityState.CONFIRMED
        statuses = {
            ClaimName.PRICE: price_claim,
            ClaimName.QUANTITY: quantity_claim,
            ClaimName.DELIVERY_DATE: delivery_date_claim,
            ClaimName.ALLERGENS: allergens_claim,
            ClaimName.ORIGIN: origin_claim,
        }
        claims = tuple(
            ClaimCheck(claim=claim, status=status, sentence=f"The {claim.value} claim is {status.value}.")
            for claim, status in statuses.items()
            if status is not None
        )
        if substitute is not None and "original_net" not in substitute.model_fields_set:
            # A substitute at the price of the product asked for, unless the test says what that would have cost.
            substitute = substitute.model_copy(update={"original_net": net})
        return OfferLine(
            product_id=product_id,
            name=name,
            category="10400",
            request_line_index=0,
            quantity=units,
            sales_unit="ST",
            pack_size=PackSize(value=Decimal(1), unit=Unit.L, source=PackSizeSource.PRICE_RATIO),
            covers=units,
            unit_net_price=Decimal(unit_net_price),
            tax_rate=TAX_RATE,
            net=net,
            tax=tax,
            gross=net + tax,
            price_valid_to=NOW + timedelta(days=30),
            availability=AvailabilityAssessment(
                product_id=product_id,
                state=state,
                usable_amount=units if confirmed else None,
                sales_unit="ST",
                closing_time=NOW + timedelta(days=1),
                sentence="Confirmed." if confirmed else "Not confirmed.",
            ),
            claims=claims,
            allergen_check=allergen_check,
            variable_weight=variable_weight,
            has_deposits=has_deposits,
            substitute=substitute,
        )

    return build


@pytest.fixture(scope="session")
def make_option(make_line: Callable[..., OfferLine]) -> Callable[..., OfferOption]:
    def build(
        lines: Sequence[OfferLine] | None = None,
        *,
        net: str = "100.00",
        fill_ratio: str = "1",
        kind: OptionKind = OptionKind.BEST_CONFIRMED,
        valid_until: datetime | None = _UNSET,
        is_ceiling: bool = False,
        excludes_deposits: bool = False,
        needed_by: CheckResult | None = CheckResult.MET,
    ) -> OfferOption:
        """An option of a one-line request dated `NEEDED_BY`, which it meets. `needed_by=None`: the request gave
        no date. The line asks for 1,000 L and the option covers `fill_ratio` of it."""
        total = Decimal(net)
        tax = round_money(total * TAX_RATE / 100)
        ratio = Decimal(fill_ratio)
        covered = REQUESTED_LITRES * ratio
        return OfferOption(
            option_id="opt_1",
            kind=kind,
            rank=1,
            title="Test option",
            summary="An option built for a policy test.",
            lines=tuple(lines) if lines is not None else (make_line(),),
            totals=Totals(
                net=total, tax=tax, gross=total + tax, excludes_deposits=excludes_deposits, is_ceiling=is_ceiling
            ),
            coverage=(
                Coverage(
                    request_line_index=0, requested=REQUESTED_LITRES, covered=covered, unit=Unit.L, fill_ratio=ratio,
                    missing=REQUESTED_LITRES - covered,
                ),
            ),
            fill_ratio=ratio,
            valid_until=NOW + timedelta(days=1) if valid_until is _UNSET else valid_until,
            constraint_checks=() if needed_by is None else (
                ConstraintCheck(
                    kind=ConstraintKind.NEEDED_BY, subject=NEEDED_BY, result=needed_by,
                    sentence=f"The needed-by check for {NEEDED_BY} is {needed_by.value}.",
                ),
            ),
        )

    return build


@pytest.fixture(scope="session")
def make_revalidation() -> Callable[..., RevalidationResult]:
    def build(*, ok: bool = True, expired: bool = False, changed_price: bool = False) -> RevalidationResult:
        changes = (
            RevalidationChange(
                product_id="463380", field="price", before="2.65", after="2.80",
                sentence="The price of 463380 changed from 2.65 to 2.80.",
            ),
        ) if changed_price else ()
        return RevalidationResult(ok=ok, expired=expired, changes=changes, checked_at=NOW, source=DataSource.REPLAY)

    return build


@pytest.fixture(scope="session")
def make_context() -> Callable[..., PolicyContext]:
    def build(
        day_committed: str | None = "0",
        *,
        at_order_time: bool = False,
        revalidation: RevalidationResult | None = None,
        at: datetime = NOW,
        day_waiting: str | None = None,
    ) -> PolicyContext:
        """`day_waiting`: the part of `day_committed` that waits for a person; None when the caller does not say."""
        return PolicyContext(
            now=at,
            day_committed_net_eur=None if day_committed is None else Decimal(day_committed),
            day_waiting_net_eur=None if day_waiting is None else Decimal(day_waiting),
            at_order_time=at_order_time,
            revalidation=revalidation,
        )

    return build
