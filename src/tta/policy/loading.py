"""Read and check the rules file. A file that fails any check raises `PolicyLoadError`: nothing is skipped."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from tta.policy.errors import PolicyLoadError, validation_problems
from tta.policy.facts import KNOWN_FACTS
from tta.policy.rulebook import Rulebook
from tta.policy.validation import validate_rulebook

PACKAGE_DIR = Path(__file__).resolve().parent
RULES_PATH = PACKAGE_DIR / "rules.yaml"
PROFILES_DIR = PACKAGE_DIR / "profiles"


def read_mapping(path: Path, source: str) -> dict[str, Any]:
    """The YAML file as a mapping with text keys. The file is data: `safe_load` builds plain values only."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PolicyLoadError(source, [f"the file cannot be read ({type(error).__name__})"]) from error
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise PolicyLoadError(source, ["the file is not valid YAML"]) from error
    if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
        raise PolicyLoadError(source, ["the file must be a mapping of setting names to values"])
    return data


def parse_rulebook(data: Any, source: str = "rules") -> Rulebook:
    """Plain data to a checked rulebook. Every problem found is in the error, not only the first."""
    if not isinstance(data, dict):
        raise PolicyLoadError(source, ["the rules must be a mapping"])
    try:
        rulebook = Rulebook.model_validate(data)
    except ValidationError as error:
        raise PolicyLoadError(source, validation_problems(error)) from error
    problems = validate_rulebook(rulebook, KNOWN_FACTS)
    if problems:
        raise PolicyLoadError(source, problems)
    return rulebook


def load_rulebook(path: Path = RULES_PATH) -> Rulebook:
    source = f"rules file {path.name}"
    return parse_rulebook(read_mapping(path, source), source)
