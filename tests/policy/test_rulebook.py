"""The rules file: its shape, the checks made when it is loaded, and what Friday's file had to drop."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, Verdict
from tta.policy import RULES_PATH, PolicyLoadError, load_rulebook, parse_rulebook
from tta.policy.facts import KNOWN_FACTS
from tta.policy.rulebook import facts_read_by

SPEC_RULES = {
    "F-01": (True, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "F-02": (True, Verdict.BLOCK, None),
    "F-03": (True, Verdict.APPROVAL, None),  # the role comes from the fact that is missing
    "F-04": (True, Verdict.BLOCK, None),
    "F-05": (True, Verdict.BLOCK, None),
    "P-00": (False, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "P-01": (False, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "P-02": (False, Verdict.APPROVAL, ApproverRole.FINANCE),
    "P-03": (False, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "P-04": (False, Verdict.APPROVAL, ApproverRole.DIETITIAN),
    "P-05": (False, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "P-06": (False, Verdict.APPROVAL, ApproverRole.PURCHASING_MANAGER),
    "P-07": (False, Verdict.APPROVAL, ApproverRole.FINANCE),
}


def _rule(data: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(rule for rule in data["rules"] if rule["id"] == rule_id)


def test_the_shipped_rules_are_exactly_those_of_the_spec() -> None:
    rulebook = load_rulebook(RULES_PATH)

    assert {rule.id: (rule.fixed, rule.verdict, rule.approver_role) for rule in rulebook.rules} == SPEC_RULES
    assert [rule.id for rule in rulebook.rules] == sorted(SPEC_RULES)
    assert [rule.id for rule in rulebook.access_rules] == ["F-06"]
    assert rulebook.fixed_rule_ids == frozenset({"F-01", "F-02", "F-03", "F-04", "F-05", "F-06"})


def test_verdicts_run_from_least_to_most_severe_and_a_missing_fact_never_passes() -> None:
    rulebook = load_rulebook(RULES_PATH)

    assert rulebook.verdicts == (Verdict.AUTO, Verdict.APPROVAL, Verdict.BLOCK)
    assert rulebook.defaults.verdict_when_no_rule_fires is Verdict.AUTO
    assert rulebook.defaults.on_missing_fact is Verdict.APPROVAL


def test_every_rule_reads_declared_facts_and_every_declared_fact_can_be_read() -> None:
    rulebook = load_rulebook(RULES_PATH)

    assert set(rulebook.facts) == set(KNOWN_FACTS)
    for rule in rulebook.rules:
        assert set(facts_read_by(rule)) <= set(rulebook.facts), rule.id


def test_no_fixed_rule_reads_a_profile_setting() -> None:
    rulebook = load_rulebook(RULES_PATH)

    for rule in rulebook.rules:
        if rule.fixed and rule.when is not None:
            assert not [name for name in facts_read_by(rule) if name.startswith("profile.")], rule.id


def test_every_rule_carries_a_title_a_message_a_justification_and_a_plain_summary() -> None:
    for rule in load_rulebook(RULES_PATH).rules:
        assert rule.title and rule.message and rule.justification and rule.authority, rule.id


def test_what_the_plan_supersedes_is_gone(rules_data: Callable[[], dict[str, Any]]) -> None:
    data = rules_data()
    text = str(data)

    assert "params" not in data and "sentinel" not in text  # no sentinel threshold: F-01 always asks a human
    assert "approval" not in data and "closing_time" not in text  # no contradicted-closing-time setting
    assert "trust_findings" not in data
    assert "X99" not in text and "unspecified_allergen" not in text  # X99 is not blocked


def _break(data: dict[str, Any], case: str) -> None:
    if case == "duplicate id":
        data["rules"].append(dict(_rule(data, "P-01")))
    elif case == "undeclared fact in a condition":
        _rule(data, "P-01")["when"]["all"][0]["fact"] = "option.typo"
    elif case == "undeclared fact in a message":
        _rule(data, "P-01")["message"] = "the total is {option.typo}"
    elif case == "unknown operator":
        _rule(data, "P-01")["when"]["all"][0]["op"] = "roughly"
    elif case == "approval without a role":
        del _rule(data, "P-01")["approver_role"]
    elif case == "unknown role":
        _rule(data, "P-01")["approver_role"] = "nobody"
    elif case == "fixed rule reads a profile setting":
        _rule(data, "F-01")["when"]["all"].append({"fact": "profile.auto_order_enabled", "op": "is_false"})
    elif case == "fixed rule removed":
        data["rules"] = [rule for rule in data["rules"] if rule["id"] != "F-02"]
    elif case == "fixed rule no longer fixed":
        _rule(data, "F-05")["fixed"] = False
    elif case == "rule with the verdict AUTO":
        _rule(data, "F-01")["verdict"] = "AUTO"
    elif case == "missing fact passes":
        data["defaults"]["on_missing_fact"] = "AUTO"
    elif case == "order rule reads a line fact":
        _rule(data, "P-01")["when"]["all"].append({"fact": "line.has_deposits", "op": "is_true"})
    elif case == "fact nobody can read":
        data["facts"]["line.typo"] = {"type": "bool", "source": "option", "label": "a typo"}
    elif case == "number compared with a word":
        _rule(data, "P-01")["when"]["all"][0]["value"] = "a lot"
    elif case == "condition without a value":
        del _rule(data, "P-01")["when"]["all"][0]["value"]
    elif case == "no unconditional summary":
        _rule(data, "P-00")["authority"] = _rule(data, "P-00")["authority"][:1]
    elif case == "verdicts out of order":
        data["verdicts"] = ["BLOCK", "APPROVAL", "AUTO"]
    elif case == "unknown key":
        data["sentinel_qty_threshold"] = 100
    elif case == "no missing-fact rule":
        data["rules"] = [rule for rule in data["rules"] if rule["id"] != "F-03"]
    elif case == "missing-fact rule with a condition":
        _rule(data, "F-03")["when"] = {"all": [{"fact": "context.at_order_time", "op": "is_true"}]}
    elif case == "missing-fact rule with a weaker verdict than the default":
        data["defaults"]["on_missing_fact"] = "BLOCK"
    elif case == "missing-fact message with an unknown placeholder":
        _rule(data, "F-03")["message"] = "{missing.colour} is missing"
    elif case == "block rule with a role":
        _rule(data, "F-02")["approver_role"] = "dietitian"
    elif case == "rule without a scope":
        del _rule(data, "P-01")["scope"]
    elif case == "undeclared fact as a value":
        _rule(data, "P-01")["when"]["all"][0]["value"] = {"fact": "profile.typo"}
    elif case == "undeclared fact in records":
        _rule(data, "P-02")["records"] = ["context.typo"]
    elif case == "value on an operator that takes none":
        _rule(data, "P-00")["when"]["all"][0]["value"] = True
    elif case == "yes-or-no operator on a number":
        _rule(data, "P-00")["when"]["all"][0]["fact"] = "profile.max_order_net_eur"
    elif case == "list operator on a yes-or-no fact":
        _rule(data, "P-00")["when"]["all"][0] = {"fact": "profile.auto_order_enabled", "op": "not_empty"}
    elif case == "contains_any on a text":
        _rule(data, "P-04")["when"]["all"][0]["fact"] = "line.name"
    elif case == "in without a list":
        _rule(data, "P-05")["when"]["all"][1]["value"] = "SAME_CATEGORY"
    elif case == "authority text reads the option":
        _rule(data, "P-01")["authority"][0]["text"] = "Above €{option.net_eur} a human decides."
    elif case == "summary reads the option":
        data["authority"]["summary"][2]["text"] = "The total is €{option.net_eur}."
    elif case == "decision sentence with an unknown placeholder":
        data["decision_sentences"]["BLOCK"] = "Blocked: {excuses}."
    elif case == "decision sentence reads a line":
        data["decision_sentences"]["AUTO"] = "Ordered {line.name}."
    elif case == "no sentence for a verdict":
        del data["decision_sentences"]["BLOCK"]
    elif case == "role without a description":
        del data["roles"]["finance"]
    elif case == "substitution scope missing":
        del data["substitution_scopes"]["NONE"]
    elif case == "substitution scope with an unknown value":
        data["substitution_scopes"]["SAME_CATEGORY"] = ["ANYTHING"]
    elif case == "something else than AUTO when no rule fires":
        data["defaults"]["verdict_when_no_rule_fires"] = "APPROVAL"
    elif case == "access rule reuses an id":
        data["access_rules"][0]["id"] = "F-01"
    elif case == "a group with all and any":
        _rule(data, "P-06")["when"]["any"] = [{"fact": "line.has_deposits", "op": "is_true"}]
    else:  # pragma: no cover
        raise AssertionError(case)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("duplicate id", "P-01: duplicate id"),
        ("undeclared fact in a condition", "P-01: undeclared fact 'option.typo'"),
        ("undeclared fact in a message", "P-01: message uses undeclared fact 'option.typo'"),
        ("unknown operator", "roughly"),
        ("approval without a role", "P-01: APPROVAL needs an approver_role"),
        ("unknown role", "nobody"),
        ("fixed rule reads a profile setting", "F-01: a fixed rule may not read 'profile.auto_order_enabled'"),
        ("fixed rule removed", "fixed rule F-02 is missing"),
        ("fixed rule no longer fixed", "F-05 must be marked fixed"),
        ("rule with the verdict AUTO", "F-01: a rule asks for a human or blocks"),
        ("missing fact passes", "on_missing_fact"),
        ("order rule reads a line fact", "P-01: an order rule cannot read the line fact 'line.has_deposits'"),
        ("fact nobody can read", "fact 'line.typo' is declared but the engine cannot read it"),
        ("number compared with a word", "P-01: 'gt' compares numbers"),
        ("condition without a value", "P-01: op 'gt' needs a value"),
        ("no unconditional summary", "P-00: the last authority text must have no `when`"),
        ("verdicts out of order", "verdicts"),
        ("unknown key", "sentinel_qty_threshold"),
        ("no missing-fact rule", "F-03"),
        ("missing-fact rule with a condition", "F-03: the missing-fact rule has no `when`"),
        ("missing-fact rule with a weaker verdict than the default", "F-03: its verdict must equal"),
        ("missing-fact message with an unknown placeholder", "F-03: message uses unknown placeholder"),
        ("block rule with a role", "F-02: a BLOCK rule has no approver_role"),
        ("rule without a scope", "P-01: a rule needs a `scope` and a `when`"),
        ("undeclared fact as a value", "P-01: undeclared fact 'profile.typo'"),
        ("undeclared fact in records", "P-02: records undeclared fact 'context.typo'"),
        ("value on an operator that takes none", "P-00: op 'is_false' takes no value"),
        ("yes-or-no operator on a number", "P-00: 'is_false' reads a yes-or-no fact"),
        ("list operator on a yes-or-no fact", "P-00: 'not_empty' reads a list"),
        ("contains_any on a text", "P-04: 'contains_any' reads a list"),
        ("in without a list", "P-05: op 'not_in' needs a list as its value"),
        ("authority text reads the option", "P-01: an authority text may only read declared profile facts"),
        ("summary reads the option", "authority.summary: an authority text may only read declared profile facts"),
        ("decision sentence with an unknown placeholder", "decision_sentences.BLOCK: unknown placeholder 'excuses'"),
        ("decision sentence reads a line", "decision_sentences.AUTO: unknown placeholder 'line.name'"),
        ("no sentence for a verdict", "decision_sentences: no sentence for BLOCK"),
        ("role without a description", "roles: finance is not described"),
        ("substitution scope missing", "substitution_scopes: NONE is not listed"),
        ("substitution scope with an unknown value", "substitution_scopes.SAME_CATEGORY: unknown value ANYTHING"),
        ("something else than AUTO when no rule fires", "verdict_when_no_rule_fires must be AUTO"),
        ("access rule reuses an id", "F-01: duplicate id"),
        ("a group with all and any", "exactly one of `all` or `any`"),
    ],
)
def test_the_loader_catches_a_broken_rules_file(
    case: str, message: str, rules_data: Callable[[], dict[str, Any]]
) -> None:
    data = rules_data()
    _break(data, case)

    with pytest.raises(PolicyLoadError) as raised:
        parse_rulebook(data)

    assert message in str(raised.value)


def test_every_problem_of_a_broken_file_is_reported_at_once(rules_data: Callable[[], dict[str, Any]]) -> None:
    data = rules_data()
    _break(data, "duplicate id")
    _break(data, "undeclared fact in a message")
    _break(data, "fixed rule removed")

    with pytest.raises(PolicyLoadError) as raised:
        parse_rulebook(data)

    assert len(raised.value.problems) >= 3


def test_a_rules_file_that_is_not_a_mapping_is_rejected(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("- not\n- a mapping\n", encoding="utf-8")

    with pytest.raises(PolicyLoadError):
        load_rulebook(path)


def test_a_rules_file_that_does_not_exist_is_rejected(tmp_path) -> None:
    with pytest.raises(PolicyLoadError, match="cannot be read"):
        load_rulebook(tmp_path / "nowhere.yaml")
