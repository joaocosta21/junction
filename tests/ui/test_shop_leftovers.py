"""The shop page's small leftovers (lane G3): each one serves "used and intuitive".

Scores on the 20% "solving the problem and user need" (stock said in pieces, a tag that agrees with its sentence, a
sentence that says who decided the recipe matters) and the 20% "autonomy and controls" (one person is named once,
with no role label; the manufacturer's page is beside the allergen question wherever it is asked; a standing order
that was set up is listed). Through the shop's routes in replay at the recording's own clock (Saturday 14 Nov 2026
02:52), and by reading the page's scripts; two pure functions of the page are run with node when it is installed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.evidence.answers import AnswersClient

API = "/shop/api"
SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
MONDAY = "2026-11-16"
CUSTOMER_OF = {"hotel": "hotel-kitchen", "bakery": "bakery-cafe"}
# The hotel's own example of the page: Valio Aimo's data states nothing about milk for 469512 (rule P-04).
OAT = {
    "needed_by": MONDAY,
    "lines": [{"text": "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk",
               "product_ids": ["469512"], "quantity": 100, "unit": "L", "exclude_allergens": ["AM"],
               "allergen_strictness": "STRICT"}],
}
DOUBTFUL = "469512"
# The hotel uses cream as an ingredient (its customer file): in the mode LEARN the gateway adds the recipe check.
CREAM_100 = {"needed_by": MONDAY, "lines": [
    {"text": "100 L of whipping cream 469346", "product_ids": ["469346"], "quantity": 100, "unit": "L"}]}
CREAM_20 = {"needed_by": MONDAY, "lines": [
    {"text": "20 L whipping cream", "product_type": "cream", "quantity": 20, "unit": "L"}]}
REQUEST_SAYS = "the request says the formula matters"
LEARNED_SAYS = "what the agent learned about your orders says the formula matters"


def _read(name: str) -> str:
    return (SHOP_JS / name).read_text(encoding="utf-8")


def _call(client: TestClient, method: str, path: str, kitchen: str, **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _set_up(client: TestClient, kitchen: str, settings: dict[str, dict[str, Any]], **change: Any) -> None:
    saved = _call(client, "PUT", "/kitchen", kitchen, json={**settings[CUSTOMER_OF[kitchen]], **change})
    assert saved.status_code == 200, saved.text


def _offer(client: TestClient, kitchen: str, request: dict[str, Any]) -> Any:
    answer = _call(client, "POST", "/offers", kitchen, json=request)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _node(script: str) -> Any:
    """What a script prints as JSON, run by node; the test is skipped where node is not installed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    # The script is this file's own text around a function of the page's source: nothing from outside is run.
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# --- 1. stock is said in pieces ------------------------------------------------------------------------------


def test_the_stock_line_counts_packs_in_pieces_whatever_the_pack_is() -> None:
    parts = _read("views/parts.js")
    found = re.search(r"export const stockUnit = .*;\n", parts)
    assert found is not None and "const u = stockUnit(a.sales_unit);" in parts

    units = _node(
        'const unit = (code) => ({ KG: "kg", L: "l", PS: "bag", RS: "box", KI: "crt" })[code];\n'
        + found.group(0).replace("export ", "")
        + 'console.log(JSON.stringify(["PS", "RS", "KI", "ST", "KG", "L", undefined].map(stockUnit)));'
    )

    assert units == ["pcs", "pcs", "pcs", "pcs", "kg", "l", "pcs"]  # "976 pcs available in storage", never "976 bag"


# --- 2. one person confirms: a name, and a role only for a second person -------------------------------------


def test_a_person_is_named_once_and_a_role_is_said_only_for_somebody_else() -> None:
    parts, settings, plan, trail = (_read(f"views/{name}.js") for name in ("parts", "settings", "plan", "trail"))

    # Settings: who is signed in and who confirms, by name; a line per role only for another person (the dietitian).
    assert "· ${me.title}" not in settings and "Object.entries(ROLES).map" not in settings
    assert "<span>Confirms orders</span><b>${me.name} (you)</b>" in settings
    assert "otherPeople(Object.keys(ROLES))" in settings
    assert "(finance) approves" not in settings and "Ask finance" not in settings
    # An order's signers and a plan's "Needs …": each person once, a role only for somebody who is not signed in.
    assert "${name} · ${ROLES[role] || role}" not in parts and "(${roleWord(r)})" not in parts
    assert "const isMe = (name) => name === contact()?.name;" in parts
    assert "listed(peopleFor(roles))" in plan and "ROLES" not in plan and "roleWord" not in plan
    # Valio Aimo's view names a role only where a second person of the buyer holds it, and never a name.
    assert '"a person of the buyer confirms"' in trail and "hasPerson(role) && !isMine(role)" in trail


# --- 3. the manufacturer's page beside the allergen question asked on the result -----------------------------


def _never(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("Context.dev must not be asked: the route reads recordings only")


def test_the_recorded_manufacturers_page_is_read_for_a_question_asked_before_any_approval(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AnswersClient, "ask", _never)
    _set_up(client, "hotel", shop_profile_settings)
    offer = _offer(client, "hotel", OAT)
    asked = next(one for one in offer["options"] if [line["product_id"] for line in one["lines"]] == [DOUBTFUL])
    # The question is asked as before: the evidence changes no decision and makes no allergen question disappear.
    fired = asked["decision"]["fired"]
    assert any(rule["rule_id"] == "P-04" and rule["approver_role"] == "dietitian" for rule in fired)

    answer = _call(client, "GET", f"/evidence?offer_id={offer['offer_id']}&option_id={asked['option_id']}", "hotel")

    assert answer.status_code == 200, answer.text
    (found,) = answer.json()
    assert (found["product_id"], found["found"]) == (DOUBTFUL, True)
    assert found["source_url"].startswith("https://") and found["sentence"]
    assert _call(client, "GET", "/approvals", "hotel").json() == []  # no approval exists, and nothing is ordered
    assert _call(client, "GET", "/orders", "hotel").json() == []
    again = _call(client, "GET", f"/offers/{offer['offer_id']}", "hotel").json()
    assert again["options"] == offer["options"]  # no status and no decision changed


def test_an_option_that_asks_no_allergen_question_has_no_evidence_and_another_book_reads_none(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings)
    _set_up(client, "bakery", shop_profile_settings)
    offer = _offer(client, "hotel", OAT)
    plain = next(one for one in offer["options"]
                 if not any(rule["rule_id"] == "P-04" for rule in one["decision"]["fired"]))
    path = f"/evidence?offer_id={offer['offer_id']}&option_id="

    assert _call(client, "GET", path + plain["option_id"], "hotel").json() == []
    assert _call(client, "GET", path + "opt_99", "hotel").status_code == 404
    assert _call(client, "GET", path + plain["option_id"], "bakery").status_code == 404  # another customer's book
    assert _call(client, "GET", "/evidence?offer_id=" + offer["offer_id"], "hotel").status_code == 422


def test_the_page_shows_the_evidence_with_the_question_on_the_result_and_on_the_waiting_page() -> None:
    question, assistant, approvals, evidence = (
        _read(f"views/{name}.js") for name in ("question", "assistant", "approvals", "evidence")
    )

    own = question.split("export function ownQuestion", 1)[1]
    assert own.index("${evidenceFor(turn, option)}") < own.index('<ol class="choices">')  # read before choosing
    # Lane FP-Z: read from the book of the customer the request was sent for (`who`), whatever is switched to since.
    assert "loadOwnEvidence(turn, who);" in assistant and "evidenceBlock(approval)" in approvals
    assert "Found on the web, not Valio Aimo data" in evidence and "this changes no status and no decision" in evidence
    assert "/evidence?offer_id=${q(offerId)}&option_id=${q(optionId)}" in _read("api.js")


# --- 5. a suggestion's tag says what its sentence says --------------------------------------------------------


def test_valio_aimos_suggestion_carries_the_figures_its_tag_reads(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    """The bakery's usual Oatly iKaffe 0.5 L against the 1.5 L pack: both figures of the sentence are right. €44.40
    is what the new line adds to this order; €42.00 is what it saves against the usual product at the usual 30 L."""
    _set_up(client, "bakery", shop_profile_settings)
    offer = _offer(client, "bakery", CREAM_20)

    (suggestion,) = [one for one in offer["suggestions"] if one["kind"] == "FROM_SUPPLIER"]

    assert suggestion["request_line_index"] is None  # accepting adds a line: it takes the place of none
    assert "€1.48 a litre instead of €2.88. For your usual 30 L: €44.40, €42.00 less." in suggestion["sentence"]
    effect = suggestion["effect"]
    assert (effect["net_change_eur"], effect["measure"]) == (44.4, "L")
    assert (effect["unit_price_before_eur"], effect["unit_price_after_eur"]) == (2.88, 1.48)
    assert effect["saving_ratio"] > 0


def test_a_suggestion_that_adds_a_line_is_never_tagged_as_costing_more() -> None:
    suggestions = _read("views/suggestions.js")
    effect = suggestions.split("function effect(s) {", 1)[1].split("\n}\n", 1)[0]

    # A new line: what it adds, and the lower price a litre the sentence states; "more" only for a line it replaces.
    assert effect.index("if (addsALine(s) && !isTrend(s))") < effect.index("more, before tax")
    assert "Adds ${money(n)} to this order, before tax" in effect and "${cheaperTag(s.effect)}" in effect
    assert "${money(after)} ${MEASURE[e.measure]} instead of ${money(before)}" in suggestions
    assert "Number(e?.saving_ratio) > 0" in suggestions  # no saving, no such tag


# --- 7. who says the recipe matters: the request, or what was learned ----------------------------------------


def _texts(offer: dict[str, Any]) -> list[str]:
    return [*offer["notes"], *(option["summary"] for option in offer["options"])]


def test_a_line_the_gateway_learned_never_reads_as_if_the_request_said_it(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings, formula_mode="LEARN", formula_matters=False)

    offer = _offer(client, "hotel", CREAM_100)

    assert offer["request"]["lines"][0]["keep_formula"] is None  # the request did not say it
    assert any("The gateway applied this; your request did not say it." in note for note in offer["notes"])
    assert not [text for text in _texts(offer) if REQUEST_SAYS in text.lower()]
    assert any(note.startswith(f"Request line 1: {LEARNED_SAYS}") for note in offer["notes"])
    assert any(LEARNED_SAYS in option["summary"].lower() for option in offer["options"])


def test_a_request_that_says_the_recipe_matters_is_still_said_to_say_it(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings, formula_mode="LEARN", formula_matters=False)
    said = {**CREAM_100, "lines": [{**CREAM_100["lines"][0], "keep_formula": True}]}

    offer = _offer(client, "hotel", said)

    assert any(REQUEST_SAYS in text.lower() for text in _texts(offer))
    assert not [text for text in _texts(offer) if LEARNED_SAYS in text.lower()]


# --- 8. the later recording is said once ----------------------------------------------------------------------


def test_the_later_recordings_fold_never_repeats_its_own_line() -> None:
    plan = _read("views/plan.js")
    found = re.search(r"export function laterParts\(note\) \{.*?\n\}\n", plan, re.DOTALL)
    assert found is not None and "const [first, rest] = laterParts(note);" in plan
    note = ("7 of the 9 products of this offer have their price and stock from the later recording (460856, 475703 "
            "and 476689). 394 of the products were recorded on Saturday.")

    first, rest = _node(
        found.group(0).replace("export ", "") + f"console.log(JSON.stringify(laterParts({json.dumps(note)})));"
    )

    assert first == "7 of the 9 products of this offer have their price and stock from the later recording"
    assert rest == "They are 460856, 475703 and 476689. 394 of the products were recorded on Saturday."
    assert first not in rest  # the line of the fold is not said again under it


def test_the_later_recording_is_worded_in_one_place() -> None:
    import tta.menus.sentence as menus
    import tta.offers.recorded as offers

    assert not hasattr(menus, "LATER_RECORDED") and hasattr(offers, "LATER_RECORDED")
    assert menus.offer_later_recorded_note is offers.later_recorded_note
