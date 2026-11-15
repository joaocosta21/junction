"""A request stays its customer's, and the next request is one keystroke away (lane FP-Z, items 1 and 6).

Scores on the 20% "autonomy and controls" (an answer is never made under another customer's rules, nor an order
placed or signed in another customer's name, when the customer is switched while a request is on its way) and on the
30% "working end-to-end demo" (after an answer the request box is one click or one "/" away, with the cursor in it).

The page's own modules are run with node, the frame (main.js) included, against a stand-in for the window: a root
that keeps what was drawn, a request box that records its focus, a window that records its scrolls. The gateway is a
stand-in too: it notes which customer's book each call was sent to and answers after a delay, so a customer can be
switched while a call is on its way. Every sentence of these fixtures is made up.
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

PRELUDE = r"""
const JS = __JS__;
const say = (value) => { console.log(JSON.stringify(value)); process.exit(0); };
const wait = (ms) => new Promise((done) => setTimeout(done, ms));

// ---- the window: what was drawn, where it scrolled to, which field has the cursor ---------------------------------
const listeners = {};
const page = { html: "", focused: null, toast: "" };
const BOX_TOP = 300, BOX_BOTTOM = 500, RESULT_TOP = 700, HEADER = 72, GAP = 12;
const BODY = { id: "", dataset: {}, matches: () => false, closest: () => null };
const ASK = { getBoundingClientRect: () => ({ top: BOX_TOP - window.scrollY, bottom: BOX_BOTTOM - window.scrollY }) };
const BOX = { id: "ask-text", dataset: {}, selectionStart: 0, selectionEnd: 0, setSelectionRange() {},
  matches: (selector) => selector.includes("textarea"),
  closest: (selector) => (selector === ".ask" ? ASK : selector.includes("textarea") ? BOX : null),
  focus() { page.focused = "ask-text"; document.activeElement = BOX; },
  blur() { page.focused = null; document.activeElement = BODY; } };
const ROOT = { set innerHTML(value) { page.html = value; }, get innerHTML() { return page.html; },
  querySelectorAll: () => [] };
globalThis.document = { activeElement: BODY, body: BODY,
  addEventListener: (type, fn) => { listeners[type] = fn; },
  getElementById(id) {
    if (id === "app") return ROOT;
    if (id === "toasts") return { replaceChildren() {}, append(note) { page.toast = note.textContent; } };
    if (!page.html.includes('id="' + id + '"')) return null;
    if (id === "ask-text") return BOX;
    return { getBoundingClientRect: () => ({ top: RESULT_TOP - window.scrollY }) };
  },
  querySelector: (selector) => (selector === "header.header" ? { offsetHeight: HEADER } : null),
  createElement: () => ({ setAttribute() {}, remove() {}, className: "", textContent: "" }) };
globalThis.window = { scrollY: 0, innerHeight: 900, addEventListener: (type, fn) => { listeners[type] = fn; },
  scrollTo(x, y) { window.scrollY = y; } };
globalThis.location = { hash: "" };

// ---- the gateway: one book per customer, each call noted with the book it was sent to ---------------------------
const NAMES = { hotel: "Harbourside Hotel", ward: "City Hospital, Ward 4" };
const PEOPLE = { hotel: { purchasing_manager: "Hanna Laine", finance: "Hanna Laine", dietitian: "Hanna Laine" },
  ward: { purchasing_manager: "Jussi Nieminen", finance: "Jussi Nieminen", dietitian: "Sari Lehto" } };
const gw = { calls: [], delay: 0, alone: { hotel: false, ward: false }, verdict: "APPROVAL", onCall: null, offers: 0 };
const customer = (k) => ({ note: "", customer: { customer_number: "1", address: "Test street 1", delivery_days: "",
  contact: { name: PEOPLE[k].purchasing_manager, title: "Purchasing manager" }, usual: [], history: [],
  people: PEOPLE[k] } });
const MILK = { text: "milk", product_type: "milk", quantity: 100, unit: "L" };
const REQUEST = { needed_by: "2026-11-16", lines: [MILK] };
const offer = (k) => ({ offer_id: "off_" + k + "_" + ++gw.offers, source: "replay", request: REQUEST,
  suggestions: [], excluded: [], notes: [], candidates_considered: 1,
  options: [{ option_id: "opt_1", kind: "BEST_CONFIRMED", rank: 1, title: "TITLE",
    summary: "ANSWER-UNDER-" + k + "-RULES",
    lines: [{ product_id: "100001", name: "Test milk 1 L", vendor_name: "TEST OY", sales_unit: "PS", quantity: 100,
      unit_net_price: 2, net: 200, request_line_index: 0, claims: [],
      availability: { state: "CONFIRMED", usable_amount: 500, sales_unit: "PS", available_date: "2026-11-16" } }],
    totals: { net: 200, gross: 228 }, constraint_checks: [],
    decision: { verdict: gw.verdict, required_roles: gw.verdict === "AUTO" ? [] : ["purchasing_manager"],
      sentence: "MADE-UP-DECISION.", fired: [] } }] });
const order = (k, body, status) => ({ order_id: "ord_" + k, status, approval_id: "apr_" + k, placed_by: "AGENT",
  created_at: "2026-11-12T12:15:00Z", updated_at: "2026-11-12T12:15:00Z", status_sentence: "MADE-UP-OUTCOME.",
  decision: { required_roles: gw.verdict === "AUTO" ? [] : ["purchasing_manager"], fired: [] },
  option: { lines: [], totals: { net: 200 } }, key: body?.key });
function answer(k, method, path, body) {
  if (path === "/kitchen") return { profile: { display_name: NAMES[k], auto_order_enabled: gw.alone[k],
    excluded_allergens: [] } };
  if (path === "/customer") return customer(k);
  if (path === "/orders" && method === "GET") return [];
  if (path === "/approvals") return [];
  if (path === "/read") return { source: "rule-based", sentence: "", request: REQUEST };
  if (path === "/offers") return offer(k);
  if (path === "/orders") return order(k, body, gw.verdict === "AUTO" ? "ORDERED" : "PENDING_APPROVAL");
  if (path.endsWith("/decision")) return order(k, body, "ORDERED");
  return null;
}
globalThis.fetch = async (url, init = {}) => {
  const reply = (status, data) => ({ ok: status === 200, status, json: async () => data });
  if (!String(url).startsWith("/shop/api")) return reply(200, { mode: "replay" });
  const k = init.headers["X-Shop-Kitchen"], method = init.method || "GET", path = String(url).slice("/shop/api".length);
  const body = init.body ? JSON.parse(init.body) : null;
  gw.calls.push({ k, method, path, body });
  if (gw.onCall) gw.onCall({ k, method, path });
  await wait(gw.delay);
  const data = answer(k, method, path, body);
  return data === null ? reply(404, { title: "Not found", detail: "MADE-UP-404" }) : reply(200, data);
};

const store = await import(JS + "/store.js");
const core = await import(JS + "/core.js");
await import(JS + "/main.js");
// No brand assumption of a customer stands between an answer and an order.
for (const k of ["hotel", "ward"]) store.mine(k).learned = [];
await wait(30);  // the page has opened the first customer

const switchTo = (id) => core.handlers.switch({ dataset: { id } });
const send = (text) => core.handlers.ask({ elements: { text: { value: text } } });
const sentTo = (path, method = "POST") =>
  gw.calls.filter((c) => c.path === path && c.method === method).map((c) => c.k);
const thread = (k) => store.mine(k).thread;
// The customer is switched to `other` while the nth call made for `from`'s book, counted from now, is on its way.
function switchDuring(from, nth, other) {
  let seen = 0;
  const done = { switched: null };
  gw.onCall = (call) => {
    if (call.k !== from || ++seen !== nth) return;
    gw.onCall = null;
    done.switched = switchTo(other);
  };
  return done;
}
const key = (extra = {}) => ({ key: "/", ctrlKey: false, metaKey: false, altKey: false, target: BODY, prevented: false,
  preventDefault() { this.prevented = true; }, ...extra });
"""


def _node(script: str) -> Any:
    """What a script prints as JSON, run by node on the page's own modules; skipped where node is not installed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    source = PRELUDE.replace("__JS__", json.dumps(str(SHOP_JS))) + script
    # The script is this file's own text around the page's modules: nothing from outside is run.
    done = subprocess.run(  # noqa: S603
        [node, "--input-type=module", "-e", source], capture_output=True, text=True, timeout=120, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- 1. a request belongs to the customer that was active when it was sent ------------------------------------------

# The calls one typed sentence makes for its customer's book, in order: the rules read back, the reading, the offer.
STEPS = {1: "the rules are read back", 2: "the sentence is read", 3: "the offer is made"}


@pytest.mark.parametrize("nth", sorted(STEPS), ids=[STEPS[n].replace(" ", "-") for n in sorted(STEPS)])
def test_a_request_keeps_its_customer_when_the_customer_is_switched_on_the_way(nth: int) -> None:
    found = _node(
        """
    await switchTo("ward");
    gw.calls.length = 0; gw.delay = 15;
    const during = switchDuring("ward", NTH, "hotel");
    await send("100 litres of lactose-free milk by Monday");
    await during.switched;
    const turn = thread("ward").at(-1);
    const hotelPage = page.html;
    await switchTo("ward");
    say({ switched: Boolean(during.switched), read: sentTo("/read"), offers: sentTo("/offers"),
      rules: sentTo("/kitchen", "PUT").concat(sentTo("/kitchen", "GET")).filter((k) => !NAMES[k]),
      answer: turn.offer.options[0].summary, offerId: turn.offer.offer_id.slice(0, 8),
      hotelResults: thread("hotel").length,
      onHotelPage: hotelPage.includes("result-" + turn.id) || hotelPage.includes("ANSWER-UNDER"),
      hotelPageIsHotels: hotelPage.includes("Harbourside Hotel"),
      onWardPage: page.html.includes("result-" + turn.id) && page.html.includes("ANSWER-UNDER-ward-RULES"),
      wardShowsHotels: page.html.includes("ANSWER-UNDER-hotel-RULES") });
    """.replace("NTH", str(nth))
    )

    assert found["switched"]  # the customer was switched while the request was on its way
    # Every step of the request went to the book of the customer it was sent for.
    assert found["read"] == ["ward"] and found["offers"] == ["ward"]
    assert found["answer"] == "ANSWER-UNDER-ward-RULES" and found["offerId"] == "off_ward"
    # The other customer's page draws nothing of it; it waits on its own customer's page.
    assert found["hotelPageIsHotels"] and not found["onHotelPage"] and found["hotelResults"] == 0
    assert found["onWardPage"] and not found["wardShowsHotels"]


def test_the_settings_sent_to_a_book_are_its_own_customers_whatever_is_switched_to() -> None:
    found = _node("""
    await switchTo("ward");
    gw.calls.length = 0; gw.delay = 15;
    core.app.data.authority = null;  // the ward's rules are not confirmed: the request sets them up first
    const during = switchDuring("ward", 1, "hotel");
    await send("100 litres of lactose-free milk by Monday");
    await during.switched;
    say(gw.calls.filter((c) => c.path === "/kitchen" && c.method === "PUT").map((c) => [c.k, c.body.display_name]));
    """)

    assert ["ward", "City Hospital, Ward 4"] in found and ["hotel", "Harbourside Hotel"] in found
    assert all(name == {"ward": "City Hospital, Ward 4", "hotel": "Harbourside Hotel"}[book] for book, name in found)


def test_the_agent_orders_alone_only_under_the_setting_of_the_customer_that_asked() -> None:
    found = _node("""
    gw.verdict = "AUTO"; gw.alone.hotel = true;  // only the hotel lets its agent order alone
    await switchTo("ward"); await switchTo("hotel");
    // The ward's request, the hotel switched to while its offer is made: nothing is ordered for anybody.
    await switchTo("ward");
    gw.calls.length = 0; gw.delay = 15;
    let during = switchDuring("ward", 3, "hotel");
    await send("100 litres of lactose-free milk by Monday");
    await during.switched;
    const wardOrders = sentTo("/orders");
    // The hotel's request, the ward switched to while its offer is made: the hotel's agent orders, in the hotel's book.
    gw.calls.length = 0;
    during = switchDuring("hotel", 3, "ward");
    await send("100 litres of lactose-free milk by Monday");
    await during.switched;
    const placed = gw.calls.filter((c) => c.path === "/orders" && c.method === "POST");
    say({ wardOrders, books: placed.map((c) => c.k),
      keys: placed.map((c) => c.body.key.split(".").slice(0, 3).join(".")),
      kept: thread("hotel").at(-1).order?.order_id, wardHolds: thread("ward").some((t) => t.order) });
    """)

    assert found["wardOrders"] == []  # the ward never switched ordering alone on: the hotel's setting is not its own
    assert found["books"] == ["hotel"] and found["keys"] == ["shop.hotel.off_hotel_2"]
    assert found["kept"] == "ord_hotel" and found["wardHolds"] is False


def test_an_order_confirmed_by_a_click_is_placed_and_signed_for_the_customer_whose_result_it_is() -> None:
    found = _node("""
    await switchTo("ward"); await switchTo("hotel");  // both customer files are read: each has its own people
    await send("100 litres of lactose-free milk by Monday");
    const turn = thread("hotel").at(-1);
    gw.calls.length = 0; gw.delay = 15;
    const during = switchDuring("hotel", 2, "ward");  // 1: the rules read back, 2: the order, then the signature
    await core.handlers.confirm({ dataset: { turn: turn.id, option: "opt_1" } });
    await during.switched;
    const signed = gw.calls.filter((c) => c.path.endsWith("/decision"));
    say({ switched: Boolean(during.switched), orders: sentTo("/orders"), books: signed.map((c) => c.k),
      names: signed.map((c) => c.body.name), paths: signed.map((c) => c.path), signedBy: turn.signedBy,
      status: turn.order?.status });
    """)

    assert found["switched"] and found["orders"] == ["hotel"]
    assert found["books"] == ["hotel"] and found["paths"] == ["/approvals/apr_hotel/decision"]
    assert found["names"] == ["Hanna Laine, Harbourside Hotel"] and found["signedBy"] == "Hanna Laine"
    assert found["status"] == "ORDERED"


# --- 6. after an answer the next sentence is one keystroke away ------------------------------------------------------


def test_new_request_stands_on_the_newest_result_only_and_takes_no_line_of_its_own() -> None:
    found = _node("""
    const empty = page.html.includes('data-act="new-request"');
    await send("100 litres of lactose-free milk by Monday");
    await send("200 litres of lactose-free milk by Monday");
    const [older, newest] = thread("hotel").slice(-2);
    const cardOf = (t) => { const from = page.html.indexOf('id="result-' + t.id + '"');
      const next = page.html.indexOf("<article", from + 1);
      return page.html.slice(from, next < 0 ? undefined : next); };
    say({ empty, count: page.html.split('data-act="new-request"').length - 1,
      newest: cardOf(newest).includes('data-act="new-request"'),
      older: cardOf(older).includes('data-act="new-request"'),
      before: cardOf(newest).indexOf('data-act="new-request"') < cardOf(newest).indexOf("ANSWER-UNDER"),
      words: />New request<kbd[^>]*>\\/<\\/kbd><\\/button>/.test(page.html),
      box: page.html.indexOf('id="ask-text"') < page.html.indexOf('class="results') });
    """)
    css = (SHOP / "shop.css").read_text(encoding="utf-8")
    rule = css.split(".new-request {", 1)[1].split("}", 1)[0]

    assert found == {
        "empty": False, "count": 1, "newest": True, "older": False, "before": True, "words": True, "box": True,
    }
    assert "position: absolute" in rule  # out of the flow: the answer under it is where it was


def test_new_request_and_the_slash_key_bring_the_box_back_with_the_cursor_in_it() -> None:
    found = _node("""
    await send("100 litres of lactose-free milk by Monday");
    const after = { y: window.scrollY, focused: page.focused };  // the page went to the answer; the box has no cursor
    // The control on the result.
    const button = { dataset: { act: "new-request" }, tagName: "BUTTON" };
    listeners.click({ target: { closest: (s) => (s === "[data-act]" ? button : null) }, preventDefault() {} });
    await wait(5);
    const clicked = { y: window.scrollY, focused: page.focused };
    // The key, from the answer again, in a window too short to hold the box from the top of the page.
    BOX.blur(); window.scrollTo(0, 616); window.innerHeight = 400;
    const slash = key();
    listeners.keydown(slash);
    const pressed = { y: window.scrollY, focused: page.focused, prevented: slash.prevented };
    // In a field "/" is a character; with Ctrl or Cmd it is the browser's.
    BOX.blur(); window.scrollTo(0, 616);
    const typed = key({ target: { closest: () => ({}), matches: () => false } });
    const withCtrl = key({ ctrlKey: true });
    listeners.keydown(typed); listeners.keydown(withCtrl);
    const left = { y: window.scrollY, focused: page.focused, prevented: typed.prevented || withCtrl.prevented };
    // From another page of the shop: the request page is opened, and its box takes the cursor.
    location.hash = "#/orders"; listeners.hashchange();
    listeners.keydown(key({ shiftKey: true }));  // "/" is Shift+7 on many keyboards
    const hash = location.hash;
    listeners.hashchange();
    say({ after, clicked, pressed, left, hash, fromOrders: { y: window.scrollY, focused: page.focused } });
    """)

    assert found["after"] == {"y": 700 - 72 - 12, "focused": None}
    assert found["clicked"] == {"y": 0, "focused": "ask-text"}  # the box fits in the first window: the page's top
    assert found["pressed"] == {"y": 300 - 72 - 12, "focused": "ask-text", "prevented": True}  # else under the header
    assert found["left"] == {"y": 616, "focused": None, "prevented": False}
    assert found["hash"] == "#/" and found["fromOrders"]["focused"] == "ask-text"


def test_an_answer_that_arrives_while_the_next_sentence_is_typed_leaves_the_page_at_the_box() -> None:
    found = _node("""
    gw.delay = 15;
    const sent = send("100 litres of lactose-free milk by Monday");
    await wait(5);
    const waiting = { y: window.scrollY, focused: page.focused };  // at the result, while it is being read
    listeners.keydown(key());
    const back = { y: window.scrollY, focused: page.focused };
    await sent;
    say({ waiting, back, answered: page.html.includes("ANSWER-UNDER-hotel-RULES"),
      then: { y: window.scrollY, focused: page.focused } });
    """)

    assert found["waiting"] == {"y": 616, "focused": None}
    assert found["back"] == {"y": 0, "focused": "ask-text"}
    assert found["answered"] and found["then"] == {"y": 0, "focused": "ask-text"}
