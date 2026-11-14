"""What an agent's host reads on the MCP surface says that ordering alone is a buyer setting, off by default.

Scores on the 20% "what the agent can decide alone, what needs human sign-off". After B0 the instructions and
the tool texts still said every order waits for a human; with the buyer's setting on, `AUTO` and `ORDERED`
come back.
"""

from __future__ import annotations

from tta.api.mcp_surface import INSTRUCTIONS, GatewayTools

UNTRUE_SINCE_B0 = ("submit the option for human approval", "Submit one option of an offer for human approval")


def _read(text: str | None) -> str:
    """The text as an agent reads it, without line breaks."""
    return " ".join((text or "").split())


def test_the_instructions_name_the_three_verdicts_and_the_setting() -> None:
    for phrase in ("AUTO", "APPROVAL", "BLOCK", "auto_order_enabled", "off by default", "every statement"):
        assert phrase in INSTRUCTIONS, phrase
    for untrue in UNTRUE_SINCE_B0:
        assert untrue not in INSTRUCTIONS, untrue


def test_the_offer_and_order_tools_say_when_the_agent_orders_alone() -> None:
    for tool in (GatewayTools.get_offer, GatewayTools.place_order):
        text = _read(tool.__doc__)
        assert "`AUTO`" in text and "ordering alone" in text and "every statement" in text, tool.__name__
        for untrue in UNTRUE_SINCE_B0:
            assert untrue not in text, tool.__name__
    assert "`ORDERED`" in _read(GatewayTools.place_order.__doc__)
