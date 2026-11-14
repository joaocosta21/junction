"""What a rules file must hold beyond its shape. Every problem is collected, none stops at the first.

After Gabriela's `AIMO/policy/policy_check.py`: rules read declared facts only, an approval names a
role, ids are unique. Added here: the fixed rules must be present and fixed, with the verdict and the
approver role that are written in this module and not in the file; a fixed rule may not read a profile
setting, a missing fact may not pass, and every declared fact must be readable by the engine.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from tta.contracts.common import ApproverRole, SubstitutionScope, Verdict
from tta.policy.facts import LINE_FACT_PREFIX, PROFILE_FACT_PREFIX, SUBSTITUTE_LISTED, SUBSTITUTE_SAME_CATEGORY
from tta.policy.rulebook import (
    LIST_FACT_OPS,
    LIST_VALUE_OPS,
    NUMBER_OPS,
    NUMBER_TYPES,
    TRUTH_OPS,
    UNARY_OPS,
    AuthorityText,
    Condition,
    FactRef,
    FactType,
    Op,
    Rulebook,
    RuleSpec,
    Scope,
    Trigger,
    conditions_of,
    facts_in_when,
    placeholders,
)


@dataclass(frozen=True)
class FixedRule:
    """What SPEC section 7 fixes about one rule. The rules file must say the same, or it is rejected."""

    verdict: Verdict
    approver_role: ApproverRole | None  # None: nobody signs off a BLOCK; F-03 takes its role from the missing fact
    scopes: tuple[Scope, ...]  # the rule has one entry per scope; empty for the missing-fact rule, which has none


# SPEC section 7: the rules no profile can switch off and the engine evaluates. F-06 is an access rule.
# Their verdicts and roles are pinned here so that editing the rules file cannot weaken one of them: a
# file that turns a BLOCK into an APPROVAL, or names another approver, does not load.
FIXED_RULES: Mapping[str, FixedRule] = MappingProxyType({
    "F-01": FixedRule(Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER, (Scope.LINE,)),
    "F-02": FixedRule(Verdict.BLOCK, None, (Scope.LINE,)),
    "F-03": FixedRule(Verdict.APPROVAL, None, ()),
    "F-04": FixedRule(Verdict.BLOCK, None, (Scope.ORDER,)),
    "F-05": FixedRule(Verdict.BLOCK, None, (Scope.LINE,)),
    "F-07": FixedRule(Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER, (Scope.LINE, Scope.ORDER)),
    "F-08": FixedRule(Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER, (Scope.LINE,)),
})
NO_ROLE = "none"  # how a rule without an approver role reads in a load error
MISSING_FACT_PLACEHOLDERS = frozenset({"missing.what", "missing.reason", "missing.needed_by"})
DECISION_PLACEHOLDERS = frozenset({"reasons", "roles"})
SUBSTITUTE_SCOPE_VALUES = frozenset({SUBSTITUTE_LISTED, SUBSTITUTE_SAME_CATEGORY})


def validate_rulebook(rulebook: Rulebook, known_facts: Collection[str]) -> list[str]:
    """Every problem of the rules file; empty when it can be used."""
    return [
        *_check_header(rulebook),
        *_check_facts(rulebook, known_facts),
        *_check_rule_set(rulebook),
        *(problem for rule in rulebook.rules for problem in _check_rule(rule, rulebook)),
        *_check_texts(rulebook),
    ]


def _check_header(rulebook: Rulebook) -> list[str]:
    problems: list[str] = []
    if rulebook.verdicts != tuple(Verdict):
        problems.append("verdicts must be [AUTO, APPROVAL, BLOCK], least to most severe")
    if rulebook.defaults.verdict_when_no_rule_fires is not Verdict.AUTO:
        problems.append(
            "defaults.verdict_when_no_rule_fires must be AUTO; to keep a human on every order set "
            "auto_order_enabled to false in the profile (P-00)"
        )
    if rulebook.defaults.on_missing_fact is Verdict.AUTO:
        problems.append("defaults.on_missing_fact must be APPROVAL or BLOCK: a missing fact never passes")
    problems.extend(f"roles: {role.value} is not described" for role in ApproverRole if role not in rulebook.roles)
    for scope in SubstitutionScope:
        if scope not in rulebook.substitution_scopes:
            problems.append(f"substitution_scopes: {scope.value} is not listed")
    for scope, accepted in rulebook.substitution_scopes.items():
        unknown = sorted(set(accepted) - SUBSTITUTE_SCOPE_VALUES)
        if unknown:
            problems.append(f"substitution_scopes.{scope.value}: unknown value {', '.join(unknown)}")
    return problems


def _check_facts(rulebook: Rulebook, known_facts: Collection[str]) -> list[str]:
    declared, readable = set(rulebook.facts), set(known_facts)
    unreadable = [f"fact '{name}' is declared but the engine cannot read it" for name in sorted(declared - readable)]
    undeclared = [f"fact '{name}' is read by the engine but is not declared" for name in sorted(readable - declared)]
    return unreadable + undeclared


def _check_rule_set(rulebook: Rulebook) -> list[str]:
    entries: dict[str, list[RuleSpec]] = {}
    for rule in rulebook.rules:
        entries.setdefault(rule.id, []).append(rule)
    problems = [f"{rule_id}: duplicate id" for rule_id in _duplicate_ids(rulebook, entries)]
    for rule_id, found in entries.items():
        if len({(rule.fixed, rule.title, rule.verdict, rule.approver_role) for rule in found}) > 1:
            problems.append(f"{rule_id}: the entries of one rule must agree on fixed, title, verdict and approver_role")
    for rule_id, pinned in FIXED_RULES.items():
        problems.extend(_check_fixed_rule(rule_id, pinned, entries.get(rule_id, ())))
    return problems + _check_missing_fact_trigger(rulebook)


def _duplicate_ids(rulebook: Rulebook, entries: Mapping[str, Sequence[RuleSpec]]) -> list[str]:
    """A rule judged at two scopes is listed once per scope under one id (F-07); never twice for one scope."""
    duplicates = {rule_id for rule_id, found in entries.items() if len({rule.scope for rule in found}) < len(found)}
    access_ids = [rule.id for rule in rulebook.access_rules]
    duplicates |= {rule_id for rule_id in access_ids if rule_id in entries or access_ids.count(rule_id) > 1}
    return sorted(duplicates)


def _check_fixed_rule(rule_id: str, pinned: FixedRule, entries: Sequence[RuleSpec]) -> list[str]:
    """A fixed rule must be there, in every scope it is judged at, with the verdict and the role pinned in code."""
    if not entries:
        return [f"fixed rule {rule_id} is missing: no file may drop a fixed rule"]
    problems: list[str] = []
    if not all(rule.fixed for rule in entries):
        problems.append(f"{rule_id} must be marked fixed")
    for verdict in dict.fromkeys(rule.verdict for rule in entries if rule.verdict is not pinned.verdict):
        problems.append(
            f"{rule_id}: the verdict of a fixed rule is set in code: {pinned.verdict.value}, not {verdict.value}"
        )
    for role in dict.fromkeys(rule.approver_role for rule in entries if rule.approver_role is not pinned.approver_role):
        problems.append(
            f"{rule_id}: the approver role of a fixed rule is set in code: {_role_name(pinned.approver_role)}, "
            f"not {_role_name(role)}"
        )
    listed = {rule.scope for rule in entries}
    problems.extend(
        f"fixed rule {rule_id} is missing its part judged per {scope.value}: no file may drop a fixed rule"
        for scope in pinned.scopes if scope not in listed
    )
    return problems


def _role_name(role: ApproverRole | None) -> str:
    return NO_ROLE if role is None else role.value


def _check_missing_fact_trigger(rulebook: Rulebook) -> list[str]:
    problems: list[str] = []
    on_missing = [rule for rule in rulebook.rules if rule.trigger is Trigger.MISSING_FACT]
    if len(on_missing) != 1:
        problems.append("exactly one rule must have `trigger: missing_fact`")
    for rule in on_missing:
        if not rule.fixed:
            problems.append(f"{rule.id}: the missing-fact rule must be marked fixed")
        if rule.verdict is not rulebook.defaults.on_missing_fact:
            problems.append(f"{rule.id}: its verdict must equal defaults.on_missing_fact")
    return problems


def _check_rule(rule: RuleSpec, rulebook: Rulebook) -> list[str]:
    problems: list[str] = []
    if rule.verdict is Verdict.AUTO:
        problems.append(f"{rule.id}: a rule asks for a human or blocks; AUTO is what remains when no rule fires")
    if rule.verdict is Verdict.BLOCK and rule.approver_role is not None:
        problems.append(f"{rule.id}: a BLOCK rule has no approver_role, nobody can sign it off")
    problems.extend(_check_authority(rule.id, rule.authority, rulebook, needs_default=True))
    if rule.trigger is Trigger.MISSING_FACT:
        return problems + _check_missing_fact_rule(rule)
    if rule.verdict is Verdict.APPROVAL and rule.approver_role is None:
        problems.append(f"{rule.id}: APPROVAL needs an approver_role")
    if rule.when is None or rule.scope is None:
        return [*problems, f"{rule.id}: a rule needs a `scope` and a `when`"]
    for condition in conditions_of(rule.when):
        problems.extend(f"{rule.id}: {problem}" for problem in _check_condition(condition, rulebook))
    problems.extend(_check_facts_used(rule, rulebook))
    return problems


def _check_missing_fact_rule(rule: RuleSpec) -> list[str]:
    problems: list[str] = []
    if rule.when is not None or rule.scope is not None or rule.approver_role is not None:
        problems.append(
            f"{rule.id}: the missing-fact rule has no `when`, `scope` or `approver_role`; the role comes from the fact"
        )
    unknown = sorted(set(placeholders(rule.message)) - MISSING_FACT_PLACEHOLDERS)
    problems.extend(f"{rule.id}: message uses unknown placeholder '{name}'" for name in unknown)
    return problems


def _check_facts_used(rule: RuleSpec, rulebook: Rulebook) -> list[str]:
    """Scope and fixedness: what a rule may read in its conditions, its message and its records."""
    problems: list[str] = []
    in_conditions = facts_in_when(rule.when)
    for name in placeholders(rule.message):
        if name not in rulebook.facts:
            problems.append(f"{rule.id}: message uses undeclared fact '{name}'")
    for name in rule.records:
        if name not in rulebook.facts:
            problems.append(f"{rule.id}: records undeclared fact '{name}'")
    if rule.scope is Scope.ORDER:
        used = (*in_conditions, *placeholders(rule.message), *rule.records)
        for name in dict.fromkeys(used):
            if name.startswith(LINE_FACT_PREFIX):
                problems.append(f"{rule.id}: an order rule cannot read the line fact '{name}'")
    if rule.fixed:
        for name in in_conditions:
            if name.startswith(PROFILE_FACT_PREFIX):
                problems.append(
                    f"{rule.id}: a fixed rule may not read '{name}': no profile setting can switch a fixed rule off"
                )
    return problems


def _check_condition(condition: Condition, rulebook: Rulebook) -> list[str]:
    spec = rulebook.facts.get(condition.fact)
    if spec is None:
        return [f"undeclared fact '{condition.fact}'"]
    op = condition.op
    if op in UNARY_OPS:
        problems = [f"op '{op.value}' takes no value"] if condition.has_value else []
        if op in TRUTH_OPS and spec.type is not FactType.BOOL:
            problems.append(f"'{op.value}' reads a yes-or-no fact; '{condition.fact}' is a {spec.type.value}")
        if op in LIST_FACT_OPS and spec.type is not FactType.LIST:
            problems.append(f"'{op.value}' reads a list; '{condition.fact}' is a {spec.type.value}")
        return problems
    if not condition.has_value or condition.value is None:
        return [f"op '{op.value}' needs a value"]
    return _check_value(condition, spec.type, rulebook)


def _check_value(condition: Condition, fact_type: FactType, rulebook: Rulebook) -> list[str]:
    op, value = condition.op, condition.value
    other = rulebook.facts.get(value.fact) if isinstance(value, FactRef) else None
    if isinstance(value, FactRef) and other is None:
        return [f"undeclared fact '{value.fact}'"]
    if op in NUMBER_OPS:
        value_is_number = (
            other.type in NUMBER_TYPES if other else isinstance(value, int | float) and not isinstance(value, bool)
        )
        if fact_type not in NUMBER_TYPES or not value_is_number:
            shown = value.fact if isinstance(value, FactRef) else value
            return [f"'{op.value}' compares numbers; '{condition.fact}' with {shown!r} is not such a pair"]
    if op is Op.CONTAINS_ANY and fact_type is not FactType.LIST:
        return [f"'{op.value}' reads a list; '{condition.fact}' is a {fact_type.value}"]
    if op in LIST_VALUE_OPS:
        value_is_list = other.type is FactType.LIST if other else isinstance(value, tuple)
        if not value_is_list:
            return [f"op '{op.value}' needs a list as its value"]
    return []


def _check_authority(
    owner: str, texts: tuple[AuthorityText, ...], rulebook: Rulebook, needs_default: bool
) -> list[str]:
    """Authority texts describe a profile: they may read `profile.*` facts and nothing else."""
    problems: list[str] = []
    if needs_default and (not texts or texts[-1].when is not None):
        problems.append(f"{owner}: the last authority text must have no `when`, so that every profile gets a sentence")
    for text in texts:
        for name in dict.fromkeys((*facts_in_when(text.when), *placeholders(text.text))):
            if name not in rulebook.facts or not name.startswith(PROFILE_FACT_PREFIX):
                problems.append(f"{owner}: an authority text may only read declared profile facts, not '{name}'")
        if text.when is not None:
            for condition in conditions_of(text.when):
                problems.extend(f"{owner}: authority: {problem}" for problem in _check_condition(condition, rulebook))
    return problems


def _check_texts(rulebook: Rulebook) -> list[str]:
    problems = _check_authority("authority.summary", rulebook.authority.summary, rulebook, needs_default=False)
    for verdict in Verdict:
        template = rulebook.decision_sentences.get(verdict)
        if template is None:
            problems.append(f"decision_sentences: no sentence for {verdict.value}")
            continue
        for name in placeholders(template):
            is_order_fact = name in rulebook.facts and not name.startswith(LINE_FACT_PREFIX)
            if name not in DECISION_PLACEHOLDERS and not is_order_fact:
                problems.append(f"decision_sentences.{verdict.value}: unknown placeholder '{name}'")
    return problems
