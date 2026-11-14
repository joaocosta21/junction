"""What the fixed rules could not read, and the question a person is asked instead of a guess (replan R4, M1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": Valio Aimo said on 14 Nov
2026 that when the agent is not sure it must flag it and ask for the person's input. A text the rules cannot read
is never half-read: `NotReadByRules` names what was not read (`why`) and carries the question to put (`ask`).
With no model behind the rules the fallback answers `invalid-request` (422) with that question
(`as_question`); with a model that could not be reached it stays `supplier-unavailable`, as before.
"""

from __future__ import annotations

from tta.contracts.errors import InvalidRequest, SupplierUnavailable

RULES_CANNOT_READ = "The fixed rules cannot read this text: {why}."
ASKED = "The fixed rules did not read this request, and nothing was guessed: {why}. {ask}"
ASK_AGAIN = "Please write it again, for example: 200 litres of oat drink by Monday, no milk, strict."
READ_BY = "rule-based"


class NotReadByRules(SupplierUnavailable):
    """The rules cannot read the text. `why` names what they could not read; `ask` is the question for the
    person who wrote it."""

    def __init__(self, why: str, ask: str = ASK_AGAIN) -> None:
        super().__init__(RULES_CANNOT_READ.format(why=why))
        self.why = why
        self.ask = ask


def as_question(unread: NotReadByRules) -> InvalidRequest:
    """The same refusal as a question to the person: `invalid-request`, with the question on its own too."""
    return InvalidRequest(
        ASKED.format(why=unread.why, ask=unread.ask), question=unread.ask, not_read=unread.why, read_by=READ_BY
    )
