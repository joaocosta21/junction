"""The final pass of the shop page (lane FP-UI): what a person reads on `/shop` in the seven demo scenarios.

Scores on the 30% "working end-to-end demo" (the total and "Confirm order" of a recipe plan come before its rows; a
refused request says how many products were checked and why), on the 15% "robustness to exception situations" (a
substitute's difference is said once, the figures one fold away; a later date is labelled as a later date) and on the
20% "autonomy and controls" (a change of settings is read back from the audit trail on the Settings page).

The page's own modules are run with node on hand-written offers: every sentence of these fixtures is made up and
only checked for being shown, so no sentence of the gateway is pinned. The route is tested through the gateway.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui

SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
HEADERS = {"X-Shop-Request": "1", "X-Shop-Kitchen": "hotel-kitchen"}
CHANGED = "tta.v1.settings.changed"

PRELUDE = """
const JS = %(js)s;
const CUSTOMER = { note: "", customer: { customer_number: "610 245", address: "Test street 1", delivery_days: "Mon-Sat",
  contact: { name: "Hanna Laine", title: "Purchasing manager" }, usual: [], history: [],
  people: { purchasing_manager: "Hanna Laine", finance: "Hanna Laine", dietitian: "Hanna Laine" } } };
const ANSWERS = %(answers)s;
globalThis.fetch = async (url) => {
  const path = String(url).replace(/^.*\\/shop\\/api/, "");
  if (path === "/customer") return { ok: true, status: 200, json: async () => CUSTOMER };
  if (ANSWERS[path] !== undefined) return { ok: true, status: 200, json: async () => ANSWERS[path] };
  throw new Error("no network in a test");
};
const store = await import(JS + "/store.js");
const core = await import(JS + "/core.js");
const customer = await import(JS + "/customer.js");
const assistant = await import(JS + "/views/assistant.js");
const parts = await import(JS + "/views/parts.js");
store.memory.active = "hotel";
await customer.loadCustomer();
core.app.data.ready = true;
core.app.data.authority = { profile: { display_name: "Harbourside Hotel", auto_order_enabled: false,
  max_order_net_eur: 750, max_daily_net_eur: 3000, excluded_allergens: [], formula_mode: "WHEN_ASKED" } };
const line = (extra = {}) => ({ product_id: "100001", name: "Test milk 1 L", vendor_name: "TEST OY", sales_unit: "ST",
  quantity: 2, unit_net_price: 2.57, net: 5.14, request_line_index: 0, claims: [],
  availability: { state: "CONFIRMED", usable_amount: 50, sales_unit: "ST", available_date: "2026-11-16" }, ...extra });
const GIVES_UP = "MADE-UP-LEAD: another kind of product. It costs more.";
const substitute = (extra = {}) => ({ original_id: "100001", original_name: "Test milk 1 L", last_resort: true,
  claims_lost: [], gives_up: GIVES_UP,
  formula: { outcome: "DIFFERENT", sentence: "MADE-UP-FORMULA sentence.", contents_compared: true, basis: "G",
    only_in_other: [], only_in_original: ["MADE-UP-COMPONENT"],
    differences: [{ nutrient: "fat", original: 1.5, other: 3, within_tolerance: false }] }, ...extra });
const decision = () => ({ verdict: "APPROVAL", required_roles: ["purchasing_manager"],
  sentence: "The agent cannot place this order alone: MADE-UP-REASON. It needs a person.",
  fired: [{ rule_id: "P-01", approver_role: "purchasing_manager", verdict: "APPROVAL", sentence: "MADE-UP-REASON" }] });
const option = (id, kind, extra = {}) => ({ option_id: id, kind, rank: 1, title: "TITLE-" + id,
  summary: "SUMMARY-" + id, lines: [line()], totals: { net: 1083.39, gross: 1229.64 }, decision: decision(),
  constraint_checks: [], ...extra });
const request = (lines) => ({ needed_by: "2026-11-16", lines });
const MILK = { text: "milk", product_type: "milk", quantity: 100, unit: "L" };
const turn = (id, options, extra = {}) => ({ id, text: "TYPED-" + id, at: "2026-11-12T12:15:00.000Z", phase: "done",
  reading: { source: "rule-based" }, sent: request([MILK]), regular: null,
  offer: { offer_id: "off_" + id, source: "replay", request: request([MILK]), options, suggestions: [],
    excluded: [], notes: [], candidates_considered: 3 }, ...extra });
const thread = () => store.mine().thread;
const page = () => String(assistant.view());
const card = (html, id) => { const from = html.indexOf('id="result-' + id + '"');
  const next = html.indexOf('<article', from + 1); return from < 0 ? "" : html.slice(from, next < 0 ? undefined :
    next); };
const say = (value) => console.log(JSON.stringify(value));
"""


def _node(script: str, answers: dict[str, Any] | None = None) -> Any:
    """What a script prints as JSON, run by node on the page's own modules; skipped where node is not installed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    source = PRELUDE % {"js": json.dumps(str(SHOP_JS)), "answers": json.dumps(answers or {})} + script
    # The script is this file's own text around the page's modules: nothing from outside is run.
    done = subprocess.run(  # noqa: S603
        [node, "--input-type=module", "-e", source], capture_output=True, text=True, timeout=120, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- 1. the hero answer: a substitute's difference once, the rest one fold away ------------------------------------


def test_a_last_resort_that_loses_no_claim_does_not_speak_of_a_dietary_claim() -> None:
    found = _node("""
    const note = (s) => String(parts.substituteNote(line({ substitute: substitute(s) })));
    say({ none: note({}), one: note({ claims_lost: ["FREE_FROM_LACTOSE"] }) });
    """)

    said = "Not a like-for-like replacement, and nothing like for like can be ordered. A person decides."
    assert said in found["none"]
    assert "dietary claim" not in found["none"] and "Last resort:" not in found["none"]
    assert "Last resort: it does not carry “lactose free”, a claim of the product asked for" in found["one"]


def test_a_substitute_row_says_the_difference_once_and_folds_the_figures() -> None:
    found = _node("""
    const row = String(parts.productLine(line({ substitute: substitute() })));
    const fold = row.slice(row.indexOf("<details"), row.indexOf("</details>"));
    say({ sentence: row.split("MADE-UP-LEAD").length - 1, formula: row.split("MADE-UP-FORMULA").length - 1,
      beforeFold: row.indexOf("MADE-UP-LEAD") < row.indexOf("<details"), table: fold.includes("<table"),
      lacks: fold.includes("MADE-UP-COMPONENT"), outside: row.replace(fold, "").includes("<table") });
    """)

    assert found == {"sentence": 1, "formula": 1, "beforeFold": True, "table": True, "lacks": True, "outside": False}


def test_an_options_summary_is_cut_where_it_starts_to_say_what_the_substitute_differs_in() -> None:
    found = _node("""
    const lines = [line(), line({ product_id: "100002", substitute: substitute() })];
    say({ cut: parts.summaryParts({ summary: "FIRST-PART for a price. MADE-UP-LEAD: and so on. MORE.", lines }),
      whole: parts.summaryParts({ summary: "FIRST-PART for a price. Something else. MORE.", lines }),
      plain: parts.summaryParts({ summary: "FIRST-PART. MADE-UP-LEAD: x.", lines: [line()] }) });
    """)

    assert found["cut"] == ["FIRST-PART for a price.", "MADE-UP-LEAD: and so on. MORE."]
    assert found["whole"] == ["FIRST-PART for a price. Something else. MORE.", ""]
    assert found["plain"] == ["FIRST-PART. MADE-UP-LEAD: x.", ""]  # no substitute in the option: nothing is folded


def test_the_third_option_shows_its_first_sentence_and_folds_what_differs_chosen_or_not() -> None:
    found = _node("""
    const third = option("three", "SUBSTITUTE", { rank: 3, summary: "FIRST-PART for a price. MADE-UP-LEAD: REST-PART.",
      lines: [line(), line({ product_id: "100002", name: "Test coffee milk", substitute: substitute() })] });
    thread().push(turn("t1", [option("one", "BEST_CONFIRMED"), third]));
    const listed = card(page(), "t1");
    const other = listed.slice(listed.indexOf('class="others"'));
    thread()[0].chosen = "three";
    const chosen = card(page(), "t1");
    const headline = (chosen.match(/class="headline">([^<]*)</) || [])[1];
    const fold = chosen.slice(chosen.indexOf('class="why fold differs"'));
    say({ otherFirst: other.includes("FIRST-PART for a price.</div>"), otherFold: other.includes("What differs"),
      otherRest: other.slice(other.indexOf("What differs")).includes("MADE-UP-LEAD: REST-PART."),
      otherSaysItOnce: other.split("MADE-UP-LEAD").length - 1, otherResort: other.includes("A person decides."),
      headline, foldAfterHeadline: chosen.indexOf('class="headline"') < chosen.indexOf("What differs"),
      foldBeforeTotal: chosen.indexOf("What differs") < chosen.indexOf('class="totals'),
      rest: fold.slice(0, fold.indexOf("</details>")).includes("MADE-UP-LEAD: REST-PART.") });
    """)

    assert found == {
        "otherFirst": True, "otherFold": True, "otherRest": True, "otherSaysItOnce": 1, "otherResort": True,
        "headline": "FIRST-PART for a price.", "foldAfterHeadline": True, "foldBeforeTotal": True, "rest": True,
    }


# --- 2. an option for a later day than asked is labelled as that -----------------------------------------------------


def test_a_first_option_delivered_later_than_asked_is_labelled_later_than_asked() -> None:
    found = _node("""
    const label = (title) => { const t = turn("t" + title.length,
        [option("one", "ALTERNATIVE_UNCONFIRMED", { title })]);
      thread().push(t); return (card(page(), t.id).match(/class="label-row"><span class="label">([^<]*)</) || [])[1]; };
    say([label("Alternative: delivered MADE-UP-DAY, 3 days later than asked (partial fill)"),
      label("Alternative: quantity not confirmed")]);
    """)

    assert found == ["Later than asked", "No confirmed option"]


# --- 3. a recipe plan: the total and the button first, the rows below ------------------------------------------------


def test_a_plans_total_and_button_come_before_its_ingredient_rows() -> None:
    found = _node("""
    const plan = { offer_id: "off_t1", request: request([MILK]), cannot_be_sourced: [],
      notes: ["Read as: MADE-UP-DISH, 20 servings.",
        "Option 1, TITLE-one: €1.00 before tax, €1.14 with tax. MADE-UP-COOKS-REASON. It needs the " +
          "purchasing manager."],
      lines: [{ request_line_index: 0, product_type: "milk", to_order: 0.3, unit: "L", dishes: ["d"] }],
      dishes: [{ name: "MADE-UP-DISH", left_out: [], ingredients: [{ recipe_product_type: "milk", product_type: "milk",
        role: "MADE-UP-ROLE", needed: 0.3, in_stock: 0, to_order: 0.3, unit: "L", status: "TO_ORDER",
        request_line_index: 0 }] }] };
    thread().push(turn("t1", [option("one", "BEST_CONFIRMED")], { plan, reading: { source: "plan" } }));
    const html = card(page(), "t1");
    const box = html.slice(html.indexOf('class="verdict'), html.indexOf('class="plan"'));
    say({ total: html.indexOf('class="totals'), button: html.indexOf('data-act="confirm"'),
      rows: html.indexOf('class="plan-rows"'), lines: html.indexOf('class="lines"'),
      reason: box.includes("MADE-UP-COOKS-REASON."), role: box.includes("It needs"),
      below: html.includes("asked below"), above: html.includes("The decision is asked above, with the total."),
      litres: html.includes("0.3 L") && !html.includes("0.3 l") });
    """)

    assert 0 < found["total"] < found["button"] < found["rows"] < found["lines"]
    assert found["reason"] and not found["role"]  # the cook's reason, and no role as a label
    assert found["above"] and not found["below"]
    assert found["litres"]


# --- 5. small things ------------------------------------------------------------------------------------------------


def test_a_model_is_named_as_the_gateway_reports_it_never_by_a_name_the_page_holds() -> None:
    found = _node("""
    const meta = (reading) => { const t = turn("t" + Math.random().toString(36).slice(2),
      [option("one", "BEST_CONFIRMED")], { reading }); thread().push(t);
      return (card(page(), t.id).match(/class="small muted">([^<]*)</) || [])[1]; };
    say([meta({ source: "model", model: "MADE-UP-MODEL-1" }), meta({ source: "model" }),
      meta({ source: "recording", model: "MADE-UP-MODEL-2" }), meta({ source: "rule-based", model: "rule-based" })]);
    """)

    assert "read by the model MADE-UP-MODEL-1" in found[0]
    assert "read by a model" in found[1]
    assert "read from a recorded answer of the model MADE-UP-MODEL-2" in found[2]
    assert "read by fixed rules, no model" in found[3] and "MADE-UP" not in found[3]
    sources = (SHOP_JS / "views" / "assistant.js").read_text(encoding="utf-8").split("const CONFIRM_NOTE")[0]
    assert "Gemini" not in sources


def test_a_standing_orders_renewal_is_asked_under_its_name_with_the_products_name() -> None:
    found = _node("""
    const renewal = { needed_by: null, standing_order_id: "so_1",
      lines: [{ text: "290 litres of product 100009, every week", product_ids: ["100009"], quantity: 290,
        unit: "L" }] };
    const t = { id: "t1", text: "MADE-UP-STANDING-ORDER", at: "2026-11-12T12:15:00.000Z", phase: "looking",
      reading: { source: "standing" }, sent: renewal, names: { 100009: "MADE-UP-PRODUCT 1 L" } };
    thread().push(t);
    say((card(page(), "t1").match(/class="read">\\s*<b>([^<]*)</) || [])[1]);
    """)

    assert found == "MADE-UP-STANDING-ORDER, renewed once: 290 L MADE-UP-PRODUCT 1 L (100009)"


def test_a_request_nothing_can_be_offered_for_says_how_many_were_checked_and_why() -> None:
    found = _node("""
    const out = (id, sentence) => ({ product_id: id, name: "Product " + id, request_line_index: 0,
      reason: "ALLERGEN_DECLARED", sentence });
    const t = turn("t1", []);
    t.offer.excluded = [out("1", "MADE-UP-WHY."), out("2", "MADE-UP-WHY."), out("3", "MADE-UP-WHY.")];
    t.offer.notes = ["MADE-UP-NOTE of the gateway."];
    thread().push(t);
    const html = card(page(), "t1");
    const box = html.slice(html.indexOf('class="verdict stop"'), html.indexOf("<details"));
    say({ counted: box.includes("3 products checked, 3 left out. All 3: MADE-UP-WHY."),
      noteInBox: box.includes("MADE-UP-NOTE"),
      noteFolded: html.slice(html.indexOf("<details")).includes("MADE-UP-NOTE of the gateway."),
      named: html.includes("Product 2 (2)") });
    """)

    assert found == {"counted": True, "noteInBox": False, "noteFolded": True, "named": True}


# --- 4. settings: the refusal without its prefixes, and what changed, from the audit trail --------------------------


def test_a_refused_allergen_change_is_shown_without_the_forms_and_the_fields_name() -> None:
    found = _node("""
    const words = await import(JS + "/words.js");
    say([words.refusalWords("Your kitchen: excluded_allergens: MADE-UP-SENTENCE one; allergen_strictness: MADE-UP two"),
      words.refusalWords("Your kitchen: max_order_net_eur: MADE-UP three"), words.refusalWords("MADE-UP four")]);
    """)

    assert found == ["MADE-UP-SENTENCE one; MADE-UP two", "max_order_net_eur: MADE-UP three", "MADE-UP four"]


def test_the_settings_page_shows_what_changed_newest_first_from_the_log() -> None:
    events = [{"type": CHANGED, "time": f"2026-11-15T0{hour}:00:00Z", "sentence": f"MADE-UP-CHANGE-{hour}."}
              for hour in range(1, 8)]
    found = _node("""
    let drawn = 0;
    core.setRenderer(() => { drawn += 1; });
    const settings = await import(JS + "/views/settings.js");
    store.mine().settings = store.active().settings;
    const before = String(settings.view());
    settings.enter();
    await new Promise((done) => setTimeout(done, 50));
    const after = String(settings.view());
    const log = after.slice(after.indexOf('id="s-changes"'), after.indexOf('id="s-answers"'));
    say({ reading: before.includes("Reading the log"), title: log.includes("What changed"),
      order: [7, 6, 5, 4, 3].map((n) => log.indexOf("MADE-UP-CHANGE-" + n + ".")),
      older: log.includes("MADE-UP-CHANGE-2."), count: log.includes("The 5 newest of 7 changes."), drawn: drawn > 0,
      toc: after.includes('data-to="s-changes"') });
    """, {"/audit?event_type=settings.changed": {"events": events}})

    assert found["reading"] and found["title"] and found["toc"] and found["drawn"]
    assert all(at > 0 for at in found["order"]) and found["order"] == sorted(found["order"])  # newest first
    assert not found["older"] and found["count"]


def test_the_shops_audit_route_reads_the_book_without_an_order_and_keeps_one_kind_of_event(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    settings = dict(shop_profile_settings["hotel-kitchen"])
    assert client.put("/shop/api/kitchen", headers=HEADERS, json=settings).status_code == 200
    nothing_yet = client.get("/shop/api/audit", headers=HEADERS, params={"event_type": "settings.changed"})
    switched = client.put("/shop/api/kitchen", headers=HEADERS, json={**settings, "auto_order_enabled": True})
    assert switched.status_code == 200, switched.text

    changes = client.get("/shop/api/audit", headers=HEADERS, params={"event_type": "settings.changed"})
    whole = client.get("/shop/api/audit", headers=HEADERS)
    valio = client.get("/shop/api/audit", headers=HEADERS, params={"event_type": "settings.changed",
                                                                    "reader": "supplier"})

    assert nothing_yet.status_code == 200 and nothing_yet.json()["events"] == []  # the file's values change nothing
    assert changes.status_code == 200, changes.text
    events = changes.json()["events"]
    assert [event["type"] for event in events] == [CHANGED]
    assert events[0]["sentence"] and changes.json()["chain"]["ok"] is True
    assert CHANGED in [event["type"] for event in whole.json()["events"]]
    assert whole.status_code == 200 and len(whole.json()["events"]) >= len(events)
    # Valio Aimo's view of the same event carries none of the buyer's limit amounts.
    assert valio.status_code == 200 and "750" not in json.dumps(valio.json()["events"])


def test_the_shops_audit_route_still_refuses_an_unknown_kind_of_event_and_another_books_order(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    saved = client.put("/shop/api/kitchen", headers=HEADERS, json=shop_profile_settings["hotel-kitchen"])
    assert saved.status_code == 200

    assert client.get("/shop/api/audit", headers=HEADERS, params={"event_type": "no.such"}).status_code == 422
    assert client.get("/shop/api/audit", headers=HEADERS, params={"order_id": "ord_nobody"}).status_code == 404
    assert client.get("/shop/api/audit", params={"event_type": "settings.changed"}).status_code == 403
