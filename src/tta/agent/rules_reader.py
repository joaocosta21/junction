"""The rule-based reader: common purchase sentences read by fixed rules when no model answers (task FALLBACK-1).

Scores on the 30% "working end-to-end demo": with Gemini out of reach and no recording of a sentence, the gateway
used to answer `supplier-unavailable`. These rules read the common shapes, say so (`ReadingSource.RULE_BASED`),
and read nothing else. Deterministic: no model, no network.
- Lines are split on "and" ("ja", "och"), commas, semicolons, sentence ends and new lines. A part with a quantity
  is a line; any other part speaks for the whole request ("no milk", "by Monday").
- A quantity is digits followed by a unit word of the text check (`tta.agent.textcheck`): "1,000", "1 000", "1000",
  "1.5", "1,5", read by `tta.agent.quantity`. A quantity is never guessed: a part that names a product with no
  digits and unit, and a number anywhere that is not a quantity, a date or a product number, is not read.
- The product is a key of the product-type table ("plant_drink" as "plant drink") or one of its name terms
  ("drink", "juoma"), in English, Finnish or Swedish where the table has them (`catalog/product_types.yaml`): the
  word itself, its plural, or, for a term of five letters or more, the term with an ending ("juomaa", "drinks";
  never "buttermilk" for butter). A type whose exclude term the line holds is not named ("sour milk" is not
  milk); one named inside a longer one is the longer ("beef chuck", "coffee milk"). Two types left: not read.
  The one word right before the type narrows it ("oat drink"); a word right after it that the rules do not know
  is asked about ("milk chocolate"). A 6-digit product number names a product too.
- A word of a line that is a brand of the catalog ("Arla", "Arla Pro": `tta.agent.brands`) is a name term the
  product must carry, and the reading says so. Not on a line that names its product by number.
- A use that names a variant of the type ("cream for whipping", "cream for cooking": `tta.agent.variants`) is
  the name term the product's own name gives ("whipping cream").
- Claims, certificate labels, preferences and strictness are the words of `tta.agent.wording`; exclusions, confirmed
  data and product numbers those of the text check; days those of `tta.agent.days`. A claim or a label said in a
  line is that line's, said elsewhere every line's. Every exclusion is every line's, as the text check holds it.
  An exclusion with no strictness word stays without one: the parser reads it as strict when the profile sets no
  rule either, and says so, as it does for a model.
- A use for which the formula matters ("cream for whipping", "butter for baking": `tta.agent.purpose`) sets
  `keep_formula` on the line whose part says it; said in a part with no quantity, on the line right before it
  (the first line when none is before). A product's own name ("whipping cream") and "not for baking" set nothing.
- "The usual" is never turned into a product or a number (`tta.agent.usual`): with a type and a quantity the line
  is the plain type, with no quantity or no type it is asked about. "A milk substitute" is the type plant drink.
- A part with no quantity is read whole or asked about (`tta.agent.leftover`): "500 kg of butter, unsalted" is
  unsalted butter, "200 litres of milk, urgent" and "…, cancel the order" are asked about.
- Not read: any other substitute ("a butter substitute"), an exclusion of something the allergen table lacks
  ("no sugar"),
  two days, a day before today, two preferences, both "strict" and "declared only", and every wording of
  `tta.agent.asking` (a negation, a deadline in days or weeks, an allergen named outside an exclusion, a case,
  a box, a carton, a pallet or a portion, an amount of money), and a number with a minus (`tta.agent.quantity`).
- A quantity in packs, pieces or units is read as sales units, and a drink asked for by the kilogram is read by
  weight: the reading says both (`tta.agent.measures`; review C2-8). Nothing about a unit is read without a word.
- A text in Finnish or Swedish that the rules cannot read is answered as such: they read English only for now
  (`tta.agent.language`). What they do read of the two languages (unit words, weekdays, exclusions, the type
  table's own terms) is read as before.
The answer has the model's shape, so the parser's text check and conversion run on it unchanged: `RuleModel`
implements `AgentModel`. A text these rules cannot read is refused with `NotReadByRules` (`tta.agent.unread`),
which names what they could not read and carries the question to ask the person: nothing is half-read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from tta.agent.asking import (
    refuse_a_changed_amount,
    refuse_a_day_that_cannot_be_read,
    refuse_a_deadline_with_no_day,
    refuse_a_pack_of_unknown_size,
    refuse_an_allergen_left_unsaid,
    refuse_an_amount_of_money,
    refuse_an_unread_deadline,
    refuse_negations,
    unknown_product_word,
)
from tta.agent.brands import NO_BRANDS, Brands
from tta.agent.days import day_spans, named_dates
from tta.agent.language import in_another_language
from tta.agent.leftover import parts_per_line, refuse_an_order_taken_back, with_the_rest_settled
from tta.agent.parts import NOT_A_TERM, Part, Text, part_of, with_lone_product_numbers
from tta.agent.purpose import formula_matters
from tta.agent.quantity import quantity
from tta.agent.textcheck import (
    CONFIRMED,
    exclusion_triggers,
    exclusions,
    unit_of,
)
from tta.agent.typenames import TypeNames, type_names, types_named
from tta.agent.unread import RULES_CANNOT_READ, NotReadByRules
from tta.agent.usual import says_usual_amount, usual_amount, usual_with_no_product, usual_words, without_usual
from tta.agent.variants import variant_for, variant_named
from tta.agent.wording import (
    MILK_SUBSTITUTE,
    MILK_SUBSTITUTE_TYPE,
    SUBSTITUTE,
    Span,
    claims_in,
    labels_in,
    preferences_in,
    strictness_in,
)
from tta.contracts.common import JsonDict, Unit
from tta.contracts.request import MAX_REQUEST_LINES

__all__ = ["RULES_CANNOT_READ", "NotReadByRules", "RuleReader", "TypeNames", "type_names"]

MIN_NARROWING_LETTERS = 3
_ALLOWED_AFTER_NO = frozenset({"later"})  # "no later than Monday" names a day, not an exclusion
# Words that may stand right after the product type without naming another product ("milk for baking", "milk
# delivered Monday"). Any other word there that says nothing the rules read is asked about ("milk chocolate").
MAY_FOLLOW = NOT_A_TERM | frozenset({
    "is", "are", "must", "should", "shall", "may", "can", "cannot", "not", "no", "without", "free", "which", "that",
    "if", "as", "from", "per", "each", "every", "before", "until", "till", "than", "later", "latest", "delivery",
    "needed", "required", "arriving", "we", "i", "it", "they", "nothing", "t", "or", "x", "today", "now", "product",
})


NOTHING_TO_READ = "it gives no quantity in digits with a unit, such as 200 litres"
NO_QUANTITY_FOR = "{what} is named with no quantity in digits and unit"
NO_PRODUCT = "line {line} names no product type of the table and no 6-digit product number"
TWO_TYPES = "line {line} names more than one product type ({types})"
TWO_QUANTITIES = "line {line} gives more than one quantity; separate lines with and, a comma or a semicolon"
ANOTHER_NUMBER = "line {line} gives a number besides its quantity ({number})"
A_NUMBER_ALONE = 'it gives a number that is not a quantity with a unit ("{number}")'
TOO_MANY_LINES = "it asks for more than {most} lines"
A_SUBSTITUTE = "it asks for a substitute, which only a model reads"
UNREAD_EXCLUSION = 'it excludes something the allergen table does not name ("{words}")'
TWO_DAYS = "it names more than one day"
PAST_DAY = "it names a day before today"
TWO_PREFERENCES = "it names more than one preference ({names})"
TWO_STRICTNESSES = "it says both strict and declared only"

# The question that goes with each refusal: what the person is asked instead of a guess.
ASK_HOW_MUCH_OF_WHAT = "How much is needed, and of what? For example: 200 litres of oat drink by Monday."
ASK_HOW_MUCH = (
    "What quantity of {what} is needed? Write the number in digits with litres, kilograms or packs, for example 200 "
    "litres."
)
ASK_WHICH_PRODUCT = (
    "Which product is needed on line {line}? Name a product type the gateway knows, such as milk, cream or oat "
    "drink, or give the 6-digit product number."
)
ASK_ONE_PRODUCT = "Which one is needed on line {line}? For both, write each product with its own quantity."
ASK_COFFEE_MILK = 'Is it milk for coffee? Then write "coffee milk". For both, write each with its own quantity.'
ASK_EACH_QUANTITY = "Which quantity belongs to which product? Write each product with its own quantity and unit."
ASK_WHAT_NUMBER = (
    "What does {number} stand for? Write each quantity with its unit, for example 200 litres, and leave other "
    "numbers out."
)
ASK_FEWER_LINES = "Which {most} lines come first? Send the others as another request."
ASK_WHICH_INSTEAD = "Which product should be offered instead? Name it, for example oat drink or soya drink."
ASK_WHAT_TO_EXCLUDE = (
    'What must be left out? The rules read allergens by their common names, for example "no milk", "no gluten", '
    '"no nuts", "no soy".'
)
ASK_ONE_DAY = "By which one day are the goods needed?"
ASK_A_COMING_DAY = "By which day are the goods needed? Name today or a later day."
ASK_ONE_PREFERENCE = "Which one matters most?"
ASK_ONE_STRICTNESS = "Which allergen rule applies: strict, or declared only?"
COFFEE_AND_MILK = frozenset({"coffee", "milk"})


@dataclass(frozen=True)
class _Context:
    """What every line of one text shares."""

    seen: Text
    excluding: frozenset[int]  # the words that say an exclusion
    used: frozenset[int]  # the words that already say something (`_used`)
    shared: tuple[Span, ...]  # the parts that speak for every line
    excluded: tuple[str, ...]  # the GS1 codes the text excludes
    strictness: str | None
    usual: frozenset[int]  # the words that say "the usual"
    formula: frozenset[int]  # the numbers of the lines for which the words say the formula matters
    brands: Mapping[int, str]  # the words that are part of a brand, with the brand's spelling in the catalog
    said: Mapping[int, str]  # per line number, its own words and those of the parts with no quantity after it
    owned: Mapping[int, Sequence[Part]]  # per line number, its own part and the parts with no quantity after it


class RuleReader:
    """Reads a text into the model's proposal by the rules above, or raises `NotReadByRules`."""

    def __init__(self, table: Sequence[TypeNames], brands: Brands = NO_BRANDS) -> None:
        self._table = tuple(table)
        self._brands = brands
        self._reads_milk_substitute = any(entry.key == MILK_SUBSTITUTE_TYPE for entry in self._table)

    def proposal(self, text: str, today: date) -> JsonDict:
        """The proposal for a text the rules read. Raises `NotReadByRules` otherwise: for a text in Finnish or
        Swedish, the answer that the rules read English only (`tta.agent.language`), whatever stopped them."""
        try:
            return self._proposal(text, today)
        except NotReadByRules as unread:
            elsewhere = in_another_language(text)
            if elsewhere is None:
                raise
            raise elsewhere from unread

    def _proposal(self, text: str, today: date) -> JsonDict:
        seen = Text.of(text, today)
        excluded, excluding = exclusions(seen.words)
        _refuse_what_is_not_read(seen, excluding, milk_substitute=self._reads_milk_substitute)
        parts = with_lone_product_numbers(seen, [part_of(seen, span) for span in seen.parts])
        usual = usual_words(seen.asked(excluding))
        if usual and not any(self._named(seen, part, excluding) or part.product_ids for part in parts):
            raise usual_with_no_product()
        for part in parts:
            if part.quantity is None:
                self._refuse_a_product_without_quantity(seen, part, excluding, usual)
        lines = [part for part in parts if part.quantity is not None]
        if not lines:
            raise NotReadByRules(NOTHING_TO_READ, ASK_HOW_MUCH_OF_WHAT)
        if len(lines) > MAX_REQUEST_LINES:
            raise NotReadByRules(TOO_MANY_LINES.format(most=MAX_REQUEST_LINES),
                                 ASK_FEWER_LINES.format(most=MAX_REQUEST_LINES))
        used = _used(seen, excluding) | usual
        brands = self._brands.found(seen.words, skipping=used)
        refuse_a_deadline_with_no_day(seen.asked(excluding), used | frozenset(brands))
        owned = parts_per_line(parts)
        said = {number: " ; ".join(seen.folded[part.span[0]:part.span[1]] for part in members)
                for number, members in owned.items()}  # no wording reads across the sign
        context = _Context(
            seen=seen, excluding=excluding, used=used | frozenset(brands), usual=usual, brands=brands, said=said,
            owned=owned,
            formula=frozenset(number for number, words in said.items() if formula_matters(words)),
            shared=tuple(part.span for part in parts if part.quantity is None), excluded=tuple(sorted(excluded)),
            strictness=next((strictness.value for strictness, _ in strictness_in(seen.folded)), None),
        )
        read = [self._line(context, number, line) for number, line in enumerate(lines, start=1)]
        read = with_the_rest_settled(seen, read, owned, context.used)
        rule_words = {index for _, span in strictness_in(seen.folded) for index in seen.indices_in(span)}
        refuse_an_allergen_left_unsaid(  # "declared allergens only" says the rule, not an allergen
            seen.asked(excluding), self._product_words(seen, lines, excluding) | rule_words
        )
        return {**_request_facts(seen), "lines": read}

    def _named(self, seen: Text, part: Part, excluding: frozenset[int]) -> dict[str, frozenset[int]]:
        """The types the part names, leaving out the words of an exclusion: "no milk" names no milk. "A milk
        substitute" names the plant drink, not milk, when the table holds that type."""
        stand_in = _milk_substitute_words(seen, part) if self._reads_milk_substitute else frozenset()
        words = [(index, seen.words[index]) for index in part.indices if index not in excluding | stand_in]
        named = types_named(words, self._table)
        if not stand_in:
            return named
        return {MILK_SUBSTITUTE_TYPE: named.get(MILK_SUBSTITUTE_TYPE, frozenset()) | stand_in,
                **{key: covered for key, covered in named.items() if key != MILK_SUBSTITUTE_TYPE}}

    def _refuse_a_product_without_quantity(
        self, seen: Text, part: Part, excluding: frozenset[int], usual: frozenset[int]
    ) -> None:
        what = next(iter(sorted(self._named(seen, part, excluding))), None) or next(iter(part.product_ids), None)
        if what is not None:
            name = what.replace("_", " ")
            if usual & set(part.indices) or says_usual_amount(seen.asked(excluding)):
                raise usual_amount(name)
            raise NotReadByRules(NO_QUANTITY_FOR.format(what=name), ASK_HOW_MUCH.format(what=name))
        if part.other_numbers:  # "200 of them", "Ward 4": a number in a part that gives no quantity
            number = part.other_numbers[0]
            raise NotReadByRules(A_NUMBER_ALONE.format(number=number), ASK_WHAT_NUMBER.format(number=number))

    def _product_words(self, seen: Text, lines: Sequence[Part], excluding: frozenset[int]) -> frozenset[int]:
        """The words that name a line's product: its type's own words and the one word that narrows it."""
        words: set[int] = set()
        for part in lines:
            for covered in self._named(seen, part, excluding).values():
                words |= covered | {min(covered) - 1}
        return frozenset(words)

    def _line(self, context: _Context, number: int, part: Part) -> JsonDict:
        if part.quantities > 1:
            raise NotReadByRules(TWO_QUANTITIES.format(line=number), ASK_EACH_QUANTITY)
        if part.other_numbers:
            other = part.other_numbers[0]
            raise NotReadByRules(ANOTHER_NUMBER.format(line=number, number=other),
                                 ASK_WHAT_NUMBER.format(number=other))
        named = self._named(context.seen, part, context.excluding)
        if len(named) > 1:
            ask = ASK_COFFEE_MILK if set(named) == COFFEE_AND_MILK else ASK_ONE_PRODUCT.format(line=number)
            raise NotReadByRules(TWO_TYPES.format(line=number, types=", ".join(sorted(named))), ask)
        if not named and not part.product_ids:
            if context.usual & set(part.indices):
                raise usual_with_no_product()
            raise NotReadByRules(NO_PRODUCT.format(line=number), ASK_WHICH_PRODUCT.format(line=number))
        key, covered = next(iter(named.items()), (None, frozenset[int]()))
        digits, unit = part.quantity or ("", Unit.UNIT)
        refuse_a_pack_of_unknown_size(number, digits, part.unit_word)
        _refuse_an_unknown_word_after(context, number, part, covered)
        folded = context.seen.folded
        return {
            "product_type": key, "product_ids": list(part.product_ids),
            # A product number names the product exactly: no word narrows it further.
            "name_terms": [] if part.product_ids else _name_terms(context, number, part, key, covered),
            "required_claims": _said_for(claims_in(folded), part.span, context.shared),
            "quantity": str(quantity(digits, number)), "unit": unit.value,
            "exclude_allergens": list(context.excluded), "allergen_strictness": context.strictness, "pack": None,
            "required_labels": _said_for(labels_in(folded), part.span, context.shared),
            "keep_formula": True if number in context.formula else None,
        }


def _within(position: int, span: Span) -> bool:
    return span[0] <= position < span[1]


def _said_for(found: Sequence[tuple[str, Span]], line: Span, shared: Sequence[Span]) -> list[str]:
    """The codes said in this line or in a part that speaks for every line, each once, in the order said."""
    codes = [code for code, (start, _) in found if _within(start, line) or any(_within(start, at) for at in shared)]
    return list(dict.fromkeys(codes))


def _milk_substitute_words(seen: Text, part: Part) -> frozenset[int]:
    """The words of "milk substitute" or "substitute for milk" in this part."""
    spans = [match.span() for match in MILK_SUBSTITUTE.finditer(seen.folded)]
    return frozenset(index for index in part.indices
                     if any(_within(seen.starts[index], span) for span in spans))


def _name_terms(context: _Context, number: int, part: Part, key: str | None, covered: frozenset[int]) -> list[str]:
    """The line's brands, the one word that narrows its type, and the variant its use names, each once."""
    words = [index for member in context.owned.get(number, (part,)) for index in member.indices]
    brands = [context.brands[index] for index in words if index in context.brands]
    narrowing = _narrowing(context, part, min(covered, default=None), context.used | covered)
    if narrowing and (index := context.seen.words.index(narrowing[0], part.indices[0])) - 1 in part.indices:
        # "semi-skimmed milk": the two words before the type are one variant, not the plain "skimmed"
        narrowing = [variant_named(key, (context.seen.words[index - 1], narrowing[0])) or narrowing[0]]
    variant = variant_for(key, context.said.get(number, ""), narrowing)
    return list(dict.fromkeys([*brands, *narrowing, *([variant.term] if variant else [])]))


def _refuse_what_is_not_read(seen: Text, excluding: frozenset[int], *, milk_substitute: bool) -> None:
    other_substitute = MILK_SUBSTITUTE.sub("", seen.folded) if milk_substitute else seen.folded
    if SUBSTITUTE.search(other_substitute):
        raise NotReadByRules(A_SUBSTITUTE, ASK_WHICH_INSTEAD)
    refuse_an_order_taken_back(seen)
    asked = seen.asked(excluding)
    refuse_an_amount_of_money(asked)  # before "no more than" is taken for an exclusion and "within" for a deadline
    refuse_negations(asked)
    refuse_an_unread_deadline(asked)
    refuse_a_changed_amount(without_usual(asked))  # "the same as usual" is not "the same again"
    claimed = {index for _, span in claims_in(seen.folded) for index in seen.indices_in(span)}
    dated = {index for span in day_spans(seen.folded, seen.today) for index in seen.indices_in(span)}  # "by Fri"
    for index in sorted(exclusion_triggers(seen.words) - excluding - claimed - dated):
        following = seen.words[index + 1] if index + 1 < len(seen.words) else ""
        if following not in _ALLOWED_AFTER_NO:
            said = " ".join(seen.words[max(index - 1, 0):index + 2])
            raise NotReadByRules(UNREAD_EXCLUSION.format(words=said), ASK_WHAT_TO_EXCLUDE)
    refuse_a_day_that_cannot_be_read(asked)
    days = named_dates(seen.folded, seen.today)
    if len(days) > 1:
        raise NotReadByRules(TWO_DAYS, ASK_ONE_DAY)
    if days and days[0] < seen.today:
        raise NotReadByRules(PAST_DAY, ASK_A_COMING_DAY)
    preferences = {preference for preference, _ in preferences_in(seen.folded)}
    if len(preferences) > 1:
        raise NotReadByRules(TWO_PREFERENCES.format(names=", ".join(sorted(preferences))), ASK_ONE_PREFERENCE)
    if len({strictness for strictness, _ in strictness_in(seen.folded)}) > 1:
        raise NotReadByRules(TWO_STRICTNESSES, ASK_ONE_STRICTNESS)


def _refuse_an_unknown_word_after(context: _Context, number: int, part: Part, covered: frozenset[int]) -> None:
    """"Milk chocolate": the word right after the type's own words, when it says nothing the rules read."""
    seen = context.seen
    after = max(covered, default=-1) + 1
    if not covered or after not in part.indices or after in context.used:
        return
    last_end = seen.starts[after - 1] + len(seen.words[after - 1])
    word = seen.words[after]
    if word in MAY_FOLLOW or seen.folded[last_end:seen.starts[after]].strip(" -"):
        return  # a plain word, or digits or a sign in between: not one product name
    known = " ".join(seen.words[index] for index in sorted(covered))
    raise unknown_product_word(number, known, word)


def _used(seen: Text, excluding: frozenset[int]) -> frozenset[int]:
    """The words that already say something: none of them narrows a product type."""
    spans = [span for found in (claims_in, labels_in, preferences_in, strictness_in) for _, span in found(seen.folded)]
    spans += [match.span() for match in CONFIRMED.finditer(seen.folded)]
    said = {index for span in spans for index in seen.indices_in(span)}
    dated = {index for index, word in enumerate(seen.words) if named_dates(word, seen.today)}
    dated |= {index for span in day_spans(seen.folded, seen.today) for index in seen.indices_in(span)}  # "by Mon"
    units = {index for index, word in enumerate(seen.words) if unit_of(word) is not None}
    return frozenset(said | dated | units | excluding)


def _request_facts(seen: Text) -> JsonDict:
    days = named_dates(seen.folded, seen.today)
    preference = next((preference.value for preference, _ in preferences_in(seen.folded)), None)
    return {
        "needed_by": days[0].isoformat() if days else None,
        "require_confirmed": CONFIRMED.search(seen.folded) is not None,
        "prefer": preference,
    }


def _narrowing(context: _Context, part: Part, first: int | None, used: frozenset[int]) -> list[str]:
    """The one word right before the type's own words, when it says nothing else: "oat" of "oat drink". A brand
    between the two is stepped over: "whipping" of "whipping Arla cream"."""
    before = None if first is None else first - 1
    while before is not None and before in context.brands:
        before -= 1
    if before is None or before not in part.indices or before in used:
        return []
    word = context.seen.words[before]
    return [] if len(word) < MIN_NARROWING_LETTERS or word in NOT_A_TERM else [word]
