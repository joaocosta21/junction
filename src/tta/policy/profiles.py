"""Buyer profiles: one YAML file per buyer, checked against the `BuyerProfile` contract when loaded.

A profile sets limits and nothing else. A file that names a fixed rule, or carries any setting the
contract does not know, is rejected: no profile can switch off or weaken a fixed rule.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tta.allergens import gs1_name, is_known_code
from tta.allergens.codes import GENERAL_STATEMENT_CODE
from tta.contracts.policy import BuyerProfile
from tta.policy.errors import PolicyLoadError, validation_problems
from tta.policy.loading import read_mapping

PROFILE_FILE_PATTERN = "*.yaml"
PROFILE_SETTINGS = frozenset(BuyerProfile.model_fields)


def load_profile(path: Path, fixed_rule_ids: Collection[str]) -> BuyerProfile:
    """One profile file. Raises `PolicyLoadError` naming what is wrong."""
    source = f"profile file {path.name}"
    profile = check_profile(read_mapping(path, source), source, fixed_rule_ids)
    if profile.profile_id != path.stem:
        raise PolicyLoadError(source, [f"profile_id '{profile.profile_id}' does not match the file name"])
    return profile


def check_profile(data: Mapping[str, Any], source: str, fixed_rule_ids: Collection[str]) -> BuyerProfile:
    """The checks of a profile file on its settings, wherever they come from: a file, or a form of the pages
    (task FEAT-1). Raises `PolicyLoadError` naming what is wrong."""
    named = _fixed_rules_named(dict(data), fixed_rule_ids)
    if named:
        raise PolicyLoadError(
            source, [f"it names fixed rule {', '.join(named)}: a profile cannot switch off or weaken a fixed rule"]
        )
    unknown = sorted(key for key in data if key not in PROFILE_SETTINGS)
    if unknown:
        raise PolicyLoadError(
            source,
            [f"unknown setting {', '.join(unknown)}: a profile sets {', '.join(sorted(PROFILE_SETTINGS))} "
             "and cannot change a rule"],
        )
    try:
        profile = BuyerProfile.model_validate(data)
    except ValidationError as error:
        raise PolicyLoadError(source, validation_problems(error)) from error
    problems = _exclusion_problems(profile.excluded_allergens)
    if problems:
        raise PolicyLoadError(source, problems)
    return profile


def load_profiles(directory: Path, fixed_rule_ids: Collection[str]) -> dict[str, BuyerProfile]:
    """Every profile of a folder, by id. One broken file stops the load."""
    paths = sorted(directory.glob(PROFILE_FILE_PATTERN))
    if not paths:
        raise PolicyLoadError(f"profile folder {directory.name}", ["no buyer profile was found"])
    profiles = (load_profile(path, fixed_rule_ids) for path in paths)
    return {profile.profile_id: profile for profile in profiles}


def _exclusion_problems(codes: Sequence[str]) -> list[str]:
    """What is wrong with the excluded allergen codes: each must be an allergen of the code table.

    A code that matches nothing excludes nothing, so a misspelt one ("milk", "am") would leave the buyer
    without the exclusion it asked for. Codes are not corrected here: the file is rejected.
    """
    problems: list[str] = []
    unknown = [f"'{code}'" for code in codes if not is_known_code(code)]
    if unknown:
        problems.append(
            f"excluded_allergens: unknown allergen code {', '.join(unknown)}: use the GS1 codes of the "
            "catalog in upper case, such as AM for milk"
        )
    if GENERAL_STATEMENT_CODE in codes:
        problems.append(
            f"excluded_allergens: {GENERAL_STATEMENT_CODE} is the general statement "
            f"'{gs1_name(GENERAL_STATEMENT_CODE)}', not an allergen that can be excluded"
        )
    return problems


def _fixed_rules_named(data: Any, fixed_rule_ids: Collection[str]) -> list[str]:
    """The fixed rule ids that appear anywhere in the file, as a key or as a value, in any letter case."""
    wanted = {rule_id.upper(): rule_id for rule_id in fixed_rule_ids}
    return sorted({wanted[word] for word in _words(data) if word in wanted})


def _words(data: Any) -> list[str]:
    if isinstance(data, dict):
        return [word for key, value in data.items() for word in (*_words(key), *_words(value))]
    if isinstance(data, list | tuple):
        return [word for item in data for word in _words(item)]
    return [data.strip().upper()] if isinstance(data, str) else []
