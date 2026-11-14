"""What Valio Aimo may see of the log (SPEC section 9, as Valio answered on 14 Nov: "all the steps and decisions",
"why it made that decision and the logic behind it and product considered").

Shown: every rule that fired, by its id, its title, whether it is a fixed rule or one the buyer set, its outcome
and the role that must sign; the claims and labels asked for; the products considered and left out.
Masked: limit amounts, allergen codes and the products a rule about an excluded allergen fired on. The role
stands for the approver's name. Notes and the buyer's own words stay out. Products left out for a requirement of
the buyer's are neither listed nor counted: Valio Aimo has the catalog, so a count per product type would give
the allergen away (review finding M1). Events stored before that still hold the two counts; they are masked when
read (`shown_facts`, `shown_sentence`), here and in the SQL view alike.

Of whoever acted Valio Aimo sees the kind, for an agent its id ("the agent's identity"), and for a human the
approver roles the gateway knows. The buyer sees everything about its own requests, so the buyer's side needs
no rule here. The SQL view `audit_supplier` (`tta/store/sql/003_reader_views.sql`) shows the same;
`tests/audit/test_sql_view.py` fails when the two differ.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from tta.contracts.audit import Actor, ActorKind
from tta.contracts.common import ApproverRole, ExclusionReason, JsonDict

# Kept for `tests/store_pg/test_reader_views.py`, which builds its list of rule ids from the keys. Since S4 no
# list filters the supplier's rules: a rule is named by the title it fired with (`tta.audit.supplier_decisions`).
SUPPLIER_RULE_MEANINGS = {
    "F-01": "a line's quantity is not confirmed",
    "F-03": "a fact a rule needs is missing",
    "F-04": "the offer expired, a cut-off passed, or price or availability changed",
    "F-05": "a substitute adds an allergen the original does not declare, or raises one to contains",
    "F-06": "an agent cannot approve an order",
    "F-07": "a price is not confirmed, a delivery date is ruled out, or a needed-by date is not verifiably met",
    "F-08": "a substitute lacks a nutritional claim the original carries",
}
AGENT_ON_APPROVAL_ROUTE = "F-06"
# The rules that fire because of an allergen the buyer excludes. Valio Aimo reads their id, title and outcome;
# never the allergen, and never the product, which together with Valio's own allergen data would give the code.
RULES_ABOUT_AN_EXCLUDED_ALLERGEN = ("F-02", "P-04")
# What a rule read that Valio Aimo is not shown. The sentence says so, so a masked value is not taken for a gap.
MASKED_BY_RULE = {
    "P-01": "the amount is not shown",
    "P-02": "the amounts are not shown",
    "P-03": "the buyer's minimum is not shown",
    "P-08": "the buyer's tolerance is not shown",
    "P-09": "the amount and the buyer's limit are not shown",
    **dict.fromkeys(RULES_ABOUT_AN_EXCLUDED_ALLERGEN, "which allergen and which product are not shown"),
}
KNOWN_ROLES = tuple(role.value for role in ApproverRole)
ROLE_SEPARATOR = ", "  # how `tta.orders.access.actor_of` joins the roles of one token
HUMAN_ID = "buyer-human"
HUMAN_WITHOUT_A_ROLE = "A human at the buyer"
BUYERS_ROLE = "The buyer's {roles}"
# Valio Aimo's own token acting (refused on an approval): `tta.orders.access.actor_of` gives it this role.
SUPPLIER_ROLE = "supplier"
SUPPLIER_READER_ID = "supplier-reader"
SUPPLIER_READER = "Valio Aimo's reader"
# Why a product was left out, where the reason is a requirement of the buyer's and not Valio Aimo's own data.
# Valio Aimo reads neither the products nor how many: the count per product type would name the allergen.
# CLAIM_CONTRADICTED is not one of them: it compares a claim the request requires, which Valio Aimo is shown
# (decision B14), with the product's own allergen data, and reads nothing of the buyer's exclusions.
REASONS_OF_THE_BUYER = (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED)
NOT_SHOWN_OR_COUNTED = "Products left out for a requirement of the buyer's, if any, are not shown or counted."
# Where an event stored before the fix holds those counts in the supplier's facts.
OFFER_FACT, COUNTS_FACT = "offer", "excluded_by_reason"
STORED_COUNT_PATHS = tuple((OFFER_FACT, COUNTS_FACT, reason.value) for reason in REASONS_OF_THE_BUYER)
# What an event stored before the fix says of them in the supplier's sentence, and what is read instead: the
# total goes (it gives the masked number by subtraction), then each masked count, then the list they emptied.
# Applied in this order, everywhere in the sentence. The SQL view holds the same texts, in the same order.
# \x3B is the semicolon between two reasons: written so because the SQL file is cut at semicolons when it is read
# by `tests/audit/test_sql_view.py`, and one pattern must serve Python and PostgreSQL alike.
STORED_SENTENCE_MASKS = (
    (
        r"[0-9][0-9,]* products? (was|were) considered and left out: ",
        "Left out for a reason in Valio Aimo's own data (products left out for a requirement of the buyer's, "
        "if any, are not shown or counted): ",
    ),
    (
        r"(\x3B )?[0-9][0-9,]* (declaring|stating nothing about) an allergen the buyer excludes "
        r"\(which allergen and which products are not shown\)",
        "",
    ),
    (r"are not shown or counted\): \.", "are not shown or counted): none."),
)


def supplier_rule_ids(rule_ids: Sequence[str]) -> tuple[str, ...]:
    """Every rule that fired, each id once, in the order they fired."""
    return tuple(dict.fromkeys(rule_ids))


def supplier_role(role: str | None) -> str | None:
    """The approver roles the gateway knows, of those an actor carries. Any other text is dropped: the field
    is free text in the contract, and only a role may stand for a person."""
    held = [name for name in (role or "").split(ROLE_SEPARATOR) if name in KNOWN_ROLES]
    return ROLE_SEPARATOR.join(held) or None


def is_supplier_reader(actor: Actor) -> bool:
    """Whether Valio Aimo's own token acted: it is not a person at the buyer."""
    return actor.kind is ActorKind.HUMAN and actor.role == SUPPLIER_ROLE


def shown_facts(facts: JsonDict) -> JsonDict:
    """The supplier's facts as stored, without the counts of products left out for a requirement of the buyer's."""
    offer = facts.get(OFFER_FACT)
    counts = offer.get(COUNTS_FACT) if isinstance(offer, dict) else None
    masked = {reason.value for reason in REASONS_OF_THE_BUYER}
    if not isinstance(counts, dict) or masked.isdisjoint(counts):
        return facts
    kept = {reason: number for reason, number in counts.items() if reason not in masked}
    return {**facts, OFFER_FACT: {**offer, COUNTS_FACT: kept}}


def shown_sentence(sentence: str) -> str:
    """The supplier's sentence as stored, without those counts and without the total that gives them away."""
    for pattern, replacement in STORED_SENTENCE_MASKS:
        sentence = re.sub(pattern, replacement, sentence)
    return sentence


def supplier_actor(actor: Actor) -> Actor:
    """An agent by its id and kind only; a human by role, never by name or id; Valio Aimo's own reader as
    such; the gateway as it is."""
    if actor.kind is ActorKind.AGENT:
        return Actor(kind=ActorKind.AGENT, id=actor.id)
    if actor.kind is not ActorKind.HUMAN:
        return actor
    if is_supplier_reader(actor):
        return Actor(kind=ActorKind.HUMAN, id=SUPPLIER_READER_ID, role=SUPPLIER_ROLE, display_name=SUPPLIER_READER)
    role = supplier_role(actor.role)
    if role is None:
        return Actor(kind=ActorKind.HUMAN, id=HUMAN_ID, display_name=HUMAN_WITHOUT_A_ROLE)
    return Actor(
        kind=ActorKind.HUMAN, id=HUMAN_ID, role=role, display_name=BUYERS_ROLE.format(roles=role.replace("_", " ")),
    )
