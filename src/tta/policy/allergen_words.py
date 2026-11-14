"""Allergens and dietary claims as a person reads them: words, never codes.

A rule sentence and an authority text name an allergen by the label of the catalog's own table
(`tta.allergens.codes`): "tree nuts, peanuts and sesame seeds", not "AN, AP, AS". The codes stay in the facts
written to the decision next to the sentence, where an auditor finds them. A code the table does not hold has
no word: it is said to be one the table does not name, with the code, because hiding it would hide an allergen.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from tta.allergens.codes import ALLERGEN_CODES
from tta.contracts.allergen import AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness, ApproverRole
from tta.contracts.offer import OfferLine
from tta.contracts.policy import BuyerProfile
from tta.policy.reading import Missing, Reading
from tta.policy.text import join_words, plain_name, unique

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope, ScopeTable

UNNAMED_CODE = "an allergen the catalog's table does not name ({code})"
NO_ALLERGEN = "no allergen"
# What a product says about one allergen, as a verb before the allergen's name.
SAYS: Mapping[AllergenRelation, str] = {
    AllergenRelation.CONTAINS: "contains {what}",
    AllergenRelation.MAY_CONTAIN: "may contain {what}",
    AllergenRelation.UNDECLARED: "leaves {what} undeclared",
    AllergenRelation.NOT_STATED: "says nothing about {what}",
    AllergenRelation.FREE_FROM: "is free from {what}",
}
# What a substitute adds: a statement the product asked for does not make (rule F-05).
ADDS: Mapping[AllergenRelation, str] = {
    AllergenRelation.CONTAINS: "declares that it contains {what}",
    AllergenRelation.MAY_CONTAIN: "declares that it may contain {what}",
}
ADDS_OTHER = "states {what}"
COUNTED_UNDER = "{member} (counted under {family})"
# Said when the check or the offer gives the outcome and names no allergen: the sentence still says what is so.
UNNAMED_FINDING: Mapping[AllergenOutcome, str] = {
    AllergenOutcome.REJECT: "contains an allergen the allergen check does not name",
    AllergenOutcome.TO_HUMAN: "does not rule out an allergen the allergen check does not name",
}
UNNAMED_ADDED = "states an allergen the offer does not name"
# The dietary claims of the offer (`tta.offers.substitutes.DIETARY_CLAIMS`; a test checks that the two agree),
# as a kitchen says them. Any other claim code is said in lower case, its underscores as spaces.
CLAIM_WORDS: Mapping[str, str] = {
    "FREE_FROM_LACTOSE": "lactose-free",
    "LOW_LACTOSE": "low-lactose",
    "FREE_FROM_GLUTEN": "gluten-free",
    "FREE_FROM_WHEAT": "wheat-free",
    "FREE_FROM_EGGS": "egg-free",
    "FREE_FROM_SOY": "soy-free",
    "VEGAN": "vegan",
    "VEGETARIAN": "vegetarian",
}


def allergen_word(code: str) -> str:
    """`AN` -> "tree nuts". A code outside the table is named as such, with the code."""
    entry = ALLERGEN_CODES.get(code)
    return entry.label if entry else UNNAMED_CODE.format(code=plain_name(code))


def allergen_words(codes: Sequence[str]) -> str:
    """`[AN, AP, AS]` -> "tree nuts, peanuts and sesame seeds"; "no allergen" for none."""
    return join_words(unique([allergen_word(code) for code in codes])) or NO_ALLERGEN


def claim_words(codes: Sequence[str]) -> str:
    """`[FREE_FROM_LACTOSE]` -> "lactose-free". A code is text of the product file: read as data."""
    said = [CLAIM_WORDS.get(code) or plain_name(code).replace("_", " ").lower() for code in codes]
    return join_words(unique(said))


def _by_relation(pairs: Sequence[tuple[AllergenRelation, str]], verbs: Mapping[AllergenRelation, str]) -> str:
    """"may contain tree nuts and says nothing about sesame seeds": one part per relation, in first-seen order."""
    grouped: dict[AllergenRelation, list[str]] = {}
    for relation, what in pairs:
        grouped.setdefault(relation, []).append(what)
    return join_words([
        verbs.get(relation, ADDS_OTHER).format(what=join_words(unique(names))) for relation, names in grouped.items()
    ])


def _finding_name(finding: AllergenFinding) -> str:
    """The allergen a finding is about; a member of a family is named with the family the buyer excludes."""
    family = allergen_word(finding.excluded_code)
    if finding.matched_code is None or finding.matched_code == finding.excluded_code:
        return family
    return COUNTED_UNDER.format(member=allergen_word(finding.matched_code), family=family)


def _findings_said(outcome: AllergenOutcome) -> Callable[[OrderScope, OfferLine], Reading]:
    def read(_: OrderScope, line: OfferLine) -> Reading:
        check = line.allergen_check
        found = [each for each in (check.findings if check else ()) if each.outcome is outcome]
        if not found:
            return UNNAMED_FINDING[outcome]
        return _by_relation([(each.relation, _finding_name(each)) for each in found], SAYS)

    return read


def _added_said(_: OrderScope, line: OfferLine) -> Reading:
    """"declares that it contains oats and cereals containing gluten": what the substitute states and the
    product asked for does not. The offer lists an added allergen and one raised from may contain to contains
    alike; "declares that it contains" is true of both, as the original of a raised one says "may contain"."""
    added = line.substitute.allergen_check.added if line.substitute is not None else ()
    if not added:
        return UNNAMED_ADDED
    return _by_relation([(each.relation, allergen_word(each.code)) for each in added], ADDS)


def _claims_lost_said(_: OrderScope, line: OfferLine) -> Reading:
    lost = line.substitute.claims_lost if line.substitute is not None else ()
    return claim_words(lost) if lost else Missing("the substitute lacks no claim of the product it replaces")


def _names_dietitian(profile: BuyerProfile, _: ScopeTable) -> Reading:
    """Whether somebody holds the dietitian's role at this buyer. Where nobody does, a question that would go
    to the dietitian goes to the purchasing manager, so that it can be answered at all."""
    return bool(profile.approver_roles.get(ApproverRole.DIETITIAN))


ALLERGEN_PROFILE_FACTS: Mapping[str, Callable[[BuyerProfile, ScopeTable], Reading]] = {
    "profile.excluded_allergens_said": lambda profile, _: allergen_words(profile.excluded_allergens),
    "profile.strict_allergens_said": lambda profile, _: allergen_words(profile.codes_under(AllergenStrictness.STRICT)),
    "profile.declared_only_allergens_said": lambda profile, _: allergen_words(
        profile.codes_under(AllergenStrictness.DECLARED_ONLY)
    ),
    "profile.names_dietitian": _names_dietitian,
}
ALLERGEN_LINE_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.allergens_declared_said": _findings_said(AllergenOutcome.REJECT),
    "line.allergens_to_human_said": _findings_said(AllergenOutcome.TO_HUMAN),
    "line.substitute_added_allergens_said": _added_said,
    "line.substitute_claims_lost_said": _claims_lost_said,
}
