"""GS1 allergen codes and families, the buyer exclusion rule, the substitution rule.

Pure functions over the contract's allergen statements: no file, no network, no model.
"""

from tta.allergens.codes import (
    ALLERGEN_CODES,
    FAMILIES,
    AllergenCode,
    describe,
    gs1_name,
    is_known_code,
    members_of,
    parent_of,
)
from tta.allergens.exclusion import check_exclusions
from tta.allergens.statements import statement_for
from tta.allergens.substitution import check_substitute

__all__ = [
    "ALLERGEN_CODES",
    "FAMILIES",
    "AllergenCode",
    "check_exclusions",
    "check_substitute",
    "describe",
    "gs1_name",
    "is_known_code",
    "members_of",
    "parent_of",
    "statement_for",
]
