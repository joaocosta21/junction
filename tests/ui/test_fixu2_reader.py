"""FIX-U2, item 10: the old pages name the language model that is asked first as `/healthz` names it
(`agent_reader`), and name none where none is asked: never Gemini for another provider.

Scores on the 15% "clear visibility of assumptions": a run's label says what served it.
"""

from __future__ import annotations

from tta.config import Settings
from tta.contracts.agent import AgentRun
from tta.ui import site, view

ENDPOINT = {"tta_agent_provider": "openai_compatible", "tta_agent_base_url": "http://model.invalid/v1",
            "tta_agent_model": "open-model-1"}


def _run(model: str, recorded: bool) -> AgentRun:
    return AgentRun(text="300 litres of oat drink by Monday", model=model, recorded=recorded, report="…")


def test_no_model_is_named_where_none_is_asked() -> None:
    asked = site.model_asked(Settings.for_tests())

    assert asked is None
    assert view.run_label(_run("recorded", recorded=True), asked) == (
        "Run from a recording of the model's earlier answers: no live model call.")
    assert "Gemini" not in view.run_label(_run("rule-based", recorded=False), asked)


def test_another_providers_model_is_named_and_never_called_gemini() -> None:
    asked = site.model_asked(Settings.for_tests(**ENDPOINT))

    assert asked == "open-model-1"
    for run in (_run("rule-based", recorded=False), _run("recorded", recorded=True)):
        label = view.run_label(run, asked)
        assert label.startswith("open-model-1 did not answer, so this run was "), label
        assert "Gemini" not in label


def test_gemini_is_named_when_its_key_is_what_makes_a_model_be_asked() -> None:
    asked = site.model_asked(Settings.for_tests(gemini_api_key="a-key"))

    assert asked == "Gemini"
    assert view.run_label(_run("recorded", recorded=True), asked).startswith("Gemini did not answer")
