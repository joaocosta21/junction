"""Load and validate AIMO/policy/policy.yaml, and compute its hash.

Not the engine (that comes in Fase 1) — this only guarantees the policy file is
well-formed, so the engine, the log and the approval panel can rely on it.

    python AIMO/policy/policy_check.py          # validate and print the hash
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

POLICY_PATH = Path(__file__).resolve().parent / "policy.yaml"
OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in",
       "is_true", "is_false", "contains_any", "not_empty"}
UNARY_OPS = {"is_true", "is_false", "not_empty"}
PLACEHOLDER = re.compile(r"\{([a-z_]+\.[a-z_]+)\}")


def load_policy(path=POLICY_PATH):
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def policy_hash(policy):
    """SHA-256 of the canonical JSON form: comments and whitespace do not change it."""
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _conditions(when):
    for key in ("all", "any"):
        for cond in (when or {}).get(key, []):
            if "all" in cond or "any" in cond:
                yield from _conditions(cond)
            else:
                yield cond


def validate(policy):
    """Return a list of problems; empty means the policy is valid."""
    problems = []
    verdicts = policy.get("verdicts") or []
    roles = set(policy.get("roles") or {})
    params = set(policy.get("params") or {})
    facts = set(policy.get("facts") or {})

    for key in ("policy_id", "version", "verdicts", "defaults", "params", "roles", "facts", "rules"):
        if key not in policy:
            problems.append(f"missing top-level key: {key}")
    for key in ("verdict_when_no_rule_fires", "on_missing_fact"):
        if (policy.get("defaults") or {}).get(key) not in verdicts:
            problems.append(f"defaults.{key} must be one of {verdicts}")

    seen = set()
    for rule in policy.get("rules") or []:
        rid = rule.get("id", "<no id>")
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)
        for key in ("title", "scope", "when", "verdict", "message", "justification"):
            if not rule.get(key):
                problems.append(f"{rid}: missing {key}")
        if rule.get("scope") not in ("line", "order"):
            problems.append(f"{rid}: scope must be line or order")
        if rule.get("verdict") not in verdicts:
            problems.append(f"{rid}: unknown verdict {rule.get('verdict')!r}")
        if rule.get("verdict") == "APPROVAL" and rule.get("approver_role") not in roles:
            problems.append(f"{rid}: APPROVAL needs an approver_role from roles")
        conds = list(_conditions(rule.get("when")))
        if not conds:
            problems.append(f"{rid}: `when` has no conditions")
        for cond in conds:
            if cond.get("fact") not in facts:
                problems.append(f"{rid}: undeclared fact {cond.get('fact')!r}")
            if cond.get("op") not in OPS:
                problems.append(f"{rid}: unknown op {cond.get('op')!r}")
            if cond.get("op") not in UNARY_OPS and "value" not in cond:
                problems.append(f"{rid}: op {cond.get('op')!r} needs a value")
            value = cond.get("value")
            if isinstance(value, dict) and value.get("param") not in params:
                problems.append(f"{rid}: unknown param {value.get('param')!r}")
        for ref in PLACEHOLDER.findall(rule.get("message") or ""):
            scope, name = ref.split(".", 1)
            if scope == "params" and name not in params:
                problems.append(f"{rid}: message uses unknown param {ref!r}")
            elif scope != "params" and ref not in facts:
                problems.append(f"{rid}: message uses undeclared fact {ref!r}")
    return problems


def main():
    policy = load_policy()
    problems = validate(policy)
    for p in problems:
        print("ERROR", p, file=sys.stderr)
    todo = sorted(k for k, v in policy["facts"].items() if v.get("status") == "todo")
    print(f"{policy['policy_id']} v{policy['version']}  {policy_hash(policy)}")
    print(f"{len(policy['rules'])} rules · {len(policy['facts'])} facts ({len(todo)} still todo)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
