"""What a reading's sentence says after naming who read the text (replan P10 option a; P1 C4; B8).

Scores on the 20% "decisions logged and auditable" and the 20% "how precisely the agent matches what the buyer
actually asked for": whatever the reader took from the words beyond product, quantity and day is said to the
person in one sentence each, in this order:
- an allergen rule read as strict because none was given (`tta.agent.parser.strict_assumed`);
- 'Formula matters: the request says "for whipping".' when a line has `keep_formula`; with several lines and not
  all of them marked, "Formula matters for line 2: …";
- 'A milk substitute is read as a plant drink …' when the words say so and a line is a plant drink;
- 'The request says "the usual": …' when the words say so and a line names a product type and no product.
The notes are made from the typed request and the buyer's words, so they hold for a model's reading, a
recording's and the fixed rules' alike. `notes_of` gives them back from a reading, for a reader that rewrites the
first sentence (`tta.agent.fallback`, `tta.agent.photo`).
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.agent.labels import reading_sentence
from tta.agent.model import AnswerSource
from tta.agent.purpose import formula_uses
from tta.agent.usual import USUAL_SAID, says_usual
from tta.agent.wording import MILK_SUBSTITUTE, MILK_SUBSTITUTE_TYPE
from tta.contracts.agent import Reading
from tta.contracts.request import PurchaseRequest

FORMULA_MATTERS = "Formula matters{where}: the request says {said}."
FOR_LINES = " for line {lines}"
NO_USE_NAMED = "the text names no use for which the formula matters"
MILK_SUBSTITUTE_READ = (
    "A milk substitute is read as a plant drink (oat, soya and other plant-based drinks): a product type, not a "
    "product."
)


def _formula_note(request: PurchaseRequest, text: str) -> str | None:
    marked = [number for number, line in enumerate(request.lines, start=1) if line.keep_formula]
    said = list(dict.fromkeys(use.said for use in formula_uses(text)))
    if not marked or not said:
        return None
    every_line = len(marked) == len(request.lines)
    where = "" if every_line else FOR_LINES.format(lines=", ".join(map(str, marked)))
    return FORMULA_MATTERS.format(where=where, said=", ".join(f'"{words}"' for words in said))


def _notes(request: PurchaseRequest, text: str) -> Sequence[str]:
    notes = [_formula_note(request, text)]
    if MILK_SUBSTITUTE.search(text.casefold()) and any(
        line.product_type == MILK_SUBSTITUTE_TYPE for line in request.lines
    ):
        notes.append(MILK_SUBSTITUTE_READ)
    if says_usual(text) and any(line.product_type and not line.product_ids for line in request.lines):
        notes.append(USUAL_SAID)
    return [note for note in notes if note]


def with_notes(sentence: str, request: PurchaseRequest, text: str) -> str:
    """The sentence followed by each note the request and the buyer's words give."""
    return " ".join([sentence, *_notes(request, text)])


def notes_of(reading: Reading) -> str:
    """What the reading's sentence says after naming its source, with a leading space; empty when nothing."""
    source = reading_sentence(AnswerSource(reading.source, reading.model, reading.recorded_at))
    return reading.sentence.removeprefix(source) if reading.sentence.startswith(source) else ""
