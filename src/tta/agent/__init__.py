"""Gemini: request parsing and the buyer agent loop (SPEC section 11; task T10).

The gateway looks for the two factories below (`tta.api.hooks`). With no key they return the parser and the
runner over the recorded model, so the demonstration scenarios run without a key. With a Gemini key they
return the same parser and runner over the Gemini model, with the recorded ones behind them: when Gemini
cannot be reached, a sentence that has a recording is answered from it, and says so (`tta.agent.fallback`).
Behind the recordings, with or without a key, stand the fixed rules (`tta.agent.rules_reader`, task FALLBACK-1):
a common sentence with no recording is read by them, and says so.
Both Gemini models share the process's memory of an outage (`tta.agent.outage`).

Task AG: which model is asked first is a setting (`TTA_AGENT_PROVIDER`). `openai_compatible` asks the model behind
`TTA_AGENT_BASE_URL` (the open-weights model of `deploy/agent_model.py` on Modal): its reading is held to the
buyer's words (`tta.agent.held`), its run is told the buyer's authority, and the fixed rules are its check and its
fallback (`tta.agent.fallback`, `ours`). Gemini is then never asked. `gemini` and `none` are as before: Gemini
when its key is set, else no model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

from tta.agent.brands import NO_BRANDS, Brands, products_of
from tta.agent.fallback import FallbackParser, FallbackRunner
from tta.agent.gemini import DEFAULT_MODEL, GeminiModel, chosen_model, sdk_transport
from tta.agent.model import AgentModel
from tta.agent.openai_compat import OUTAGE_MEMORY_SECONDS, OpenAICompatibleModel
from tta.agent.outage import PROCESS_OUTAGE, Outage
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.rules_model import RuleModel, brands_for
from tta.agent.runner import ModelAgentRunner
from tta.agent.status import PROCESS_STATUS, agent_status
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
    "OpenAICompatibleModel",
    "RecordedModel",
    "RuleModel",
    "agent_status",
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
    model: AgentModel, clock: Clock, keys: Sequence[str], strictness: Strictness, brands: Brands = NO_BRANDS,
    *, held_to_words: bool = False,
) -> ModelRequestParser:
    return ModelRequestParser(
        model=model, clock=clock, product_type_keys=keys, profile_strictness=strictness, brands=brands,
        held_to_words=held_to_words,
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


# The model of ours remembers its own outage, for a shorter while than Gemini's (`tta.agent.openai_compat`).
OURS_OUTAGE = Outage(seconds=OUTAGE_MEMORY_SECONDS)


def _ours(settings: Settings) -> OpenAICompatibleModel | None:
    """The model behind the OpenAI-compatible endpoint, when the settings choose it and name it. Building it
    sends nothing."""
    if not settings.has_agent_endpoint:
        return None
    return OpenAICompatibleModel.from_settings(settings, outage=OURS_OUTAGE, status=PROCESS_STATUS)


def _fallback_parser(
    ours: OpenAICompatibleModel, settings: Settings, clock: Clock, keys: Sequence[str], strictness: Strictness
) -> FallbackParser:
    """The model of ours first, held to the buyer's words; then a recording; then the fixed rules."""
    recordings = RecordedModel.from_settings(settings)
    brands = _brands(settings, keys)
    return FallbackParser(
        live=_parser(ours, clock, keys, strictness, brands, held_to_words=True),
        recorded=_parser(recordings, clock, keys, strictness), recordings=recordings,
        rules=_parser(RuleModel.for_keys(keys, brands), clock, keys, strictness, brands), ours=True,
    )


def build_request_parser(
    *, settings: Settings, clock: Clock, product_type_keys: Sequence[str]
) -> FallbackParser:
    """`clock` is the data clock (pinned in replay): "by Monday" is resolved against it."""
    strictness = profile_strictness()
    ours = _ours(settings)
    if ours is not None:
        return _fallback_parser(ours, settings, clock, product_type_keys, strictness)
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
    ours = _ours(settings)
    if ours is not None:
        # The model of ours makes the calls on a reading that is its own, checked, or the fixed rules' (and says
        # which); it is told the buyer's authority as the gateway reports it.
        reader = _fallback_parser(ours, settings, clock, product_type_keys, strictness)
        live = ModelAgentRunner(model=ours, parser=reader, states_authority=True)
        return FallbackRunner(live=live, recorded=recorded, recordings=recordings, rules=rules, ours=True)
    live = None
    if settings.has_gemini_key:
        gemini = _gemini(settings)
        live = ModelAgentRunner(model=gemini, parser=_parser(gemini, clock, product_type_keys, strictness))
    return FallbackRunner(live=live, recorded=recorded, recordings=recordings, rules=rules)
