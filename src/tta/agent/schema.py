"""The JSON Schema the model's structured answer is held to (SPEC sections 3 and 11).

It has the fields of the typed request (`tta.contracts.request`), with two differences that keep the model
from guessing: every field is required and a field the text does not state is `null`, and the fields that are
not the buyer's to say are left out: the buyer's own words (`text`) are set by the parser, and the standing order
a request renews (`standing_order_id`) and the recipe ingredient a line stands in for (`stands_in_for`,
`stands_in_role`) by the gateway (tasks FALLBACK-1, MENU-1). `keep_formula` is the reader's to set: the buyer's
words say what the product is for ("for whipping"), and the parser refuses it when the text names no such use.
`max_net_eur` is the reader's to set too: the most to spend the text names ("under €1,000"), which the parser
refuses unless the text states that amount as a limit (`tta.agent.budget`).
A test compares the fields with the contract, field by field: a new contract field fails it until it is placed.

Only keywords the Gemini documentation lists as enforced are used (structured output, read 14 Nov 2026):
`type`, `properties`, `required`, `additionalProperties`, `enum`, `format`, `items`, `anyOf`, `description`.
Length, pattern and range limits are not sent; the contract model enforces them on the answer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from tta.agent.wording import LABEL_CODES
from tta.allergens import ALLERGEN_CODES
from tta.allergens.codes import GENERAL_STATEMENT_CODE
from tta.contracts.common import AllergenStrictness, JsonDict, PackPreference, Preference, Unit
from tta.contracts.request import MAX_TERM_LENGTH

# The 21 nutritionalClaim ids of the whole catalog (AIMO/docs/SCHEMA-AND-CODES.md section 2.4).
CLAIM_CODES: tuple[str, ...] = (
    "FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN", "VEGAN", "VEGETARIAN", "FREE_FROM_PRESERVATIVES",
    "FREE_FROM_COLOURING_AGENTS", "FREE_FROM_ADDITIVES", "NO_ADDED_SUGARS", "HIGH_FIBRE", "FREE_FROM_EGGS",
    "HIGH_PROTEIN", "LOW_SODIUM_SALT", "FREE_FROM_SWEETENERS", "FREE_FROM_SOY", "LOW_LACTOSE", "FREE_FROM_FAT",
    "FREE_FROM_WHEAT", "LOW_FAT", "FREE_FROM_ARTIFICIAL_SWEETENERS", "FREE_FROM_GMO", "FREE_FROM_SODIUM_SALT",
)
# X99 is a general statement about a product, not an allergen a buyer can exclude
# (AIMO/docs/SCHEMA-AND-CODES.md section 3.4).
EXCLUDABLE_ALLERGEN_CODES: tuple[str, ...] = tuple(code for code in ALLERGEN_CODES if code != GENERAL_STATEMENT_CODE)

_PLAIN_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_NULL: JsonDict = {"type": "null"}


# The answer to a photo (task T18): the lines read, word for word, and nothing else. The parser reads them next.
TRANSCRIPTION_SCHEMA: JsonDict = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array", "items": {"type": "string"},
            "description": "The written lines of the photo, top to bottom, each word for word as written.",
        },
    },
    "required": ["lines"],
    "additionalProperties": False,
}


def checked_keys(product_type_keys: Sequence[str]) -> tuple[str, ...]:
    """The keys of the product-type table, refused unless each is a plain, distinct key: they are placed in
    the model's instruction, where nothing but our own words may stand."""
    keys = tuple(product_type_keys)
    plain = all(_PLAIN_KEY.match(key) and len(key) <= MAX_TERM_LENGTH for key in keys)
    if not keys or not plain or len(set(keys)) != len(keys):
        raise ValueError("The product type keys must be distinct plain keys such as plant_drink, and at least one.")
    return keys


def _nullable(schema: JsonDict, description: str) -> JsonDict:
    return {"anyOf": [schema, _NULL], "description": description}


def _choice(values: Sequence[str], description: str) -> JsonDict:
    return _nullable({"type": "string", "enum": list(values)}, description)


def _strings(description: str, values: Sequence[str] | None = None) -> JsonDict:
    items: JsonDict = {"type": "string"} if values is None else {"type": "string", "enum": list(values)}
    return {"type": "array", "items": items, "description": description}


def _object(properties: dict[str, Any]) -> JsonDict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _line_schema(keys: tuple[str, ...]) -> JsonDict:
    return _object({
        "product_type": _choice(keys, "The key that names the product asked for; null when no key fits."),
        "product_ids": _strings("Product numbers written in the text; otherwise empty."),
        "name_terms": _strings("Words the product name must contain beyond what the key and the claims say."),
        "required_claims": _strings("Claims the product itself must carry, such as lactose-free.", CLAIM_CODES),
        "quantity": _nullable({"type": "number"}, "How much is asked for; null when the text gives no quantity."),
        "unit": _choice([unit.value for unit in Unit], "L litres, KG kilograms, UNIT sales units; null if not said."),
        "exclude_allergens": _strings(
            "Allergens the buyer says must not be in the product.", EXCLUDABLE_ALLERGEN_CODES
        ),
        "allergen_strictness": _choice(
            [value.value for value in AllergenStrictness], "Only when the text says how strict; otherwise null."
        ),
        "pack": _choice([value.value for value in PackPreference], "Only when the text asks for a pack kind."),
        "required_labels": _strings(
            "Certificate labels the product must carry, only when the text names one (organic, MSC, Fairtrade).",
            LABEL_CODES,
        ),
        "keep_formula": _nullable(
            {"type": "boolean"},
            "True only when the text says what the product is for and the formula matters for that use (for "
            "baking, for cakes, for whipping, for a sauce, for a recipe); otherwise null. A product's own name "
            "(whipping cream) is not a use.",
        ),
    })


def proposal_schema(product_type_keys: Sequence[str]) -> JsonDict:
    """The schema of the model's answer for this product-type table. Raises `ValueError` for bad keys."""
    keys = checked_keys(product_type_keys)
    return _object({
        "needed_by": _nullable(
            {"type": "string", "format": "date"}, "The date the goods are needed, from the calendar; null if not said."
        ),
        "require_confirmed": {"type": "boolean", "description": "True only when the buyer asks for confirmed data."},
        "prefer": _choice(
            [value.value for value in Preference],
            "What to rank by, only when the text says (as soon as possible, most reliable, lowest carbon); else null.",
        ),
        "max_net_eur": _nullable(
            {"type": "number"},
            "The most to spend on this request, in euros before tax, only when the text names one amount in euros "
            "as a limit (under €1,000, a budget of 1,000 euros, max 1000 euros); otherwise null. Never a price per "
            "unit, never an amount in another currency.",
        ),
        "lines": {"type": "array", "items": _line_schema(keys), "description": "One per product asked for."},
    })
