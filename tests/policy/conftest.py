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

from tta.contracts.allergen import AllergenCheck, AllergenFinding, AllergenStatement, SubstituteAllergenCheck
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck, RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    DataSource,
    OptionKind,
    PackSizeSource,
    Unit,
    round_money,
)
from tta.contracts.offer import OfferLine, OfferOption, SubstituteInfo, Totals
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.product import PackSize
from tta.policy import PROFILES_DIR, RULES_PATH, RulePolicyEngine

# Server time of the demo capture: Saturday 14 Nov 2026, 02:52 (AIMO/build/AGENT-RULES.md).
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))
TAX_RATE = Decimal("14")
_UNSET: Any = object()
_SEVERITY = {AllergenOutcome.PASS: 0, AllergenOutcome.TO_HUMAN: 1, AllergenOutcome.REJECT: 2}


def _outcome_for(relation: AllergenRelation, strictness: AllergenStrictness) -> AllergenOutcome:
    """The buyer exclusion table of SPEC section 6."""
    if relation is AllergenRelation.FREE_FROM:
        return AllergenOutcome.PASS
    if relation is AllergenRelation.CONTAINS:
        return AllergenOutcome.REJECT
    if relation is AllergenRelation.MAY_CONTAIN or strictness is AllergenStrictness.STRICT:
        return AllergenOutcome.TO_HUMAN
    return AllergenOutcome.PASS


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
        findings = tuple(
            AllergenFinding(
                excluded_code=code,
                relation=relation,
                outcome=_outcome_for(relation, strictness),
                sentence=f"The product states {relation.value} for {code}.",
            )
            for code, relation in relations.items()
        )
        worst = max((finding.outcome for finding in findings), key=_SEVERITY.__getitem__, default=AllergenOutcome.PASS)
        explicit = {AllergenRelation.FREE_FROM, AllergenRelation.CONTAINS}
        return AllergenCheck(
            outcome=outcome or worst,
            strictness=strictness,
            findings=findings,
            all_explicit=all(finding.relation in explicit for finding in findings),
        )

    return build


@pytest.fixture(scope="session")
def make_substitute() -> Callable[..., SubstituteInfo]:
    def build(
        *, listed: bool = True, category_distance: int = 0, added: Sequence[tuple[str, AllergenRelation]] = ()
    ) -> SubstituteInfo:
        return SubstituteInfo(
            original_id="473609",
            original_name="Oddlygood Barista oat drink",
            listed_by_supplier=listed,
            category_distance=category_distance,
            allergen_check=SubstituteAllergenCheck(
                passes=not added,
                added=tuple(AllergenStatement(code=code, relation=relation) for code, relation in added),
                sentence="Adds an allergen the original does not declare." if added else "Adds no allergen.",
            ),
            gives_up="A different brand.",
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
        quantity_claim: ClaimStatus | None = ClaimStatus.CONFIRMED,
        allergen_check: AllergenCheck | None = None,
        variable_weight: bool | None = False,
        has_deposits: bool = False,
        substitute: SubstituteInfo | None = None,
    ) -> OfferLine:
        units = Decimal(quantity)
        net = round_money(units * Decimal(unit_net_price))
        tax = round_money(net * TAX_RATE / 100)
        confirmed = state is AvailabilityState.CONFIRMED
        claims = () if quantity_claim is None else (
            ClaimCheck(claim=ClaimName.QUANTITY, status=quantity_claim, sentence="Quantity claim."),
        )
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
    ) -> OfferOption:
        total = Decimal(net)
        tax = round_money(total * TAX_RATE / 100)
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
            fill_ratio=Decimal(fill_ratio),
            valid_until=NOW + timedelta(days=1) if valid_until is _UNSET else valid_until,
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
    ) -> PolicyContext:
        return PolicyContext(
            now=at,
            day_committed_net_eur=None if day_committed is None else Decimal(day_committed),
            at_order_time=at_order_time,
            revalidation=revalidation,
        )

    return build
