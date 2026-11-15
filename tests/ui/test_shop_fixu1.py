"""The request and its answer on the shop page (lane FIX-U1): what a person sees between a sentence and an order.

Scores on the 30% "working end-to-end demo" (after a request the answer, its total and "Confirm order" are what the
window shows; a fold a person opened stays open; one result can be ordered, never the one it replaced), on the 20%
"solving the problem and user need" (labels and figures that say what is true, in one money format) and on the 20%
"autonomy and controls" (the page says who the visitor acts as, and what the agent may order alone).

The page's own modules are run with node: the request view is drawn from a hand-written offer, so no sentence of
the gateway is pinned here (every sentence of these fixtures is made up and only checked for being shown). The
moves that need a window (the scroll to the answer, a toast that leaves the page alone) are proven in a browser by
the lane's pictures; here the functions behind them are run against a stand-in for the page.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

import tta.ui

SHOP = Path(tta.ui.__file__).parent / "static" / "shop"
SHOP_JS = SHOP / "js"

# What every script starts with: no network, the hotel's customer file as the route would answer it, one profile.
PRELUDE = """
const JS = %(js)s;
const CUSTOMER = { note: "", customer: { customer_number: "610 245", address: "Test street 1", delivery_days: "Mon-Sat",
  contact: { name: "Hanna Laine", title: "Purchasing manager" }, usual: [], history: [],
  people: { purchasing_manager: "Hanna Laine", finance: "Hanna Laine", dietitian: "Hanna Laine" } } };
globalThis.fetch = async (url) => {
  if (String(url).endsWith("/shop/api/customer")) return { ok: true, status: 200, json: async () => CUSTOMER };
  throw new Error("no network in a test");
};
const store = await import(JS + "/store.js");
const core = await import(JS + "/core.js");
const customer = await import(JS + "/customer.js");
const assistant = await import(JS + "/views/assistant.js");
store.memory.active = "hotel";
await customer.loadCustomer();
core.app.data.ready = true;
core.app.data.authority = { profile: { display_name: "Harbourside Hotel", auto_order_enabled: false,
  max_order_net_eur: 750,
  max_daily_net_eur: 3000, excluded_allergens: [], formula_mode: "WHEN_ASKED" } };
const line = (extra = {}) => ({ product_id: "100001", name: "Test milk 1 L", vendor_name: "TEST OY", sales_unit: "PS",
  quantity: 2, unit_net_price: 2.57, net: 5.14, request_line_index: 0, claims: [],
  availability: { state: "CONFIRMED", usable_amount: 50, sales_unit: "PS", available_date: "2026-11-16" }, ...extra });
const decision = () => ({ verdict: "APPROVAL", required_roles: ["purchasing_manager"],
  sentence: "The agent cannot place this order alone: MADE-UP-REASON. It needs a person.",
  fired: [{ rule_id: "P-01", approver_role: "purchasing_manager", verdict: "APPROVAL", sentence: "MADE-UP-REASON" }] });
const option = (id, kind, extra = {}) => ({ option_id: id, kind, rank: 1, title: "TITLE-" + id,
  summary: "SUMMARY-" + id,
  lines: [line()], totals: { net: 1083.39, gross: 1229.64 }, decision: decision(), constraint_checks: [], ...extra });
const request = (lines) => ({ needed_by: "2026-11-16", lines });
const MILK = { text: "milk", product_type: "milk", quantity: 100, unit: "L" };
const turn = (id, options, extra = {}) => ({ id, text: "TYPED-" + id, at: "2026-11-12T12:15:00.000Z", phase: "done",
  reading: { source: "rule-based" }, sent: request([MILK]), regular: null,
  offer: { offer_id: "off_" + id, source: "replay", request: request([MILK]), options, suggestions: [],
    excluded: [], notes: [],
    candidates_considered: 3 }, ...extra });
const thread = () => store.mine().thread;  // save() makes a new list: read it each time
const page = () => String(assistant.view());
const card = (html, id) => { const from = html.indexOf('id="result-' + id + '"');
  const next = html.indexOf('<article', from + 1); return from < 0 ? "" : html.slice(from, next < 0 ? undefined :
    next); };
const say = (value) => console.log(JSON.stringify(value));
"""


def _node(script: str) -> Any:
    """What a script prints as JSON, run by node on the page's own modules; skipped where node is not installed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    source = PRELUDE % {"js": json.dumps(str(SHOP_JS))} + script
    # The script is this file's own text around the page's modules: nothing from outside is run.
    done = subprocess.run(  # noqa: S603
        [node, "--input-type=module", "-e", source], capture_output=True, text=True, timeout=120, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def _read(name: str) -> str:
    return (SHOP / name).read_text(encoding="utf-8")


# --- 1. the request box first, the answer where the window is, the total and the button before the lines ----------


def test_the_request_box_is_first_and_the_reorder_prompt_is_a_compact_block_below_it() -> None:
    found = _node("""
    core.app.data.reorder = { sentence: "MADE-UP-ACCOUNT of what was ordered week after week.", note: "MADE-UP-NOTE",
      why_not: ["MADE-UP-WHY-NOT"], request: request([MILK]),
      lines: [{ product_id: "100002", name: "Test cream 1 L", quantity: 10, unit: "L", orders_matching: 4,
        orders_considered: 4 }] };
    const html = page();
    const prompt = html.slice(html.indexOf('class="reorder'), html.indexOf('class="results'));
    say({ box: html.indexOf('class="ask"'),
      prompt: html.indexOf('class="reorder'), results: html.indexOf('class="results'),
      goes: prompt.includes('data-act="reorder-go"'), hides: prompt.includes('data-act="reorder-hide"'),
      names: prompt.indexOf("Test cream 1 L"), fold: prompt.indexOf("<details"),
        account: prompt.indexOf("MADE-UP-ACCOUNT"),
      whyNot: prompt.indexOf("MADE-UP-WHY-NOT") });
    """)

    assert 0 < found["box"] < found["prompt"] < found["results"]  # the box, then the prompt, then the results
    assert found["goes"] and found["hides"]  # João's prompt keeps its two buttons
    # What it is and its buttons are said at once; the gateway's whole account is folded under them.
    assert 0 < found["names"] < found["fold"] < found["account"] < found["whyNot"]


def test_the_total_and_the_button_come_before_the_product_lines() -> None:
    found = _node("""
    thread().push(turn("t1", [option("one", "BEST_CONFIRMED")]));
    const html = card(page(), "t1");
    say({ headline: html.indexOf("SUMMARY-one"),
      total: html.indexOf('class="totals'), button: html.indexOf('data-act="confirm"'),
      lines: html.indexOf('class="pline"'), totals: html.split('class="totals').length - 1 });
    """)

    assert 0 < found["headline"] < found["total"] < found["button"] < found["lines"]
    assert found["totals"] == 1  # the total is said once


def test_a_request_that_is_sent_asks_the_page_to_bring_its_result_to_the_top() -> None:
    found = _node("""
    const sent = core.handlers.example({ dataset: { i: "0" } });  // an example chip: a request like any other
    const id = thread().at(-1).id;
    say({ reveal: core.app.ui.reveal === id, anchor: page().includes('id="result-' + id + '"') });
    await sent;
    """)
    frame, core = _read("js/main.js"), _read("js/core.js")

    assert found == {"reveal": True, "anchor": True}
    # The frame scrolls to it after the redraw, under the header that stays on screen, and takes no smooth way there
    # (a redraw on the way would stop it half-way).
    assert "revealPending();" in frame and "header?.offsetHeight" in frame
    assert "behavior" not in frame and "scrollIntoView" not in frame
    assert "export function reveal(" in core


# --- 2. a fold a person opened stays open: a toast redraws nothing, a redraw keeps folds and scroll -----------------

FOLDS = """
const fold = (scope, words, open, act = "") => ({ open, querySelector: () => ({ textContent: words,
  dataset: act ? { act } : {} }),
  parentElement: { closest: () => (scope ? { id: scope } : null) } });
const root = (folds) => ({ querySelectorAll: () => folds });
"""


def test_a_redraw_keeps_each_fold_as_the_person_left_it() -> None:
    found = _node(FOLDS + """
    // Before the redraw: the person opened "Why this answer" of the first result and closed one the page draws open.
    const before = root([fold("result-t1", "Why this answer", true), fold("result-t1", "Typed request", false),
      fold("result-t2", "Why this answer", false), fold("result-t1", "Why?", false), fold("result-t1", "Why?", true),
      fold("app", "Drawn open", false), fold("app", "The clock", false, "clock-fold")]);
    const kept = core.keepFolds(before);
    // The redraw draws every fold as the page's own state says: all closed but two.
    const drawn = [fold("result-t1", "Why this answer", false), fold("result-t1", "Typed request", false),
      fold("result-t2", "Why this answer", false), fold("result-t1", "Why?", false), fold("result-t1", "Why?", false),
      fold("app", "Drawn open", true), fold("app", "The clock", true, "clock-fold"), fold("result-t3",
        "Why this answer", false)];
    core.restoreFolds(root(drawn), kept);
    say(drawn.map((one) => one.open));
    """)

    # Opened stays open, per result and per place; closed stays closed; the page's own fold and a new one are as drawn.
    assert found == [True, False, False, False, True, False, True, False]


def test_a_toast_comes_and_goes_without_a_redraw() -> None:
    found = _node("""
    const host = { shown: [], replaceChildren() { this.shown = []; }, append(one) { this.shown.push(one); } };
    globalThis.document = { getElementById: (id) => (id === "toasts" ? host : null),
      createElement: () => ({ className: "", textContent: "", setAttribute() {},
        remove() { host.shown = host.shown.filter((x) => x !== this); } }) };
    let redraws = 0;
    core.setRenderer(() => { redraws += 1; });
    core.toast("MADE-UP-TOAST", 30);
    const up = host.shown.map((one) => [one.className, one.textContent]);
    await new Promise((done) => setTimeout(done, 120));
    say({ up, after: host.shown.length, redraws });
    """)
    frame, shell = _read("js/main.js"), _read("index.html")

    assert found == {"up": [["toast", "MADE-UP-TOAST"]], "after": 0, "redraws": 0}
    # It lives beside the page, never inside what a redraw replaces; a redraw puts folds and scroll back.
    assert 'id="toasts"' in shell and shell.index('id="app"') < shell.index('id="toasts"')
    assert "app.ui.toast" not in frame
    assert "keepFolds(root)" in frame and "restoreFolds(root, folds)" in frame and "window.scrollTo(0, y)" in frame
    assert "preventScroll: true" in frame  # the field a person types in is focused again without moving the page


# --- 3. one result can be ordered: the one a suggestion replaced loses its button and says so ----------------------

SUGGESTED = """
const suggestion = { suggestion_id: "sug_1", kind: "FORGOTTEN_ITEM", name: "Test cream 1 L", product_id: "100002",
  sentence: "MADE-UP-SUGGESTION", quantity: 10, unit: "L", request_line_index: null, effect: { net_change_eur: 33.1 },
  accept_request: request([MILK, { text: "cream", product_ids: ["100002"], quantity: 10, unit: "L" }]) };
const old = turn("t1", [option("one", "BEST_CONFIRMED"), option("two", "ALTERNATIVE_UNCONFIRMED")]);
old.offer.suggestions = [suggestion];
thread().push(old);
const buttons = (html, id) => ({ confirm: card(html, id).split('data-act="confirm"').length - 1,
  choose: card(html, id).includes('data-act="choose"'), add: card(html, id).includes('data-act="suggest-add"'),
  replaced: card(html, id).includes('class="replaced"') });
"""


def test_add_replaces_the_result_it_was_clicked_on() -> None:
    found = _node(SUGGESTED + """
    const before = buttons(page(), "t1");
    const sent = core.handlers["suggest-add"]({ dataset: { turn: "t1", id: "sug_1" } });
    const added = thread().at(-1);
    const sending = { replaces: added.replaces, reveal: core.app.ui.reveal === added.id, old: buttons(page(), "t1") };
    await sent;  // no network here: the new request fails, so it replaces nothing and the first can be ordered again
    const failed = { phase: added.phase, old: buttons(page(), "t1") };
    Object.assign(added, { phase: "done", problem: null, offer: turn("x", [option("nine", "BEST_CONFIRMED")]).offer });
    const html = page();
    say({ before, sending, failed, answered: { old: buttons(html, "t1"), fresh: buttons(html, added.id),
      order: html.indexOf('id="result-' + added.id + '"') < html.indexOf('id="result-t1"') } });
    """)

    live = {"confirm": 1, "choose": True, "add": True, "replaced": False}
    gone = {"confirm": 0, "choose": False, "add": False, "replaced": True}
    assert found["before"] == live
    # At once, and the page goes to the new one.
    assert found["sending"] == {"replaces": "t1", "reveal": True, "old": gone}
    # It failed: the first result can be ordered again; its suggestion says it was sent ("Try again" is on the new one).
    assert found["failed"] == {"phase": "failed", "old": {**live, "add": False}}
    assert found["answered"]["old"] == gone and found["answered"]["order"] is True
    assert found["answered"]["fresh"]["confirm"] == 1 and found["answered"]["fresh"]["replaced"] is False


def test_a_replaced_result_cannot_be_ordered_by_a_click_that_was_already_on_its_way() -> None:
    found = _node(SUGGESTED + """
    thread().push(turn("t2", [option("nine", "BEST_CONFIRMED")], { replaces: "t1" }));
    await core.handlers.confirm({ dataset: { turn: "t1", option: "one" } });
    core.handlers.choose({ dataset: { turn: "t1", option: "two" } });
    say({ order: old.order ?? null, busy: old.busy ?? null, chosen: old.chosen ?? null });
    """)

    assert found == {"order": None, "busy": None, "chosen": None}


def test_a_result_that_is_ordered_offers_no_button_that_would_ask_for_it_all_again() -> None:
    found = _node(SUGGESTED + """
    old.order = { order_id: "ord_1", status: "ORDERED", placed_by: "HUMAN_APPROVAL", option: old.offer.options[0],
      decision: decision(), status_sentence: "MADE-UP-OUTCOME" };
    const html = card(page(), "t1");
    say({ sentence: html.includes("MADE-UP-SUGGESTION"), add: html.includes('data-act="suggest-add"'),
      replaced: html.includes('class="replaced"') });
    """)

    # A suggestion's request is the whole request again with the suggestion taken: after the order it has no button.
    assert found == {"sentence": True, "add": False, "replaced": False}


def test_the_usual_quantity_sent_from_a_results_bar_replaces_that_result() -> None:
    found = _node("""
    const usual = request([{ ...MILK, quantity: 10 }]);
    const old = turn("t1", [option("one", "BEST_CONFIRMED")], { regular: { finding: "REGULAR_DIFFERENT_QUANTITY",
      sentence: "MADE-UP-BAR", lines: [], standingOrderRequest: null, usualRequest: usual } });
    thread().push(old);
    const sent = assistant.sendAsWritten("reorder", "TYPED-t1", usual);  // what the bar's own button does (regular.js)
    const prompt = assistant.sendAsWritten("reorder", "Order the same again", request([MILK]));
       // the reorder prompt's request
    say({ fromTheBar: thread().at(-2).replaces ?? null, fromThePrompt: thread().at(-1).replaces ?? null });
    await Promise.all([sent, prompt]);
    """)

    assert found == {"fromTheBar": "t1", "fromThePrompt": None}


# --- 4. the label above an option says what is true ----------------------------------------------------------------


def test_the_label_says_suggested_only_of_the_gateways_own_suggestion() -> None:
    found = _node("""
    const label = (html, id) => (card(html, id).match(/class="label-row"><span class="label">([^<]*)</) || [])[1];
    thread().push(turn("t1", [option("one", "BEST_CONFIRMED"), option("two", "ALTERNATIVE_UNCONFIRMED")]));
    thread().push(turn("t2", [option("one", "BEST_CONFIRMED"), option("two", "ALTERNATIVE_UNCONFIRMED")],
      { chosen: "two" }));
    thread().push(turn("t3", [option("one", "ALTERNATIVE_UNCONFIRMED"), option("two", "ALTERNATIVE_UNCONFIRMED")]));
    thread().push(turn("t4", [option("one", "SUBSTITUTE")]));
    const html = page();
    const rest = card(html, "t2").slice(card(html, "t2").indexOf('class="others"'));
    say({ first: label(html, "t1"), chosen: label(html, "t2"), none: label(html, "t3"), substitute: label(html, "t4"),
      restHeading: (rest.match(/<h4>([^<]*)</) || [])[1], restMarksTheSuggestion: rest.includes("TITLE-one") &&
        rest.includes(">Suggested<") });
    """)

    assert found["first"] == "Suggested" and found["substitute"] == "Suggested"
    assert found["chosen"] == "Your choice"
    assert "uggested" not in found["none"]  # no option is confirmed: nothing is called suggested
    # The option a person turned down is listed with its own name, under a heading that fits it.
    assert found["restHeading"] == "Other options" and found["restMarksTheSuggestion"] is True


# --- 5. a regular order is said once, as one line under the headline -------------------------------------------------


def test_a_regular_order_is_said_once_under_the_headline() -> None:
    found = _node("""
    const usual = { suggestion_id: "sug_u", kind: "USUAL_QUANTITY", name: "Test milk 1 L", product_id: "100001",
      sentence: "MADE-UP-USUAL-QUANTITY", quantity: 10, unit: "L", request_line_index: 0,
        accept_request: request([MILK]) };
    const other = { ...usual, suggestion_id: "sug_o", kind: "FORGOTTEN_ITEM", product_id: "100002",
      sentence: "MADE-UP-FORGOTTEN" };
    const bar = (finding) => ({ finding, sentence: "MADE-UP-BAR", standingOrderRequest: null,
      usualRequest: request([MILK]),
      lines: [{ product_id: "100001", comparison: "MORE", quantity: 30, usual_quantity: 10, unit: "L" }] });
    const asked = turn("t1", [option("one", "BEST_CONFIRMED")], { regular: bar("REGULAR_DIFFERENT_QUANTITY") });
    asked.offer.suggestions = [usual, other];
    const standing = turn("t2", [option("one", "BEST_CONFIRMED")], { regular: bar("ALREADY_ON_STANDING_ORDER") });
    standing.offer.suggestions = [usual];
    thread().push(asked, standing);
    const html = page();
    const one = card(html, "t1");
    say({ headline: one.indexOf("SUMMARY-one"), bar: one.indexOf("MADE-UP-BAR"),
      button: one.indexOf('data-act="confirm"'),
      bars: one.split("MADE-UP-BAR").length - 1, sameAgain: one.includes("MADE-UP-USUAL-QUANTITY"),
        other: one.includes("MADE-UP-FORGOTTEN"),
      anotherFinding: card(html, "t2").includes("MADE-UP-USUAL-QUANTITY") });
    """)

    assert 0 < found["headline"] < found["bar"] < found["button"] and found["bars"] == 1
    assert found["sameAgain"] is False  # the bar already asks whether the quantity is right
    assert found["other"] is True and found["anotherFinding"] is True  # nothing else is hidden


# --- 6. words and numbers -------------------------------------------------------------------------------------------


def test_the_asked_line_says_each_allergen_it_is_without() -> None:
    found = _node("""
    const without = (codes) => { const t = turn("t" + codes.length, [option("one", "BEST_CONFIRMED")]);
      t.offer.request = request([{ text: "x", product_type: "plant_drink", quantity: 200, unit: "L",
        exclude_allergens: codes }]);
      thread().push(t); return (card(page(), t.id).match(/class="read">\\s*<b>([^<]*)</) || [])[1]; };
    say([without(["AM", "AW"]), without(["AN"]), without(["AN", "AP", "AS"])]);
    """)

    assert found[0] == "200 L plant drink, without milk and without cereals containing gluten, by Mon 16 Nov"
    assert found[1] == "200 L plant drink, without tree nuts, by Mon 16 Nov"
    assert found[2] == "200 L plant drink, without tree nuts, without peanuts and without sesame, by Mon 16 Nov"


def test_the_page_says_what_is_true_when_the_agent_may_order_alone() -> None:
    found = _node("""
    const sub = () => (page().match(/class="sub">([^<]*)</) || [])[1];
    const off = sub();
    core.app.data.authority.profile.auto_order_enabled = true;
    say({ off, on: sub() });
    """)

    assert found["off"].endswith("Nothing is ordered until you confirm it.")
    assert "Nothing is ordered until you confirm it" not in found["on"]
    assert "orders alone" in found["on"] and "confirm" in found["on"]


def test_the_pages_own_figures_are_written_as_the_gateway_writes_them() -> None:
    found = _node("""
    const parts = await import(JS + "/views/parts.js");
    const ordered = turn("t1", [option("one", "BEST_CONFIRMED")], { signedBy: "Hanna Laine" });
    ordered.order = { order_id: "ord_1", status: "ORDERED", placed_by: "HUMAN_APPROVAL",
      option: ordered.offer.options[0],
      decision: decision(), status_sentence: "MADE-UP-OUTCOME" };
    thread().push(ordered);
    const html = card(page(), "t1");
    const verdict = html.slice(html.indexOf('class="verdict ok"'));
    say({ money: [core.money(1083.39), core.money(2.5), core.money(0), core.money(null), core.money(1234567.891)],
      total: parts.netTotal({ net: 1083.39 }), estimate: parts.netTotal({ net: 506.4, is_ceiling: true }),
      line: (html.match(/class="pprice"><b>([^<]*)<\\/b><span>([^<]*)</) || []).slice(1),
      outcome: (verdict.match(/<p>([^<]*)</) || [])[1] });
    """)

    assert found["money"] == ["€1,083.39", "€2.50", "€0.00", "–", "€1,234,567.89"]
    assert found["total"] == "€1,083.39" and found["estimate"] == "about €506.40"
    # A pack is counted in pieces, as the stock line counts it: never "2 bag".
    assert found["line"] == ["€5.14", "2 pcs × €2.57"]
    # One format in one sentence, and a reason is called what it is.
    assert found["outcome"] == "Ordered for €1,083.39. Why it needed your confirmation: MADE-UP-REASON."
    for name in ("views/parts.js", "views/suggestions.js"):
        script = _read("js/" + name)
        assert "money" not in script.split('from "../dom.js"')[0].split("\n")[-1], name  # one function: core.js's


# --- 10 and 11. a dish: the planner's own account in the decision box, and its list of dishes beside a question ---


def test_a_dishs_decision_box_says_the_planners_own_account_of_the_option() -> None:
    found = _node("""
    const reason = (html, id) => {
      const one = card(html, id);
      return (one.slice(one.lastIndexOf('class="verdict wait"')).match(/<p>([^<]*)</) || [])[1]; };
    const plan = (notes) => ({ offer_id: "off_x", request: request([MILK]), lines: [], dishes: [], notes });
    const own = "Option 1, MADE-UP-TOTALS with tax. MADE-UP-ACCOUNT of the ingredients. It goes to a person.";
    const another = "Option 2, MADE-UP-TOTALS with tax. ANOTHER-OPTION.";
    thread().push(turn("t1", [option("one", "BEST_CONFIRMED")], { plan: plan(["MADE-UP-NOTE.", own]) }));
    thread().push(turn("t2", [option("one", "BEST_CONFIRMED")], { plan: plan([another]) }));
    thread().push(turn("t3", [option("one", "BEST_CONFIRMED")]));
    const html = page();
    say([reason(html, "t1"), reason(html, "t2"), reason(html, "t3")]);
    """)

    assert found[0] == "MADE-UP-ACCOUNT of the ingredients. It goes to a person."
    assert found[1] == "MADE-UP-REASON." and found[2] == "MADE-UP-REASON."  # no note of this option: as before


def test_the_planners_dishes_are_said_beside_the_readers_question_when_it_knew_an_ingredient() -> None:
    found = _node("""
    const answer = (status, data) => ({ ok: status < 400, status, json: async () => data });
    const refuse = (planner) => { globalThis.fetch = async (url, init = {}) => {
      const path = String(url);
      if (path.endsWith("/kitchen")) return answer(200, core.app.data.authority);
      if (path.endsWith("/read")) return answer(422, { title: "Not read", detail: "MADE-UP-QUESTION?" });
      const none = { title: "No dish", detail: "MADE-UP-DISHES-WITH-CREAM.", dishes_named: [], ...planner };
      if (path.endsWith("/menus/plan")) return answer(422, none);
      throw new Error("no network in a test"); }; };
    const asked = async (planner) => {
      refuse(planner);
      await core.handlers.ask({ elements: { text: { value: "something with cream" } } });
      const html = card(page(), thread().at(-1).id);
      await new Promise((done) => setTimeout(done, 5));
      return html.includes("If you meant a dish:") && html.includes("MADE-UP-DISHES-WITH-CREAM"); };
    say({ ingredient: await asked({ ingredients_named: ["cream"] }),
      builtAround: await asked({ built_around: "cream" }),
      unknownDish: await asked({ unknown_dishes: ["x"] }), nothingKnown: await asked({ ingredients_named: [] }) });
    """)

    assert found == {"ingredient": True, "builtAround": True, "unknownDish": True, "nothingKnown": False}


# --- 7 and 8. who a newcomer is, and who they act as ---------------------------------------------------------------


def test_a_newcomer_starts_at_the_hotel_and_a_returning_visitor_where_they_were() -> None:
    found = _node("""
    const kept = {};
    globalThis.localStorage = { getItem: (key) => kept[key] ?? null, setItem: (key,
      value) => { kept[key] = String(value); } };
    const first = core.startingCustomer("school");
    const again = core.startingCustomer("school");
    globalThis.localStorage = { getItem() { throw new Error("no storage"); },
      setItem() { throw new Error("no storage"); } };
    say({ first, again, noStorage: core.startingCustomer("school"), example: store.active().examples[0].text });
    """)
    frame = _read("js/main.js")

    assert found == {"first": "hotel", "again": "school", "noStorage": "hotel",
                     "example": "1,000 litres of lactose-free milk by Monday"}  # the brief's own sentence
    assert "startingCustomer(memory.active)" in frame


def test_the_page_says_who_the_visitor_acts_as_and_that_nobody_logged_in() -> None:
    found = _node("""
    say((page().match(/class="sub">([^<]*)</) || [])[1]);
    """)
    frame = _read("js/main.js")

    assert found.startswith("Demo, no login: you are acting as Hanna Laine, purchasing manager.")
    assert "Signed in" not in found
    # One quiet line where the customer is chosen (decision B62): the menu's foot.
    assert "Demo, no login: you are acting as ${me.name}, ${k.name}." in frame
