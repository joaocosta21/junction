"""A model's reading is held to the buyer's words: what is asked about whoever reads, and what may not be added
(task AG).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 20% "the model
decides nothing". The fixed reader gained rules on 14 Nov 2026 that are about the text, not about who reads it.
The general ones are applied here to an open-weights model's reading too; the fixed reader's own grammar (which
word narrows a product type, what a case holds) stays its own.

Before the model is asked (`ask_whoever_reads`), a text is asked about, with the fixed reader's own question, when
it holds:
- an order taken back or words that take an instruction back ("cancel", "ignore", "disregard", "forget"), or
  words addressed to the agent about its instructions or about approving ("approve the order yourself"): the
  buyer's text is data, and an agent never approves;
- a claim, a label, a preference or a day said with a negation or an "or"; "does not matter";
- a deadline that names no day ("within 3 days"), a date that is no date ("31 February"), a time of day, "next
  Friday" in doubt, more than one day, or a day before today;
- an amount changed without its number ("twice", "per day", "the same again");
- a number that can be read two ways ("1.250", "Ward 4 200 litres"), a quantity in a small unit ("5 dl") or a
  number with a minus ("-5 litres");
- an amount of money ("under €1,000"): the typed request has no price limit, and one is never dropped.
So an ambiguous number, "cancel" and an impossible date get the same question from a model as from the rules.

After the model answered (`added_faults`), on top of the parser's text check, nothing may be added:
- a claim must be one the text has a word for ("lactose-free", "gluten-free" by the tables of
  `tta.agent.wording`; any other claim by a word of its own name, such as "vegan" or "protein");
- a name term (a brand, a variety) must be a word of the text itself, as the buyer wrote it.
An exclusion the model adds beyond the tables is left to it: it can only send more products to a person.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from tta.agent.asking import (
    refuse_a_changed_amount,
    refuse_a_day_that_cannot_be_read,
    refuse_an_amount_of_money,
    refuse_an_unread_deadline,
    refuse_negations,
)
from tta.agent.days import named_dates
from tta.agent.faults import Fault
from tta.agent.leftover import refuse_an_order_taken_back
from tta.agent.parts import Text, part_of
from tta.agent.quantity import quantity
from tta.agent.rules_reader import ASK_A_COMING_DAY, ASK_ONE_DAY, PAST_DAY, TWO_DAYS
from tta.agent.textcheck import exclusions
from tta.agent.unread import NotReadByRules
from tta.agent.usual import without_usual
from tta.agent.wording import claims_in

# Words addressed to whoever reads, not about what to order. "Ignore", "disregard" and "forget" are already asked
# about as an order taken back (`tta.agent.leftover`).
_TO_THE_AGENT = re.compile(
    r"\bapprov\w*|\bauthori[sz]\w*|\bsign[\s-]?off\b|\binstructions?\b|\bsystem prompt\b"
    r"|\bguardrails?\b|\boverrid\w*|\bbypass\w*|\byou are now\b"
)
TO_THE_AGENT = 'it says "{said}", which is not something to order'
ASK_WHAT_IS_NEEDED = (
    'The request says "{said}". That is not read as an order, and an agent never approves an order: a person '
    "does. Nothing was ordered. Write only what is needed, each product with its quantity."
)
NOT_MATCHED = "the reading did not match the text: {why}"
CLAIM_NOT_SAID = "the text names no such claim"
TERM_NOT_SAID = "a name term that is not a word of the text"
_CLAIM_FILLERS = frozenset({"free", "from", "no", "added", "high", "low"})
_TABLE_CLAIMS = frozenset({"FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN"})  # the claims `tta.agent.wording` has words for
MIN_CLAIM_STEM = 5  # "sweet" of sweeteners, "prese" of preservatives; a shorter word is taken whole


class _Line(Protocol):
    name_terms: Sequence[str]
    required_claims: Sequence[str]


def refuse_words_to_the_agent(folded: str) -> None:
    found = _TO_THE_AGENT.search(folded)
    if found is not None:
        raise NotReadByRules(TO_THE_AGENT.format(said=found.group()), ASK_WHAT_IS_NEEDED.format(said=found.group()))


def _refuse_a_number_in_doubt(seen: Text) -> None:
    """Every part's numbers, read as the fixed reader reads them: a split number, a small unit, two readings."""
    line = 0
    for span in seen.parts:
        part = part_of(seen, span)  # raises for "Ward 4 200 litres" and "5 dl"
        if part.quantity is not None:
            line += 1
            quantity(part.quantity[0], line)  # raises for "1.250" and a number that is not one number


def ask_whoever_reads(text: str, today: date) -> None:
    """Raises `NotReadByRules`, with the question to put, for a text that is asked about whoever reads it."""
    seen = Text.of(text, today)
    _, excluding = exclusions(seen.words)
    refuse_an_order_taken_back(seen)
    refuse_words_to_the_agent(seen.folded)
    asked = seen.asked(excluding)
    refuse_an_amount_of_money(asked)
    refuse_negations(asked)
    refuse_an_unread_deadline(asked)
    refuse_a_changed_amount(without_usual(asked))
    refuse_a_day_that_cannot_be_read(asked)
    days = named_dates(seen.folded, seen.today)
    if len(days) > 1:
        raise NotReadByRules(TWO_DAYS, ASK_ONE_DAY)
    if days and days[0] < seen.today:
        raise NotReadByRules(PAST_DAY, ASK_A_COMING_DAY)
    _refuse_a_number_in_doubt(seen)


def _claim_said(claim: str, folded: str, said: frozenset[str]) -> bool:
    if claim in _TABLE_CLAIMS:
        return claim in said
    words = [word for word in claim.casefold().split("_") if word not in _CLAIM_FILLERS]
    return any(word[:MIN_CLAIM_STEM] in folded for word in words)


def added_faults(lines: Sequence[_Line], text: str) -> tuple[Fault, ...]:
    """What the reading holds that the text does not say: a claim, a name term. Each fault names its field."""
    folded = text.casefold()
    said = frozenset(code for code, _ in claims_in(folded))
    faults = []
    for index, line in enumerate(lines):
        at = f"lines[{index}]"
        if not all(_claim_said(claim, folded, said) for claim in line.required_claims):
            faults.append(Fault(f"{at}.required_claims", NOT_MATCHED.format(why=CLAIM_NOT_SAID)))
        if not all(term.casefold().strip() in folded for term in line.name_terms):
            faults.append(Fault(f"{at}.name_terms", NOT_MATCHED.format(why=TERM_NOT_SAID)))
    return tuple(faults)
