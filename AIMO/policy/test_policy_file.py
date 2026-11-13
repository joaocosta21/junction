import copy

from policy_check import load_policy, policy_hash, validate


def test_policy_is_valid():
    assert validate(load_policy()) == []


def test_hash_ignores_key_order_but_not_content():
    policy = load_policy()
    reordered = dict(reversed(list(policy.items())))
    assert policy_hash(reordered) == policy_hash(policy)
    changed = copy.deepcopy(policy)
    changed["params"]["auto_spend_cap_eur"] += 1
    assert policy_hash(changed) != policy_hash(policy)


def test_bio1_fields_are_declared_as_existing():
    # Names must match AIMO/catalog_search.py candidate records (branch bio1).
    facts = load_policy()["facts"]
    for name in ("id", "name", "category", "sales_unit", "allowed_lot_size",
                 "litres_per_sales_unit", "volume_source"):
        assert facts[f"line.{name}"]["source"] == "bio1_catalog"
        assert facts[f"line.{name}"]["status"] == "exists"


def test_never_cut_rules_present():
    ids = {r["id"] for r in load_policy()["rules"]}
    # spend cap, allergens (contains / may contain / silent / X99), variable weight
    assert {"P-01", "P-02", "P-03a", "P-04", "P-05", "P-06"} <= ids


def test_missing_fact_never_auto():
    assert load_policy()["defaults"]["on_missing_fact"] != "AUTO"


def test_validator_catches_mistakes():
    bad = copy.deepcopy(load_policy())
    bad["rules"].append(copy.deepcopy(bad["rules"][0]))                 # duplicate id
    bad["rules"][1]["when"]["all"][0]["fact"] = "line.typo"              # undeclared fact
    bad["rules"][0]["approver_role"] = "nobody"                          # unknown role
    problems = "\n".join(validate(bad))
    assert "duplicate id" in problems
    assert "undeclared fact 'line.typo'" in problems
    assert "approver_role" in problems
