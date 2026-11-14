"""Gemini: request parsing and the buyer agent loop (SPEC section 11; task T10).

The gateway looks for the two factories below (`tta.api.hooks`). With no key they return the parser and the
runner over the recorded model, so the demonstration scenarios run without a key. With a Gemini key they
return the same parser and runner over the Gemini model, with the recorded ones behind them: when Gemini
cannot be reached, a sentence that has a recording is answered from it, and says so (`tta.agent.fallback`).
Behind the recordings, with or without a key, stand the fixed rules (`tta.agent.rules_reader`, task FALLBACK-1):
a common sentence with no recording is read by them, and says so.
Both Gemini models share the process's memory of an outage (`tta.agent.outage`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

from tta.agent.brands import NO_BRANDS, Brands, products_of
from tta.agent.fallback import FallbackParser, FallbackRunner
from tta.agent.gemini import DEFAULT_MODEL, GeminiModel, chosen_model, sdk_transport
from tta.agent.model import AgentModel
from tta.agent.outage import PROCESS_OUTAGE
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.rules_model import RuleModel, brands_for
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
    "RuleModel",
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


def _parser(
    model: AgentModel, clock: Clock, keys: Sequence[str], strictness: Strictness, brands: Brands = NO_BRANDS
) -> ModelRequestParser:
    return ModelRequestParser(
        model=model, clock=clock, product_type_keys=keys, profile_strictness=strictness, brands=brands
    )


@lru_cache(maxsize=2)
def _brands_of(product_file: Path, keys: tuple[str, ...]) -> Brands:
    return brands_for(products_of(product_file), keys)


def _brands(settings: Settings, keys: Sequence[str]) -> Brands:
    """The brands of the catalog a request may name (decision B39), from the product file the settings name:
    read and worked out once per process, for the parser and the runner alike."""
    return _brands_of(settings.tta_product_file, tuple(keys))


def _gemini(settings: Settings) -> GeminiModel:
    return GeminiModel(sdk_transport(settings), chosen_model(settings), outage=PROCESS_OUTAGE)


def build_request_parser(
    *, settings: Settings, clock: Clock, product_type_keys: Sequence[str]
) -> FallbackParser:
    """`clock` is the data clock (pinned in replay): "by Monday" is resolved against it."""
    strictness = profile_strictness()
    recordings = RecordedModel.from_settings(settings)
    recorded = _parser(recordings, clock, product_type_keys, strictness)
    brands = _brands(settings, product_type_keys)
    rules = _parser(RuleModel.for_keys(product_type_keys, brands), clock, product_type_keys, strictness, brands)
    live = _parser(_gemini(settings), clock, product_type_keys, strictness) if settings.has_gemini_key else None
    return FallbackParser(live=live, recorded=recorded, recordings=recordings, rules=rules)


def build_agent_runner(
    *, settings: Settings, clock: Clock, product_type_keys: Sequence[str]
) -> FallbackRunner:
    """The runner reads the pasted text with a parser of its own, over the same model."""
    strictness = profile_strictness()
    recordings = RecordedModel.from_settings(settings)
    recorded = ModelAgentRunner(model=recordings, parser=_parser(recordings, clock, product_type_keys, strictness))
    brands = _brands(settings, product_type_keys)
    rule_model = RuleModel.for_keys(product_type_keys, brands)
    rules = ModelAgentRunner(
        model=rule_model, parser=_parser(rule_model, clock, product_type_keys, strictness, brands)
    )
    live = None
    if settings.has_gemini_key:
        gemini = _gemini(settings)
        live = ModelAgentRunner(model=gemini, parser=_parser(gemini, clock, product_type_keys, strictness))
    return FallbackRunner(live=live, recorded=recorded, recordings=recordings, rules=rules)
