"""A menu asked for in a sentence (task CK): "I want to make a chocolate cake for 20 people".

Scores on the 30% "full request → lookup → order/approval flow" and the 20% "how precisely the agent matches what
the buyer actually asked for". `MenuAsk` is the body of POST /v1/menus/plan and the argument of the MCP tool
`plan_menu`: the typed menu request, with an optional `text` beside it. `resolve` turns it into the typed request
the planner takes and the sentence that says what was read. Typed fields win: typed dishes are used as they are,
a typed date is kept. Nothing is guessed (`tta.agent.dishes`): a dish that is not in the recipe table, servings
that are missing or unclear, and two days are refused with the question to answer, and the list of dishes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from tta.agent.days import helsinki_date
from tta.agent.dishes import MAX_TEXT, DishSentence, read_dishes
from tta.availability.wording import format_day
from tta.config import Settings
from tta.contracts.common import DataSource, Identity
from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import MAX_DISHES, DishOrder, MenuPlan, MenuRequest, Recipe
from tta.contracts.offer import Offer
from tta.contracts.ports import GatewayService
from tta.menus.ingredients import named_as_a_dish, no_dish_named
from tta.menus.planner import plan_menu
from tta.menus.recipes import dish_names
from tta.menus.wording import THE_DISHES, joined
from tta.offers.recorded import later_recorded_note as offer_later_recorded_note
from tta.valio.replay import ReplayGateway, recording_instant

NOTHING_ASKED = (
    'Name at least one dish: in `dishes`, or in `text` as a sentence, for example "chocolate cake for 20". '
    + THE_DISHES
)
NO_RECIPE = "No recipe for {unknown} in the recipe table. " + THE_DISHES
READ_AS = "Read as: {what}."
TYPED_DISHES_WIN = " The typed dishes were used, not the sentence's."
TYPED_DATE_WINS = " The typed date was used, not the sentence's."


class MenuAsk(MenuRequest):
    """Body of POST /v1/menus/plan: the typed menu request, or a sentence, or both (typed fields win)."""

    text: str | None = Field(
        default=None, max_length=MAX_TEXT,
        description='A sentence that names dishes of the recipe table, each with its servings, and optionally a '
        'day: "I want to make a chocolate cake for 20 people", "lasagne for 50 and oven pancake for 50 by Monday". '
        "Read by fixed rules, with no model; what cannot be read is asked about, never guessed. Typed `dishes` and "
        "a typed `needed_by` win over the sentence's",
    )
    dishes: tuple[DishOrder, ...] = Field(
        default=(), max_length=MAX_DISHES, description="The dishes with their servings; may be empty when `text` "
        "names them",
    )


@dataclass(frozen=True)
class Resolved:
    """The typed request the planner takes, and what was read from the sentence (None: there was no sentence)."""

    request: MenuRequest
    read_as: str | None = None


def data_today(settings: Settings) -> date:
    """The date in Helsinki that "by Monday" is counted from, for a caller that holds the settings and not the
    gateway's clock: the demo clock or the recording's instant in replay, the real time in live mode (the
    supplier's server time is not asked for a sentence). Raises `SupplierUnavailable` for an unusable capture."""
    if settings.tta_mode is not DataSource.REPLAY:
        return helsinki_date(datetime.now(UTC))
    return helsinki_date(settings.demo_clock or recording_instant(settings.replay_capture_dir))


def dish_list(recipes: Mapping[str, Recipe]) -> str:
    """`beef stew, lasagne and chocolate cake`: each dish by its first name."""
    return joined([names[0] for names in dish_names(recipes).values()])


def _refuse(
    reading: DishSentence | None, recipes: Mapping[str, Recipe], text: str, *, need_dishes: bool
) -> None:
    """Raises `InvalidRequest` with the question to answer when the sentence cannot be used as it is. A
    sentence that names no dish is answered with the dishes that use the ingredient it names, when it names
    one (`tta.menus.ingredients`)."""
    dishes = dish_list(recipes)
    if reading is None:
        if need_dishes:
            raise no_dish_named(text, recipes, dishes)
        return
    if need_dishes and reading.unknown:
        ingredient = None if reading.dishes else named_as_a_dish(reading.unknown, text, recipes)
        if ingredient is not None:
            raise ingredient
        unknown = joined([f'"{name}"' for name in reading.unknown])
        raise InvalidRequest(NO_RECIPE.format(unknown=unknown, dishes=dishes))
    problems = reading.problems if need_dishes else tuple(
        problem for problem in reading.problems if problem.endswith("Which day is it needed by?")
    )
    if problems:
        raise InvalidRequest(" ".join(problems))
    if need_dishes and not reading.dishes:
        raise no_dish_named(text, recipes, dishes)


def _read_as(reading: DishSentence, recipes: Mapping[str, Recipe], *, dishes_used: bool, date_used: bool) -> str:
    names = dish_names(recipes)
    parts = [f"{names[dish.dish_id][0]}, {dish.servings:,} serving{'s' if dish.servings != 1 else ''}"
             for dish in reading.dishes if dish.servings is not None]
    if reading.needed_by is not None:
        parts.append(f"by {format_day(reading.needed_by)}")
    said = READ_AS.format(what="; ".join(parts) if len(reading.dishes) > 1 else ", ".join(parts))
    if not dishes_used and reading.dishes:
        said += TYPED_DISHES_WIN
    if not date_used and reading.needed_by is not None:
        said += TYPED_DATE_WINS
    return said


def resolve(ask: MenuAsk, recipes: Mapping[str, Recipe], today: date) -> Resolved:
    """The typed request of a typed menu, a sentence, or both. `today` is the date the days of the sentence are
    counted from (the gateway's clock, in Helsinki). Raises `InvalidRequest`, with the list of dishes, when
    neither names a dish, and with the question to answer when the sentence cannot be read without a guess."""
    typed = ask.model_dump(exclude={"text"})
    text = (ask.text or "").strip()
    if not text:
        if not ask.dishes:
            raise InvalidRequest(NOTHING_ASKED.format(dishes=dish_list(recipes)))
        return Resolved(MenuRequest.model_validate(typed))
    reading = read_dishes(text, dish_names(recipes), today)
    _refuse(reading, recipes, text, need_dishes=not ask.dishes)
    if reading is None:
        return Resolved(MenuRequest.model_validate(typed))
    dishes_used, date_used = not ask.dishes, ask.needed_by is None
    if dishes_used:
        typed["dishes"] = [{"dish_id": dish.dish_id, "servings": dish.servings} for dish in reading.dishes]
    if date_used:
        typed["needed_by"] = reading.needed_by
    return Resolved(
        MenuRequest.model_validate(typed),
        _read_as(reading, recipes, dishes_used=dishes_used, date_used=date_used),
    )


def later_recorded_note(replay: ReplayGateway, offer: Offer | None) -> str | None:
    """Which products of the plan's offer were answered from a recording made after the first one, with both
    instants and why reading them together is honest (`ReplayGateway.join_sentence`). None when the offer is not
    a replay, or holds no such product: no answer is silently taken from another time. The sentence is the
    offer's own (`tta.offers.recorded`), worded in one place, so a plan and its offer say the same words and a
    page that shows both can say them once."""
    if offer is None or offer.source is not DataSource.REPLAY:
        return None
    offered = tuple(dict.fromkeys(line.product_id for option in offer.options for line in option.lines))
    return offer_later_recorded_note(replay, offered)


def with_notes(plan: MenuPlan, *, read_as: str | None, later: str | None) -> MenuPlan:
    """The plan with what was read from the sentence as its first note and the later recording as its last."""
    notes = (*((read_as,) if read_as else ()), *plan.notes, *((later,) if later else ()))
    return plan if notes == plan.notes else plan.model_copy(update={"notes": notes})


@lru_cache(maxsize=2)
def _recording(capture_dir: Path) -> ReplayGateway:
    return ReplayGateway(capture_dir)


def later_recorded_note_of(settings: Settings, offer: Offer | None) -> str | None:
    """`later_recorded_note` for a caller that holds the settings and not the gateway's parts (the menu page, the
    MCP tool). The recording is read once per process: which recording answers a product does not depend on the
    clock. Raises `SupplierUnavailable` for an unusable capture."""
    if offer is None or offer.source is not DataSource.REPLAY:
        return None
    return later_recorded_note(_recording(settings.replay_capture_dir), offer)


def plan_from_ask(
    service: GatewayService, caller: Identity, ask: MenuAsk, recipes: Mapping[str, Recipe], settings: Settings
) -> MenuPlan:
    """The plan of a typed menu, a sentence or both, for a caller that holds the settings and not the gateway's
    clock: the day of a sentence is counted from `data_today(settings)`. Raises what `resolve` and `plan_menu`
    raise."""
    resolved = resolve(ask, recipes, data_today(settings))
    plan = plan_menu(service, caller, resolved.request, recipes)
    offer = service.get_offer(caller, plan.offer_id) if plan.offer_id is not None else None
    return with_notes(plan, read_as=resolved.read_as, later=later_recorded_note_of(settings, offer))
