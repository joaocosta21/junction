"""What a reading's sentence says after naming who read the text (replan P10 option a; P1 C4; B8).

Scores on the 20% "decisions logged and auditable" and the 20% "how precisely the agent matches what the buyer
actually asked for": whatever the reader took from the words beyond product, quantity and day is said to the
person in one sentence each, in this order:
- an allergen rule read as strict because none was given (`tta.agent.parser.strict_assumed`);
- for a reading of the fixed rules, how a comma in a quantity was read: '"1,250" is read as 1250 (a comma before
  three digits groups thousands here); for 1.25 write "1.25".', or as a decimal comma ("1,5" is 1.5)
  (`tta.agent.quantity`);
- '"before friday" is read as: by Thursday 19 November.' when the day follows "before" (`tta.agent.days`);
- 'The brand "Arla" is required.' when a line's name terms hold a brand of the catalog (`tta.agent.brands`);
- 'Cream "for whipping" is read as whipping cream.' when a use narrowed the product type (`tta.agent.variants`);
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

from tta.agent.brands import NO_BRANDS, Brands
from tta.agent.days import before_days
from tta.agent.labels import reading_sentence
from tta.agent.model import AnswerSource
from tta.agent.purpose import formula_uses
from tta.agent.quantity import comma_note, comma_readings
from tta.agent.usual import USUAL_SAID, says_usual
from tta.agent.variants import variant_for
from tta.agent.wording import MILK_SUBSTITUTE, MILK_SUBSTITUTE_TYPE
from tta.contracts.agent import Reading
from tta.contracts.request import PurchaseRequest

FORMULA_MATTERS = "Formula matters{where}: the request says {said}."
FOR_LINES = " for line {lines}"
ONE_BRAND = 'The brand "{brand}" is required.'
SEVERAL_BRANDS = "The brands {brands} are required."
BEFORE_READ = '"{said}" is read as: by {day}.'
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


def _brand_note(request: PurchaseRequest, brands: Brands) -> str | None:
    known = brands.spellings()
    named = list(dict.fromkeys(term for line in request.lines for term in line.name_terms if term in known))
    if len(named) <= 1:
        return ONE_BRAND.format(brand=named[0]) if named else None
    quoted = [f'"{brand}"' for brand in named]
    return SEVERAL_BRANDS.format(brands=f"{', '.join(quoted[:-1])} and {quoted[-1]}")


def _variant_notes(request: PurchaseRequest, text: str) -> list[str]:
    """One sentence per variant a use named and a line carries as a name term."""
    found = [variant for line in request.lines
             if (variant := variant_for(line.product_type, text)) is not None and variant.term in line.name_terms]
    return list(dict.fromkeys(variant.sentence for variant in found))


def _comma_notes(request: PurchaseRequest, text: str) -> list[str]:
    """One sentence per quantity of the request that the text writes with a comma."""
    quantities = {line.quantity for line in request.lines}
    notes = [comma_note(run, value, thousands) for run, value, thousands in comma_readings(text)
             if value in quantities]
    return list(dict.fromkeys(notes))


def _before_note(request: PurchaseRequest, text: str) -> str | None:
    """'"before friday" is read as: by Thursday 19 November.' when the day the goods are needed by follows
    "before": the day before the one named."""
    if request.needed_by is None:
        return None
    said = [words for words, _ in before_days(text, request.needed_by)]
    day = request.needed_by
    return BEFORE_READ.format(said=said[0], day=f"{day:%A} {day.day} {day:%B}") if len(said) == 1 else None


def _notes(request: PurchaseRequest, text: str, brands: Brands, *, by_rules: bool) -> Sequence[str]:
    # How a comma was read is the fixed rules' own choice (`tta.agent.quantity`): a model's reading does not say it.
    notes = [*(_comma_notes(request, text) if by_rules else ()), _before_note(request, text),
             _brand_note(request, brands),
             *_variant_notes(request, text), _formula_note(request, text)]
    if MILK_SUBSTITUTE.search(text.casefold()) and any(
        line.product_type == MILK_SUBSTITUTE_TYPE for line in request.lines
    ):
        notes.append(MILK_SUBSTITUTE_READ)
    if says_usual(text) and any(line.product_type and not line.product_ids for line in request.lines):
        notes.append(USUAL_SAID)
    return [note for note in notes if note]


def with_notes(
    sentence: str, request: PurchaseRequest, text: str, brands: Brands = NO_BRANDS, *, by_rules: bool = False
) -> str:
    """The sentence followed by each note the request and the buyer's words give. `brands` are the brands the
    reader knows: a name term that is one of them is said to be required. `by_rules`: the fixed rules read it."""
    return " ".join([sentence, *_notes(request, text, brands, by_rules=by_rules)])


def notes_of(reading: Reading) -> str:
    """What the reading's sentence says after naming its source, with a leading space; empty when nothing."""
    source = reading_sentence(AnswerSource(reading.source, reading.model, reading.recorded_at))
    return reading.sentence.removeprefix(source) if reading.sentence.startswith(source) else ""
