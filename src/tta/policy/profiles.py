"""Buyer profiles: one YAML file per buyer, checked against the `BuyerProfile` contract when loaded.

A profile sets limits and nothing else. A file that names a fixed rule, or carries any setting the
contract does not know, is rejected: no profile can switch off or weaken a fixed rule.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tta.contracts.policy import BuyerProfile
from tta.policy.errors import PolicyLoadError, validation_problems
from tta.policy.loading import read_mapping

PROFILE_FILE_PATTERN = "*.yaml"
PROFILE_SETTINGS = frozenset(BuyerProfile.model_fields)


def load_profile(path: Path, fixed_rule_ids: Collection[str]) -> BuyerProfile:
    """One profile file. Raises `PolicyLoadError` naming what is wrong."""
    source = f"profile file {path.name}"
    data = read_mapping(path, source)
    named = _fixed_rules_named(data, fixed_rule_ids)
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
    if profile.profile_id != path.stem:
        raise PolicyLoadError(source, [f"profile_id '{profile.profile_id}' does not match the file name"])
    return profile


def load_profiles(directory: Path, fixed_rule_ids: Collection[str]) -> dict[str, BuyerProfile]:
    """Every profile of a folder, by id. One broken file stops the load."""
    paths = sorted(directory.glob(PROFILE_FILE_PATTERN))
    if not paths:
        raise PolicyLoadError(f"profile folder {directory.name}", ["no buyer profile was found"])
    profiles = (load_profile(path, fixed_rule_ids) for path in paths)
    return {profile.profile_id: profile for profile in profiles}


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
