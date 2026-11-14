"""Gemini: request parsing and the buyer agent loop (SPEC section 11; task T10).

The gateway looks for the two factories below (`tta.api.hooks`). With a Gemini key they return the parser
and the runner over the Gemini model; with no key, the same parser and runner over the recorded model, so
the demonstration scenarios run without a key.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

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


def _model(settings: Settings) -> AgentModel:
    if settings.has_gemini_key:
        return GeminiModel(sdk_transport(settings), chosen_model(settings))
    return RecordedModel.from_settings(settings)


def build_request_parser(*, settings: Settings, clock: Clock, product_type_keys: Sequence[str]) -> ModelRequestParser:
    """`clock` is the data clock (pinned in replay): "by Monday" is resolved against it."""
    return ModelRequestParser(
        model=_model(settings), clock=clock, product_type_keys=product_type_keys,
        profile_strictness=profile_strictness(),
    )


def build_agent_runner(*, settings: Settings, clock: Clock, product_type_keys: Sequence[str]) -> ModelAgentRunner:
    """The runner reads the pasted text with a parser of its own, over the same model."""
    model = _model(settings)
    parser = ModelRequestParser(
        model=model, clock=clock, product_type_keys=product_type_keys, profile_strictness=profile_strictness()
    )
    return ModelAgentRunner(model=model, parser=parser)
