"""The fixed rules as five plain statements.

A customer does not read a list of rule ids. The page shows five statements in their place, and each fixed rule
of `rules.yaml` (and each access rule) belongs to exactly one of them: its `group`. The statements are in the
rules file under `groups`; their keys are pinned in `tta.policy.validation.RULE_GROUPS`, and a rules file whose
fixed rule names no group does not load. `GET /v1/authority` does not carry the grouping: `RuleSummary` has no
field for it, so a page asks `rule_groups()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from tta.policy.loading import load_rulebook
from tta.policy.rulebook import Rulebook


@dataclass(frozen=True)
class RuleGroup:
    """One statement and the fixed rules that stand behind it, in the order of the rules file."""

    key: str
    statement: str
    rule_ids: tuple[str, ...]


def groups_of(rulebook: Rulebook) -> tuple[RuleGroup, ...]:
    """The groups of one rulebook, in the order of the file. A rule listed once per scope is named once."""
    grouped = [(rule.id, rule.group) for rule in rulebook.rules if rule.fixed]
    grouped.extend((rule.id, rule.group) for rule in rulebook.access_rules)
    return tuple(
        RuleGroup(key, statement, tuple(dict.fromkeys(rule_id for rule_id, group in grouped if group == key)))
        for key, statement in rulebook.groups.items()
    )


@lru_cache(maxsize=1)
def rule_groups() -> tuple[RuleGroup, ...]:
    """The five statements of the shipped rules file, each with the ids of its fixed rules."""
    return groups_of(load_rulebook())
