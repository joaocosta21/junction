"""A run the fixed rules read and made never reads as a model's run on the page (task FALLBACK-1)."""

from __future__ import annotations

import pytest

from tta.contracts.agent import AgentRun
from tta.ui import view


def _run(model: str, recorded: bool) -> AgentRun:
    return AgentRun(text="300 litres of oat drink by Monday", model=model, recorded=recorded, report="…")


@pytest.mark.parametrize(
    ("live_model", "expected"),
    [(True, view.RUN_BY_RULES_AFTER_A_MODEL.format(model=view.THE_MODEL)), (False, view.RUN_BY_RULES_WITHOUT_A_MODEL)],
)
def test_a_rule_based_run_says_fixed_rules_made_it(live_model: bool, expected: str) -> None:
    label = view.run_label(_run("rule-based", recorded=False), live_model)

    assert label == expected
    assert "fixed rules, not by a model" in label


def test_a_live_model_run_still_names_its_model() -> None:
    assert "gemini-3.6-flash" in view.run_label(_run("gemini-3.6-flash", recorded=False), live_model=True)
