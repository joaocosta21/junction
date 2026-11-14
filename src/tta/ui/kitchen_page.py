"""The page "Your kitchen": the buyer sets what its own agent may decide alone (task FEAT-1).

Scores on Core 3 of the brief, "what the agent may decide on its own, and what must go to a human for sign-off",
on the 20% "autonomy and controls" and on the 30% demo. Each setting is shown with the rule it drives (P-00 to
P-07), in this kitchen's own values, and below the form the fixed rules F-01 to F-08 that hold whatever is set.

The settings are checked exactly as a profile file is (`tta.api.sandbox.kitchen_profile`): a value out of range,
an exclusion without a strictness, a setting that names a fixed rule or that the page does not have is refused,
with the field named, and nothing changes. The profile lives in this browser's own order book only: the agent
"My kitchen agent" acts under it, and "Start again" clears it with the book.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import FastAPI, Form
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.allergens import ALLERGEN_CODES, AllergenCode
from tta.allergens.codes import GENERAL_STATEMENT_CODE
from tta.api.sandbox import KITCHEN_AGENT, MAX_EXCLUDED_ALLERGENS, MAX_LIMIT_EUR, STARTING_POINTS, Sandbox
from tta.contracts.common import AllergenStrictness, DepositRule, SubstitutionScope, VariableWeightRule
from tta.contracts.policy import BuyerProfile, RuleSummary
from tta.policy import PolicyLoadError
from tta.ui.site import UNPROCESSABLE, Site, page_error

KITCHEN_PATH = "/kitchen"
START_FROM_PATH = f"{KITCHEN_PATH}/start-from"
TEMPLATE = "kitchen.html"
SEE_OTHER = 303
FORM_ONLY = ("csrf",)  # fields of the form that are not settings
CHECKBOXES = ("auto_order_enabled", "require_confirmed")  # a box left unticked is not sent at all
LISTS = ("excluded_allergens",)
PERCENT_SETTING = "min_fill_ratio"  # a ratio in the profile, a percentage on the page
PERCENT = Decimal(100)
SETTING_RULES = {  # the profile rule each setting drives (rules.yaml)
    "auto_order_enabled": "P-00", "max_order_net_eur": "P-01", "max_daily_net_eur": "P-02",
    "min_fill_ratio": "P-03", "excluded_allergens": "P-04", "substitution_without_approval": "P-05",
    "variable_weight": "P-06", "deposits": "P-07",
}
NO_SUCH_START = ("Not a starting point", "Start from a copy of one of the two demo profiles. Nothing was changed.")
NOT_A_PERCENTAGE = f"{PERCENT_SETTING}: write a share from 0 to 100 percent"
ONE_VALUE = "{name}: give one value"

STRICTNESS_LABELS = {
    AllergenStrictness.STRICT: "Strict: a product with no allergen statement goes to a human",
    AllergenStrictness.DECLARED_ONLY: "Declared only: such a product passes, shown as unverified",
}
SUBSTITUTION_LABELS = {
    SubstitutionScope.NONE: "None: every substitute goes to a human",
    SubstitutionScope.LISTED_BY_SUPPLIER: "Those Valio Aimo lists as substitutes of the product",
    SubstitutionScope.SAME_CATEGORY: "Any product of the same category",
}
VARIABLE_WEIGHT_LABELS = {
    VariableWeightRule.APPROVAL: "To a human",
    VariableWeightRule.AUTO_WITH_CEILING: "Allowed when the total is a ceiling, with the note",
}
DEPOSIT_LABELS = {
    DepositRule.APPROVAL: "To a human",
    DepositRule.NOTE: "Allowed, with the note that the total leaves the deposit out",
}


@dataclass(frozen=True)
class FixedRow:
    """One fixed rule as the page lists it."""

    rule_id: str
    title: str
    sentence: str


def _plain(value: Decimal) -> str:
    """A number as a person writes it: 750, not 750.00 or 7.5E+2."""
    return f"{value.normalize():f}"


def _shown(profile: BuyerProfile) -> dict[str, Any]:
    """The form's values for a profile: what the page shows in each field."""
    return {
        "display_name": profile.display_name,
        "auto_order_enabled": profile.auto_order_enabled,
        "max_order_net_eur": _plain(profile.max_order_net_eur),
        "max_daily_net_eur": _plain(profile.max_daily_net_eur),
        PERCENT_SETTING: _plain(profile.min_fill_ratio * PERCENT),
        "excluded_allergens": frozenset(profile.excluded_allergens),
        "allergen_strictness": profile.allergen_strictness.value if profile.allergen_strictness else "",
        "substitution_without_approval": profile.substitution_without_approval.value,
        "variable_weight": profile.variable_weight.value,
        "deposits": profile.deposits.value,
        "require_confirmed": profile.require_confirmed,
    }


def _ratio(text: str) -> Decimal | str:
    """A percentage as the profile's ratio. Text that is no number is passed on, for the profile check to name."""
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return text
    return value / PERCENT if value.is_finite() else text


def _setting(name: str, text: str) -> Any:
    if name == PERCENT_SETTING:
        return _ratio(text)
    if name == "allergen_strictness":
        return text or None
    return text


def _submitted(form: FormData) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """The form as settings, as values to show again, and what is wrong with the form itself. Every field is
    passed on, the unknown ones too: the profile check refuses what is not a setting of the page."""
    settings: dict[str, Any] = {}
    shown: dict[str, Any] = {}
    problems: list[str] = []
    for name in dict.fromkeys(form.keys()):
        if name in FORM_ONLY:
            continue
        values = [value for value in form.getlist(name) if isinstance(value, str)]
        if name in LISTS:
            settings[name], shown[name] = values, frozenset(values)
        elif len(values) != 1:
            problems.append(ONE_VALUE.format(name=name))
        else:
            settings[name], shown[name] = _setting(name, values[0]), values[0]
    ratio = settings.get(PERCENT_SETTING)
    if isinstance(ratio, Decimal) and not 0 <= ratio <= 1:
        problems.append(NOT_A_PERCENTAGE)
    for name in LISTS:
        settings.setdefault(name, [])
        shown.setdefault(name, frozenset())
    for name in CHECKBOXES:
        settings.setdefault(name, False)
        shown[name] = name in form
    return settings, shown, problems


def _fixed_rows(book: Sandbox, rules: tuple[RuleSummary, ...]) -> tuple[FixedRow, ...]:
    """Every fixed rule: those the engine judges, and those enforced where the caller is known (F-06)."""
    rows = [FixedRow(rule.rule_id, rule.title, rule.sentence) for rule in rules if rule.fixed]
    rows.extend(FixedRow(rule.id, rule.title, rule.text) for rule in book.kitchen.access_rules)
    return tuple(sorted(rows, key=lambda row: row.rule_id))


def _allergens() -> tuple[AllergenCode, ...]:
    """The GS1 allergen codes a kitchen can exclude: every code of the table but the general statement."""
    return tuple(code for code in ALLERGEN_CODES.values() if code.code != GENERAL_STATEMENT_CODE)


def _page(
    site: Site, request: Request, *, book: Sandbox | None = None, shown: Mapping[str, Any] | None = None,
    problems: tuple[str, ...] = (), status: int = 200,
) -> HTMLResponse:
    book = book or site.book(request)
    kitchen = book.kitchen
    authority = book.service.get_authority(KITCHEN_AGENT)
    return site.render(
        request, TEMPLATE, status=status, kitchen=kitchen, authority=authority,
        form={**_shown(kitchen.profile), **(shown or {})}, problems=problems,
        rules={rule.rule_id: rule for rule in authority.rules}, setting_rules=SETTING_RULES,
        fixed_rules=_fixed_rows(book, authority.rules), allergens=_allergens(), starting_points=STARTING_POINTS,
        strictness_labels=STRICTNESS_LABELS, substitution_labels=SUBSTITUTION_LABELS,
        variable_weight_labels=VARIABLE_WEIGHT_LABELS, deposit_labels=DEPOSIT_LABELS,
        max_limit_eur=MAX_LIMIT_EUR, max_excluded=MAX_EXCLUDED_ALLERGENS, agent=KITCHEN_AGENT,
    )


def _save(site: Site, request: Request, form: FormData) -> Response:
    """Check the form's token, then the settings. A refused form shows what is wrong and changes nothing."""
    token = form.get("csrf")
    site.check_form(request, token if isinstance(token, str) else "")
    settings, shown, problems = _submitted(form)
    book = site.own_book(request)
    if not problems:
        try:
            book.kitchen.set_up(settings)
        except PolicyLoadError as error:
            problems = list(error.problems)
        else:
            return RedirectResponse(KITCHEN_PATH, status_code=SEE_OTHER)
    return _page(site, request, book=book, shown=shown, problems=tuple(problems), status=UNPROCESSABLE)


def add_routes(app: FastAPI, site: Site) -> None:
    @app.get(KITCHEN_PATH, response_class=HTMLResponse)
    def kitchen(request: Request) -> HTMLResponse:
        return _page(site, request)

    @app.post(KITCHEN_PATH, response_class=HTMLResponse)
    async def save(request: Request) -> Response:
        """Every field of the form is read, not only those the page has: a field the page does not set is
        refused by name, never dropped in silence."""
        form = await request.form()
        return await run_in_threadpool(_save, site, request, form)

    @app.post(START_FROM_PATH, response_class=HTMLResponse)
    def start_from(
        request: Request, csrf: Annotated[str, Form()] = "", profile: Annotated[str, Form()] = ""
    ) -> Response:
        site.check_form(request, csrf)
        if profile not in STARTING_POINTS:
            raise page_error(UNPROCESSABLE, *NO_SUCH_START)
        site.own_book(request).kitchen.start_from(profile)
        return RedirectResponse(KITCHEN_PATH, status_code=SEE_OTHER)
