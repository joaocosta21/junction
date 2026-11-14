"""The buyer exclusion rule (SPEC section 6): per excluded allergen PASS, REJECT or TO_HUMAN.

A nutritional claim is never an input here: `FREE_FROM_LACTOSE` is not a statement about milk
(AIMO/docs/SCHEMA-AND-CODES.md section 4).

The product's own ingredient list counts as a statement: when it names an excluded allergen that the
declaration states FREE_FROM, marks UNDECLARED or does not state, the finding is MAY_CONTAIN and goes to a
dietitian, with a sentence quoting both. A declared CONTAINS stays a rejection.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from tta.allergens.codes import (
    GENERAL_STATEMENT_CODE,
    describe,
    gs1_name,
    is_known_code,
    members_of,
    normalise_code,
    parent_of,
)
from tta.allergens.ingredients import IngredientMention, ingredient_mentions
from tta.allergens.statements import Basis, Resolution, resolve
from tta.contracts.allergen import AllergenCheck, AllergenFinding, AllergenStatement
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.errors import InvalidRequest, SupplierUnavailable

STRICT = AllergenStrictness.STRICT
DECLARED_ONLY = AllergenStrictness.DECLARED_ONLY

# The table of SPEC section 6, cell by cell. UNDECLARED and no statement share a row.
_OUTCOME_TABLE: dict[tuple[AllergenRelation, AllergenStrictness], AllergenOutcome] = {
    (AllergenRelation.FREE_FROM, STRICT): AllergenOutcome.PASS,
    (AllergenRelation.FREE_FROM, DECLARED_ONLY): AllergenOutcome.PASS,
    (AllergenRelation.CONTAINS, STRICT): AllergenOutcome.REJECT,
    (AllergenRelation.CONTAINS, DECLARED_ONLY): AllergenOutcome.REJECT,
    (AllergenRelation.MAY_CONTAIN, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.MAY_CONTAIN, DECLARED_ONLY): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.UNDECLARED, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.UNDECLARED, DECLARED_ONLY): AllergenOutcome.PASS,
    (AllergenRelation.NOT_STATED, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.NOT_STATED, DECLARED_ONLY): AllergenOutcome.PASS,
}

# Least to most severe: the most severe finding is the outcome for the product.
_SEVERITY = {AllergenOutcome.PASS: 0, AllergenOutcome.TO_HUMAN: 1, AllergenOutcome.REJECT: 2}

# An explicit statement is one that settles the question without a person (SPEC section 4, `allergens`).
_EXPLICIT_RELATIONS = frozenset({AllergenRelation.FREE_FROM, AllergenRelation.CONTAINS})

_VERB = {AllergenRelation.CONTAINS: "contains", AllergenRelation.MAY_CONTAIN: "may contain"}

_DIRECT_FACT = {
    AllergenRelation.FREE_FROM: "The product states it is free from {allergen}",
    AllergenRelation.CONTAINS: "The product declares that it contains {allergen}, which the buyer excludes",
    AllergenRelation.MAY_CONTAIN: "The product declares that it may contain {allergen}, which the buyer excludes",
    AllergenRelation.UNDECLARED: "The product marks {allergen} as UNDECLARED, which is not a free-from statement",
}

_TO_HUMAN_ENDING = ": a dietitian must decide."
_UNVERIFIED_ENDING = ": it passes as unverified."

# The declarations an ingredient list can contradict; CONTAINS and MAY_CONTAIN already say as much.
_OPEN_RELATIONS = frozenset({AllergenRelation.FREE_FROM, AllergenRelation.UNDECLARED, AllergenRelation.NOT_STATED})
MAX_QUOTES = 3  # our limit: words quoted from the ingredient list in one sentence


def check_exclusions(
    statements: Sequence[AllergenStatement],
    excluded: Sequence[str],
    strictness: AllergenStrictness | None,
    *,
    ingredients: str | None = None,
    by_code: Mapping[str, AllergenStrictness] | None = None,
) -> AllergenCheck:
    """Apply the buyer exclusion rule to the allergen statements of one product.

    `ingredients` is the product's own ingredient list (`Product.key_ingredients`); `None` leaves the
    declaration alone to decide. `by_code` gives one excluded allergen a rule of its own (an allergy STRICT,
    another allergen DECLARED_ONLY); `strictness` is the rule of every allergen it does not name.

    An excluded allergen with no rule at all (`strictness` is `None` and `by_code` does not name it) is read as
    STRICT: the safe reading, where a refusal stood before (review P4, item M3; Valio Aimo, 14 Nov 2026: "if you
    are not sure you need to flag it to the user"). `rule_or_strict` is that default; the offer says when it was
    used (`tta.offers.candidates.need_for`).

    Raises `InvalidRequest` for an excluded code outside the code table and for `X99`. Raises
    `SupplierUnavailable` for a statement whose code is outside the code table: such a statement matches no
    exclusion, so the product would pass under `DECLARED_ONLY` on data nobody can read.
    """
    codes = tuple(dict.fromkeys(excluded))
    _require_valid_exclusions(codes)
    checked = _with_table_codes(statements)
    if not codes:
        return AllergenCheck(outcome=AllergenOutcome.PASS, strictness=strictness, all_explicit=True)
    rules = {code: rule_or_strict((by_code or {}).get(code, strictness)) for code in codes}
    mentions = ingredient_mentions(ingredients)
    findings = tuple(_finding(checked, code, rules[code], mentions) for code in codes)
    return AllergenCheck(
        outcome=max((finding.outcome for finding in findings), key=_SEVERITY.__getitem__),
        strictness=STRICT if STRICT in rules.values() else DECLARED_ONLY,
        findings=findings,
        all_explicit=all(finding.relation in _EXPLICIT_RELATIONS for finding in findings),
    )


def rule_or_strict(rule: AllergenStrictness | None) -> AllergenStrictness:
    """The rule of an excluded allergen; STRICT when none was given (review P4, item M3)."""
    return STRICT if rule is None else rule


def _require_valid_exclusions(codes: Sequence[str]) -> None:
    if GENERAL_STATEMENT_CODE in codes:
        raise InvalidRequest(
            f"{GENERAL_STATEMENT_CODE} is the general statement '{gs1_name(GENERAL_STATEMENT_CODE)}', "
            "not an allergen that can be excluded."
        )
    unknown = [code for code in codes if not is_known_code(code)]
    if unknown:
        raise InvalidRequest(
            f"Unknown allergen code(s): {', '.join(unknown)}. Use the GS1 codes of the catalog, such as AM for milk.",
            unknown_codes=unknown,
        )


def _with_table_codes(statements: Sequence[AllergenStatement]) -> tuple[AllergenStatement, ...]:
    """The statements with each code as the table spells it. Raises for a code outside the table."""
    normalised = tuple(_with_table_code(statement) for statement in statements)
    unknown = sorted({statement.code for statement in normalised if not is_known_code(statement.code)})
    if unknown:
        raise SupplierUnavailable(
            f"The product data has an allergen statement with a code outside the code table: "
            f"{', '.join(repr(code) for code in unknown)}. The allergen check is not made on such data.",
            unknown_codes=unknown,
        )
    return normalised


def _with_table_code(statement: AllergenStatement) -> AllergenStatement:
    code = normalise_code(statement.code)
    return statement if code == statement.code else AllergenStatement(code=code, relation=statement.relation)


def _finding(
    statements: Sequence[AllergenStatement],
    code: str,
    strictness: AllergenStrictness,
    mentions: Sequence[IngredientMention],
) -> AllergenFinding:
    resolution = resolve(statements, code)
    named = _named_in_ingredients(mentions, code, resolution)
    if named:
        return _ingredient_finding(code, resolution, named, strictness)
    outcome = _OUTCOME_TABLE[(resolution.relation, strictness)]
    is_about_another_code = resolution.basis in (Basis.MEMBER, Basis.OATS, Basis.FAMILY)
    return AllergenFinding(
        excluded_code=code,
        relation=resolution.relation,
        matched_code=resolution.source_code if is_about_another_code else None,
        outcome=outcome,
        sentence=_sentence(code, resolution, outcome),
        strictness=strictness,
    )


def _sentence(code: str, resolution: Resolution, outcome: AllergenOutcome) -> str:
    fact = _fact(code, resolution)
    if outcome is AllergenOutcome.TO_HUMAN:
        return fact + _TO_HUMAN_ENDING
    if resolution.relation is AllergenRelation.FREE_FROM or outcome is AllergenOutcome.REJECT:
        return fact + "."
    return fact + _UNVERIFIED_ENDING


def _fact(code: str, resolution: Resolution) -> str:
    allergen = describe(code)
    source = describe(resolution.source_code) if resolution.source_code else ""
    if resolution.basis is Basis.DIRECT:
        return _DIRECT_FACT[resolution.relation].format(allergen=allergen)
    if resolution.basis is Basis.MEMBER:
        verb = _VERB[resolution.relation]
        return f"The product declares that it {verb} {source}, part of the excluded {allergen}"
    if resolution.basis is Basis.OATS:
        return (
            f"The product declares that it contains {source} and the buyer excludes {allergen}; "
            "oats can be gluten-free or not"
        )
    if resolution.basis is Basis.FAMILY:
        if resolution.own_relation is AllergenRelation.UNDECLARED:
            return f"The product declares {source} and marks {allergen}, part of that family, as UNDECLARED"
        return f"The product declares {source} and makes no statement about {allergen}, part of that family"
    if resolution.basis is Basis.GENERAL:
        return (
            f"The product carries the general statement {GENERAL_STATEMENT_CODE} "
            f"('{gs1_name(GENERAL_STATEMENT_CODE)}'), which is not a statement about {allergen}"
        )
    return f"The product makes no statement about {allergen}"


def _named_in_ingredients(
    mentions: Sequence[IngredientMention], code: str, resolution: Resolution
) -> tuple[IngredientMention, ...]:
    """The mentions of the ingredient list that contradict an open declaration about `code`.

    Read like the declarations (`tta.allergens.statements`): a member of the excluded family counts ("ALMOND"
    for tree nuts), and the family counts for an excluded member ("nuts" for almonds) unless the member itself
    is stated FREE_FROM (lactose-free milk names MILK and states lactose FREE_FROM).
    """
    if resolution.relation not in _OPEN_RELATIONS:
        return ()
    codes = {code, *members_of(code)}
    family = parent_of(code)
    if family is not None and resolution.own_relation is not AllergenRelation.FREE_FROM:
        codes.add(family)
    return tuple(mention for mention in mentions if mention.code in codes)


def _ingredient_finding(
    code: str, resolution: Resolution, named: Sequence[IngredientMention], strictness: AllergenStrictness
) -> AllergenFinding:
    """The ingredient list names what the declaration leaves open: MAY_CONTAIN, so a dietitian decides."""
    first = named[0].code
    return AllergenFinding(
        excluded_code=code,
        relation=AllergenRelation.MAY_CONTAIN,
        matched_code=first if first != code else None,
        outcome=_OUTCOME_TABLE[(AllergenRelation.MAY_CONTAIN, strictness)],
        sentence=_ingredient_sentence(code, resolution, named),
        strictness=strictness,
    )


def _ingredient_sentence(code: str, resolution: Resolution, named: Sequence[IngredientMention]) -> str:
    names = _quoted(mention.words for mention in named if not mention.may_contain)
    phrases = _quoted(mention.words for mention in named if mention.may_contain)
    parts = (f"names {names}" if names else "", f"says {phrases}" if phrases else "")
    said = " and ".join(part for part in parts if part)
    return f"The ingredient list {said}, while {_declaration(code, resolution)}{_TO_HUMAN_ENDING}"


def _quoted(words: Iterable[str]) -> str:
    """`"ALMOND", "almond"`: each distinct wording once, at most `MAX_QUOTES`."""
    return ", ".join(f'"{each}"' for each in list(dict.fromkeys(words))[:MAX_QUOTES])


def _declaration(code: str, resolution: Resolution) -> str:
    allergen = describe(code)
    if resolution.relation is AllergenRelation.FREE_FROM:
        return f"the product states it is free from {allergen}"
    if resolution.relation is AllergenRelation.UNDECLARED:
        return f"the product marks {allergen} as UNDECLARED"
    if resolution.basis is Basis.GENERAL:
        return (
            f"the product carries only the general statement {GENERAL_STATEMENT_CODE} "
            f"('{gs1_name(GENERAL_STATEMENT_CODE)}')"
        )
    return f"the product makes no statement about {allergen}"
