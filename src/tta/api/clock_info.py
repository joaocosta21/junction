"""Which clock is in force, for `GET /healthz` and for a page's banner.

Scores on the 15% "clear visibility of assumptions": the instant every order cut-off is compared with is a choice
in replay, and the gateway says which instant it is, what it rests on and whether somebody set it.
Valio Aimo, 14 Nov 2026: "this is all static data so we can chose the date". When the recording joins a later one
(task CK), the sentence says so too, and `later_recordings` names each with its own server time and product count.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from tta.audit.phrases import moment
from tta.config import Settings
from tta.contracts.common import ClockBasis, DataSource
from tta.contracts.ports import Clock
from tta.valio import ReplayGateway

AUDIT_KEEPS_REAL_TIME = "The audit trail is stamped with the real time."
RECORDING = (
    "Clock pinned to {now}, the moment Valio Aimo's data was recorded. Order deadlines are judged against it. "
    + AUDIT_KEEPS_REAL_TIME
)
DEMO_SETTING = (
    "Demo clock: {now}, set with TTA_DEMO_CLOCK. Order deadlines are judged against it. We chose it: Valio Aimo "
    "said on 14 Nov 2026 that its test data is static. The data was recorded on {recorded_at}. "
    + AUDIT_KEEPS_REAL_TIME
)
SUPPLIER = "The clock follows the server time of Valio Aimo's answers: {now}. " + AUDIT_KEEPS_REAL_TIME
NOT_HONOURED = " TTA_DEMO_CLOCK is set and is not honoured: a demo clock applies in replay only."


class HealthLaterRecording(BaseModel):
    """A recording joined to the first one: its name, its own server time, and how many products it answers for."""

    model_config = ConfigDict(frozen=True)

    name: str
    recorded_at: datetime
    product_count: int


class HealthClock(BaseModel):
    """The data clock: the instant every order cut-off and every "by Monday" is judged against."""

    model_config = ConfigDict(frozen=True)

    now: datetime
    basis: ClockBasis  # recording, supplier or demo_setting
    demo_clock_set: bool  # whether TTA_DEMO_CLOCK is set, honoured or not
    recorded_at: datetime | None  # replay: the server time of the recording itself
    sentence: str
    later_recordings: tuple[HealthLaterRecording, ...] = ()  # replay: recordings joined to the first one


def describe_clock(settings: Settings, clock: Clock, replay: ReplayGateway) -> HealthClock:
    """What the clock reads now and why. Asks nothing of the supplier."""
    now = clock.now()
    is_set = settings.tta_demo_clock is not None
    if settings.tta_mode is not DataSource.REPLAY:
        sentence = SUPPLIER.format(now=moment(now)) + (NOT_HONOURED if is_set else "")
        return HealthClock(
            now=now, basis=ClockBasis.SUPPLIER, demo_clock_set=is_set, recorded_at=None, sentence=sentence
        )
    basis = replay.time_basis
    template = DEMO_SETTING if basis is ClockBasis.DEMO_SETTING else RECORDING
    sentence = template.format(now=moment(now), recorded_at=moment(replay.recorded_at))
    later = tuple(
        HealthLaterRecording(name=each.name, recorded_at=each.recorded_at, product_count=each.product_count)
        for each in replay.later_recordings
    )
    return HealthClock(
        now=now, basis=basis, demo_clock_set=is_set, recorded_at=replay.recorded_at, later_recordings=later,
        sentence=sentence if replay.join_sentence is None else f"{sentence} {replay.join_sentence}",
    )
