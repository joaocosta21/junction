"""Gemini: request parsing and the buyer agent loop (SPEC section 11; task T10).

The gateway looks for the two factories below (`tta.api.hooks`). With no key they return the parser and the
runner over the recorded model, so the demonstration scenarios run without a key. With a Gemini key they
return the same parser and runner over the Gemini model, with the recorded ones behind them: when Gemini
cannot be reached, a sentence that has a recording is answered from it, and says so (`tta.agent.fallback`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tta.agent.fallback import FallbackParser, FallbackRunner
from tta.agent.gemini import DEFAULT_MODEL, GeminiModel, chosen_model, sdk_transport
from tta.agent.model import AgentModel
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.runner import ModelAgentRunner
from tta.config import Settings
from tta.contracts.common import AllergenStrictness
from tta.contracts.ports import Clock
from tta.policy import RulePolicyEngine

__all__ = [
    "DEFAULT_MODEL",
    "FallbackParser",
    "FallbackRunner",
    "GeminiModel",
    "ModelAgentRunner",
    "ModelRequestParser",
    "RecordedModel",
    "build_agent_runner",
    "build_request_parser",
    "profile_strictness",
]


def profile_strictness() -> Callable[[str], AllergenStrictness | None]:
    """The allergen strictness a buyer profile sets, read from the policy files: the parser needs it to know
    whether an exclusion said in the text still lacks one. Raises `NotAuthorised` for an unknown profile."""
    policy = RulePolicyEngine.from_files()
    return lambda profile_id: policy.get_profile(profile_id).allergen_strictness


Strictness = Callable[[str], AllergenStrictness | None]


def _parser(model: AgentModel, clock: Clock, keys: Sequence[str], strictness: Strictness) -> ModelRequestParser:
    return ModelRequestParser(model=model, clock=clock, product_type_keys=keys, profile_strictness=strictness)


def _gemini(settings: Settings) -> GeminiModel:
    return GeminiModel(sdk_transport(settings), chosen_model(settings))


def build_request_parser(
    *, settings: Settings, clock: Clock, product_type_keys: Sequence[str]
) -> ModelRequestParser | FallbackParser:
    """`clock` is the data clock (pinned in replay): "by Monday" is resolved against it."""
    strictness = profile_strictness()
    recordings = RecordedModel.from_settings(settings)
    recorded = _parser(recordings, clock, product_type_keys, strictness)
    if not settings.has_gemini_key:
        return recorded
    live = _parser(_gemini(settings), clock, product_type_keys, strictness)
    return FallbackParser(live=live, recorded=recorded, recordings=recordings)


def build_agent_runner(
    *, settings: Settings, clock: Clock, product_type_keys: Sequence[str]
) -> ModelAgentRunner | FallbackRunner:
    """The runner reads the pasted text with a parser of its own, over the same model."""
    strictness = profile_strictness()
    recordings = RecordedModel.from_settings(settings)
    recorded = ModelAgentRunner(model=recordings, parser=_parser(recordings, clock, product_type_keys, strictness))
    if not settings.has_gemini_key:
        return recorded
    gemini = _gemini(settings)
    live = ModelAgentRunner(model=gemini, parser=_parser(gemini, clock, product_type_keys, strictness))
    return FallbackRunner(live=live, recorded=recorded, recordings=recordings)
