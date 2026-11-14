"""The policy engine: deterministic, read from data, with no model anywhere near a verdict.

`evaluate` judges one offer option for one buyer profile: every rule of `rules.yaml` is evaluated,
every rule that fires is listed with its sentence and the facts it read, the most severe verdict wins,
and a fact that is missing sends the order to a human (F-03) instead of passing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from tta.contracts.common import ApproverRole, JsonDict, Verdict, most_severe
from tta.contracts.errors import NotAuthorised
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import Authority, BuyerProfile, FiredRule, PolicyContext, PolicyDecision, RuleSummary
from tta.policy.conditions import Truth, evaluate
from tta.policy.facts import Missing, OrderScope, Reading, read_fact, read_profile_fact
from tta.policy.hashing import policy_hash
from tta.policy.loading import PROFILES_DIR, RULES_PATH, load_rulebook
from tta.policy.profiles import load_profiles
from tta.policy.rulebook import AuthorityText, FactType, Rulebook, RuleSpec, Scope, Trigger, facts_read_by
from tta.policy.sentences import format_fact, render, to_json
from tta.policy.text import as_sentence, join_words

Lookup = Callable[[str], Reading]


@dataclass(frozen=True)
class _Finding:
    """One fired rule with its place in the rules file and its reason as a clause."""

    order: int
    clause: str
    rule: FiredRule


@dataclass(frozen=True)
class _Gap:
    """One fact that left one rule unknown, on one line or on the order."""

    fact: str
    reason: str
    rule_id: str
    line: OfferLine | None
    line_index: int | None


class RulePolicyEngine:
    """Implements the `PolicyEngine` port over a checked rulebook and the loaded buyer profiles."""

    def __init__(self, rulebook: Rulebook, profiles: Iterable[BuyerProfile]) -> None:
        self._rulebook = rulebook
        self._canonical_rules: JsonDict = rulebook.canonical()
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._missing_fact_rule = next(rule for rule in rulebook.rules if rule.trigger is Trigger.MISSING_FACT)

    @classmethod
    def from_files(cls, rules_path: Path = RULES_PATH, profiles_dir: Path = PROFILES_DIR) -> RulePolicyEngine:
        """Load and check the rules and every profile. Raises `PolicyLoadError`; nothing broken is skipped."""
        rulebook = load_rulebook(rules_path)
        return cls(rulebook, load_profiles(profiles_dir, rulebook.fixed_rule_ids).values())

    def get_profile(self, profile_id: str) -> BuyerProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise NotAuthorised("No buyer profile is set up for this caller.")
        return profile

    def profile_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))

    def policy_hash(self, profile: BuyerProfile) -> str:
        return policy_hash(self._canonical_rules, profile)

    def evaluate(self, option: OfferOption, profile: BuyerProfile, context: PolicyContext) -> PolicyDecision:
        scope = OrderScope(option, profile, context, self._rulebook.substitution_scopes)
        findings: list[_Finding] = []
        gaps: list[_Gap] = []
        for order, rule in enumerate(self._rulebook.rules):
            if rule.when is None:
                continue  # the missing-fact rule fires from the gaps the other rules leave
            for line_index, line in _targets(rule, option):
                read = partial(read_fact, scope=scope, line=line)
                outcome = evaluate(rule.when, read)
                if outcome.truth is Truth.TRUE:
                    findings.append(self._finding(order, rule, read, line))
                elif outcome.truth is Truth.UNKNOWN:
                    gaps.extend(_Gap(name, _reason(read(name)), rule.id, line, line_index) for name in outcome.missing)
        every = [*findings, *self._missing_fact_findings(gaps)]
        in_file_order = sorted(every, key=lambda finding: finding.order)  # stable: line order is kept within a rule
        return self._decision(in_file_order, scope)

    def describe_authority(self, profile: BuyerProfile) -> Authority:
        read = partial(read_profile_fact, profile=profile, substitution_scopes=self._rulebook.substitution_scopes)
        rules = tuple(
            RuleSummary(
                rule_id=rule.id, title=rule.title, fixed=rule.fixed, verdict=rule.verdict,
                approver_role=rule.approver_role, sentence=self._text(_first_that_holds(rule.authority, read), read),
            )
            for rule in self._rulebook.rules
        )
        section = self._rulebook.authority
        summary = [self._text(text, read) for text in section.summary if _holds(text, read)]
        summary.extend(rule.text for rule in self._rulebook.access_rules)
        return Authority(
            profile=profile, rules=rules, summary=tuple(summary), policy_hash=self.policy_hash(profile),
            note=section.note,
        )

    # --- one fired rule -------------------------------------------------------------------------------

    def _finding(self, order: int, rule: RuleSpec, read: Lookup, line: OfferLine | None) -> _Finding:
        clause = render(rule.message, lambda name: self._format(name, read))
        fired = FiredRule(
            rule_id=rule.id,
            title=rule.title,
            fixed=rule.fixed,
            verdict=rule.verdict,
            approver_role=rule.approver_role,
            sentence=as_sentence(clause),
            facts={name: to_json(read(name), self._type_of(name)) for name in facts_read_by(rule)},
            product_id=line.product_id if line is not None else None,
        )
        return _Finding(order, clause, fired)

    def _missing_fact_findings(self, gaps: list[_Gap]) -> list[_Finding]:
        """One F-03 entry per missing fact and line, naming every rule that needed it."""
        rule = self._missing_fact_rule
        order = self._rulebook.rules.index(rule)
        grouped: dict[tuple[str, int | None], list[_Gap]] = {}
        for gap in gaps:
            grouped.setdefault((gap.fact, gap.line_index), []).append(gap)
        findings: list[_Finding] = []
        for group in grouped.values():
            first = group[0]
            needed_by = list(dict.fromkeys(gap.rule_id for gap in group))
            spec = self._rulebook.facts[first.fact]
            words = {
                "missing.what": spec.label + (f" of {first.line.name} ({first.line.product_id})" if first.line else ""),
                "missing.reason": first.reason,
                "missing.needed_by": f"{'rule' if len(needed_by) == 1 else 'rules'} {join_words(needed_by)}",
            }
            clause = render(rule.message, lambda name, words=words: words.get(name, name))
            fired = FiredRule(
                rule_id=rule.id,
                title=rule.title,
                fixed=rule.fixed,
                verdict=rule.verdict,
                approver_role=spec.missing_role or self._rulebook.defaults.missing_fact_approver_role,
                sentence=as_sentence(clause),
                facts={"missing_fact": first.fact, "reason": first.reason, "needed_by": needed_by},
                product_id=first.line.product_id if first.line else None,
            )
            findings.append(_Finding(order, clause, fired))
        return findings

    # --- the decision ---------------------------------------------------------------------------------

    def _decision(self, findings: list[_Finding], scope: OrderScope) -> PolicyDecision:
        fired = tuple(finding.rule for finding in findings)
        verdict = most_severe([rule.verdict for rule in fired])
        roles = _required_roles(verdict, fired)
        deciding = [
            f"{finding.clause} ({finding.rule.rule_id})" for finding in findings if finding.rule.verdict is verdict
        ]
        words = {
            "reasons": join_words(deciding),
            "roles": join_words([self._rulebook.roles[role].name for role in roles]),
        }
        read = partial(read_fact, scope=scope)
        sentence = render(
            self._rulebook.decision_sentences[verdict],
            lambda name: words[name] if name in words else self._format(name, read),
        )
        return PolicyDecision(
            verdict=verdict,
            fired=fired,
            required_roles=roles,
            policy_hash=self.policy_hash(scope.profile),
            profile_id=scope.profile.profile_id,
            evaluated_at=scope.context.now,
            sentence=sentence,
        )

    # --- texts ----------------------------------------------------------------------------------------

    def _type_of(self, name: str) -> FactType:
        return self._rulebook.facts[name].type

    def _format(self, name: str, read: Lookup) -> str:
        return format_fact(read(name), self._type_of(name))

    def _text(self, text: AuthorityText, read: Lookup) -> str:
        return render(text.text, lambda name: self._format(name, read))


def _targets(rule: RuleSpec, option: OfferOption) -> list[tuple[int | None, OfferLine | None]]:
    """What a rule is judged against: each line for a line rule, the option once for an order rule."""
    if rule.scope is Scope.LINE:
        return list(enumerate(option.lines))
    return [(None, None)]


def _reason(reading: Reading) -> str:
    return reading.reason if isinstance(reading, Missing) else "it could not be read"


def _required_roles(verdict: Verdict, fired: tuple[FiredRule, ...]) -> tuple[ApproverRole, ...]:
    """Who must sign: the roles of every rule that asks for a human. Nobody can sign off a BLOCK."""
    if verdict is not Verdict.APPROVAL:
        return ()
    asked = {rule.approver_role for rule in fired if rule.verdict is Verdict.APPROVAL}
    return tuple(role for role in ApproverRole if role in asked)


def _holds(text: AuthorityText, read: Lookup) -> bool:
    return text.when is None or evaluate(text.when, read).truth is Truth.TRUE


def _first_that_holds(texts: tuple[AuthorityText, ...], read: Lookup) -> AuthorityText:
    """The loader guarantees that the last text has no `when`, so one always holds."""
    return next(text for text in texts if _holds(text, read))
