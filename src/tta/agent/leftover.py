"""The words of a part with no quantity that nothing read (review of 14 Nov 2026, finding S3).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 20% "guardrails":
a part of the text with no quantity speaks for the request ("by Monday", "no milk", "strict"), and its other words
used to be checked by nothing. "500 kg of butter, unsalted" was read as plain butter, and "200 litres of milk,
cancel the order" as an order for 200 litres. Nothing is half-read: every word of such a part must be one the
rules read (a claim, a label, a day, an exclusion, a preference, a brand, a use), a plain word ("please", "by",
"the order"), or the brief's own closing sentence ("Find an option that meets our requirements based on price and
availability"). A variant the rules know for the product type of the line right before it ("unsalted", "whole":
`tta.agent.variants`) is that line's name term. Anything else is asked about, quoted to the person. A word that
takes an order back or changes it ("cancel", "ignore") is asked about wherever it stands. The word lists are ours.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence

from tta.agent.days import date_spans
from tta.agent.parts import NOT_A_TERM, Part, Text
from tta.agent.purpose import is_use_word, purpose_spans
from tta.agent.unread import NotReadByRules
from tta.agent.variants import named_variants, variant_named, variant_spans
from tta.contracts.common import JsonDict

# Words that ask for nothing: greetings and thanks, and the words around a day, a rule or a product number.
PLAIN_WORDS = NOT_A_TERM | frozenset({
    "please", "thanks", "thank", "you", "kindly", "hi", "hello", "hey", "dear", "regards", "cheers", "kiitos",
    "tack", "i", "we", "us", "it", "is", "are", "be", "must", "should", "day", "after", "latest", "later", "than",
    "before", "until", "till", "from", "delivery", "needed", "required", "arriving", "rule", "rules", "allergen",
    "allergens", "product", "products", "number", "no", "nr", "id", "item", "article", "all", "everything", "as",
    "vain", "tiedot", "tuote", "tuotenumero", "most", "with",
    # around an exclusion or a use the rules read: "the patient is allergic: sesame", "may not contain milk or soy"
    "not", "may", "can", "cannot", "t", "have", "has", "contain", "contains", "nothing", "or", "patient", "patients",
    "guest", "guests",
})
# The brief's own sentence, which asks for what every offer already does (CHALLENGE.md).
_BRIEF = re.compile(
    r"\bfind\s+(?:an?\s+option|options)\s+that\s+meets?\s+(?:our|the|my)\s+requirements"
    r"(?:\s+based\s+on\s+price(?:\s+and\s+availability)?)?|\bavailability\b"
)
# An order taken back or changed: never an order line without a person's answer.
_TAKEN_BACK = re.compile(
    r"\b(?:cancel(?:s|led|ed|ling|ing)?|ignor(?:e|es|ed|ing)|disregard|forget|void|undo|scrap|delete|skip)\b"
)

ALSO_SAYS = 'it also says "{said}", which the rules did not read'
ASK_A_PROPERTY = (
    'The request also says "{said}", which the rules did not read. Is it a property of the product? Then write it '
    'before the product: "{said} {product}".'
)
ASK_WHAT_IS_MEANT = (
    'The request also says "{said}", which the rules did not read. What does it ask for? Write only what is '
    'needed, each product with its quantity; a property of the product goes before it, for example "unsalted '
    'butter".'
)
TAKEN_BACK = 'it says "{said}", and the rules only read what to order'
ASK_WHAT_TO_ORDER = (
    'The request says "{said}". Is an order to be changed or cancelled? Nothing was ordered: the rules only read '
    "what is needed now. Write only that, each product with its quantity."
)


def refuse_an_order_taken_back(seen: Text) -> None:
    """"Cancel the order", "ignore my last order": asked about wherever it stands."""
    found = _TAKEN_BACK.search(seen.folded)
    if found is not None:
        raise NotReadByRules(TAKEN_BACK.format(said=found.group()), ASK_WHAT_TO_ORDER.format(said=found.group()))


def unread_words(seen: Text, part: Part, read: Collection[int], product_type: str | None) -> list[int]:
    """The words of this part that nothing read, by their index. `read` are the words the rules already took
    for something; `product_type` is the type of the line the part belongs to."""
    spans = [match.span() for match in _BRIEF.finditer(seen.folded)]
    spans += [*date_spans(seen.folded), *purpose_spans(seen.folded), *variant_spans(product_type, seen.folded)]
    in_a_span = {index for span in spans for index in seen.indices_in(span)}
    unread = [index for index in part.indices
              if index not in read and index not in in_a_span and seen.words[index] not in PLAIN_WORDS]
    # "for cakes and desserts": a use named on its own is read; beside another unread word it is quoted with it
    return [] if all(is_use_word(seen.words[index]) for index in unread) else unread


def not_read(seen: Text, unread: Sequence[int], product: str | None) -> NotReadByRules:
    """The question for the words nothing read, quoting them as the buyer wrote them."""
    last = unread[-1]
    said = seen.folded[seen.starts[unread[0]]:seen.starts[last] + len(seen.words[last])]
    one_word = len(unread) == 1 and product is not None
    ask = ASK_A_PROPERTY.format(said=said, product=product) if one_word else ASK_WHAT_IS_MEANT.format(said=said)
    return NotReadByRules(ALSO_SAYS.format(said=said), ask)


def parts_per_line(parts: Sequence[Part]) -> dict[int, tuple[Part, ...]]:
    """Per line number, its own part and each part with no quantity right after it; such a part before the first
    line belongs to the first line."""
    owned: dict[int, list[Part]] = {}
    lines_before = 0
    for part in parts:
        lines_before += part.quantity is not None
        owned.setdefault(max(lines_before, 1), []).append(part)
    return {number: tuple(members) for number, members in owned.items()}


def _settled(seen: Text, line: JsonDict, part: Part, read: Collection[int]) -> JsonDict:
    """The line with what this quantity-less part adds to it. Raises `NotReadByRules` for words nothing read."""
    key = line["product_type"]
    unread = unread_words(seen, part, read, key)
    if not unread:
        return line
    term = variant_named(key, [seen.words[index] for index in unread])
    already = named_variants(key) & {name.casefold() for name in line["name_terms"]}
    if term is None or already or line["product_ids"]:
        raise not_read(seen, unread, key.replace("_", " ") if key else None)
    return {**line, "name_terms": [*line["name_terms"], term]}


def with_the_rest_settled(
    seen: Text, lines: Sequence[JsonDict], owned: Mapping[int, Sequence[Part]], read: Collection[int]
) -> list[JsonDict]:
    """The lines after every part with no quantity was accounted for: a variant the rules know becomes a name
    term of the line the part belongs to, and any other unread word is asked about."""
    settled = list(lines)
    for number, parts in owned.items():
        for part in parts:
            if part.quantity is None and number <= len(settled):
                settled[number - 1] = _settled(seen, settled[number - 1], part, read)
    return settled
