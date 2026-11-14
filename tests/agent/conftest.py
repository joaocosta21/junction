"""Fixtures for the buyer agent tests: the gateway in replay over tonight's capture, a scripted model.

No test here calls Gemini or the live Valio API, and nothing reads `.env`. Every helper is a fixture or a
class handed out by one, because test modules cannot import from one another (`--import-mode=importlib`).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tta.agent.model import AnswerSource, ExtractCall, FunctionCall, ModelTurn, TurnCall
from tta.agent.outage import PROCESS_OUTAGE
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.runner import ModelAgentRunner
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import REPO_ROOT, Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.common import AllergenStrictness
from tta.contracts.ports import Clock

SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
NO_QUANTITY_TEXT = "Some milk for Monday"
FIXTURES_AGENT_DIR = REPO_ROOT / "fixtures" / "agent"
# Surfaces other tasks add to the gateway. They may be half-written while these tests run.
OTHER_SURFACES = ("tta.api.mcp_surface", "tta.ui.routes")
PROFILE_STRICTNESS = {"allergy-ward": AllergenStrictness.STRICT, "hotel-kitchen": None}
HAPPY_PATH = ([("get_authority", {})], [("create_offer", {})], [("place_order", {"option_id": "opt_1"})])

Json = dict[str, Any]


@dataclass
class ScriptedModel:
    """A model that answers from a script and remembers what it was asked. Satisfies `AgentModel`.
    A turn of the script that is an exception is raised instead of answered."""

    extracts: list[str] = field(default_factory=list)
    turns: list[Sequence[tuple[str, Json]] | Exception] = field(default_factory=list)
    model_id: str = "scripted"
    recorded: bool = False
    extract_calls: list[ExtractCall] = field(default_factory=list)
    turn_calls: list[TurnCall] = field(default_factory=list)

    def label_for(self, request_text: str) -> str:
        return self.model_id

    def answer_source(self, request_text: str) -> AnswerSource:
        return AnswerSource(ReadingSource.MODEL, self.model_id)

    def extract(self, call: ExtractCall) -> str:
        self.extract_calls.append(call)
        return self.extracts.pop(0)

    def next_turn(self, call: TurnCall) -> ModelTurn:
        self.turn_calls.append(call)
        if not self.turns:
            return ModelTurn(text="Done.")
        scripted_turn = self.turns.pop(0)
        if isinstance(scripted_turn, Exception):
            raise scripted_turn
        calls = tuple(
            FunctionCall(id=f"call-{call.turn}-{number}", name=name, arguments=arguments)
            for number, (name, arguments) in enumerate(scripted_turn, start=1)
        )
        steps = tuple(
            {"type": "function_call", "id": one.id, "name": one.name, "arguments": one.arguments} for one in calls
        )
        return ModelTurn(steps=steps, calls=calls)


@pytest.fixture(autouse=True)
def no_remembered_outage() -> Iterator[None]:
    """The process's memory of a Gemini outage is empty when each test starts and when it ends."""
    PROCESS_OUTAGE.clear()
    yield
    PROCESS_OUTAGE.clear()


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def product_type_keys(catalog: ProductCatalog) -> tuple[str, ...]:
    return catalog.product_type_keys()


@pytest.fixture
def without_other_surfaces() -> Iterator[None]:
    """The MCP surface and the pages read as not installed, whatever their tasks have landed."""
    with pytest.MonkeyPatch.context() as patch:
        for name in OTHER_SURFACES:
            patch.setitem(sys.modules, name, None)
        yield


@pytest.fixture
def parts(settings: Settings, catalog: ProductCatalog) -> Iterator[Parts]:
    """The gateway in replay, wired through the real hooks: with no key, the recorded model."""
    built = build_parts(settings, catalog=catalog)
    yield built
    built.close()


@pytest.fixture(scope="session")
def recorded_model() -> RecordedModel:
    return RecordedModel(FIXTURES_AGENT_DIR)


@pytest.fixture(scope="session")
def scripted() -> type[ScriptedModel]:
    return ScriptedModel


@pytest.fixture(scope="session")
def make_parser(product_type_keys: tuple[str, ...]) -> Callable[..., ModelRequestParser]:
    """A parser over any model, with the two demonstration profiles' strictness."""

    def build(model: Any, clock: Clock) -> ModelRequestParser:
        return ModelRequestParser(
            model=model, clock=clock, product_type_keys=product_type_keys,
            profile_strictness=lambda profile_id: PROFILE_STRICTNESS[profile_id],
        )

    return build


@pytest.fixture(scope="session")
def proposal() -> Callable[..., str]:
    """The JSON text a model returns for a one-line request; keyword arguments replace fields of the line."""

    def build(*, needed_by: str | None = "2026-11-16", require_confirmed: bool = False, **line: Any) -> str:
        base: Json = {
            "product_type": "milk", "product_ids": [], "name_terms": [], "required_claims": [], "quantity": 10,
            "unit": "L", "exclude_allergens": [], "allergen_strictness": None, "pack": None,
        }
        return json.dumps(
            {"needed_by": needed_by, "require_confirmed": require_confirmed, "lines": [{**base, **line}]}
        )

    return build


@pytest.fixture(scope="session")
def ward_answer(proposal: Callable[..., str]) -> str:
    """What a model returns for the allergy ward's request: 200 litres of plant drink, no milk, no gluten."""
    return proposal(product_type="plant_drink", quantity=200, exclude_allergens=["AM", "AW"], require_confirmed=True)


@pytest.fixture(scope="session")
def happy_path() -> tuple[list[tuple[str, Json]], ...]:
    """The turns of a run with nothing in its way: authority, offer, order of the first option."""
    return HAPPY_PATH


@pytest.fixture
def scripted_runner(
    make_parser: Callable[..., ModelRequestParser], demo_clock: Clock
) -> Callable[..., tuple[ScriptedModel, ModelAgentRunner]]:
    """A runner over a scripted model: one structured answer, then the given turns."""

    def build(answer: str, turns: Sequence[Any]) -> tuple[ScriptedModel, ModelAgentRunner]:
        script = [turn if isinstance(turn, Exception) else list(turn) for turn in turns]
        model = ScriptedModel(extracts=[answer], turns=script)
        return model, ModelAgentRunner(model=model, parser=make_parser(model, demo_clock))

    return build


@pytest.fixture(scope="session")
def fixtures_agent_dir() -> Path:
    return FIXTURES_AGENT_DIR


@pytest.fixture(scope="session")
def shown_as() -> Callable[[str], str]:
    """What a trace shows as the model for a sentence of `fixtures/agent/`: "recorded" once the live check
    has saved the model's own answers, "hand-built" while a person's are in their place."""

    def label(text: str) -> str:
        files = (json.loads(path.read_text(encoding="utf-8")) for path in FIXTURES_AGENT_DIR.glob("*.json"))
        sources = {recording["source"] for recording in files if recording["text"] == text}
        return "recorded" if sources == {"live"} else "hand-built"

    return label


@pytest.fixture(scope="session")
def texts() -> dict[str, str]:
    return {"scenario_1": SCENARIO_1_TEXT, "scenario_2": SCENARIO_2_TEXT, "no_quantity": NO_QUANTITY_TEXT}
