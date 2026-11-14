"""Client for the Valio mock API: recorder, replay, call budget, clock (SPEC section 10).

Live:   `client = ValioClient(settings)` and `client.clock` for the `Clock` port;
        `client.calls_remaining` says how much of the call budget is left.
Replay: `replay = ReplayGateway.from_settings(settings)` and `replay.clock`.
"""

from tta.valio.budget import CallBudget
from tta.valio.client import ValioClient
from tta.valio.clock import LiveClock, PinnedClock
from tta.valio.parsing import load_body, parse_availability_body, parse_price_body
from tta.valio.recorder import Recorder
from tta.valio.replay import ReplayGateway

__all__ = [
    "CallBudget",
    "LiveClock",
    "PinnedClock",
    "Recorder",
    "ReplayGateway",
    "ValioClient",
    "load_body",
    "parse_availability_body",
    "parse_price_body",
]
