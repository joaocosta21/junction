"""FIX-U2, items 2 to 7: what the pages around the answer draw, run from the page's own scripts by node.

Scores on the 30% demo (the menu plan and the order page read as one thing after an order), on the 20% "autonomy
and controls" (Valio Aimo's view of an order shows nothing of the buyer's private values; the dietitian's allergen
settings cannot be loosened on the page) and on the main goal (plain words: every step of a log has a title, a
paragraph is said once). No gateway sentence is pinned: the texts below are this file's own stand-ins.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

import tta.ui
from tta.contracts.audit import AuditEventType
from tta.customers import shipped_customers

SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
MIN_NODE = 22  # a page script is read as a module by its own syntax from this version on
PRELUDE = """
const store = new Map();
globalThis.localStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k) };
const answers = %(answers)s;
globalThis.fetch = async (url) => {
  const path = String(url).replace(/^.*\\/shop\\/api/, "");
  const body = answers[path];
  return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? {} };
};
const load = (name) => import(%(base)s + name);
const { memory } = await load("store.js");
memory.active = %(kitchen)s;
const core = await load("core.js");
core.setRenderer(() => {});
const settle = () => new Promise((done) => setTimeout(done, 30));
"""
PRIVATE_SUMMARY = "Covers 435 L. Its data rules out tree nuts, which this buyer excludes."
ORDER = {
    "order_id": "ord_1", "status": "ORDERED", "placed_by": "HUMAN", "approval_id": "apr_1",
    "status_sentence": "Ordered with approval by Hanna Laine, Harbourside Hotel (purchasing manager).",
    "option": {
        "title": "Best confirmed option", "summary": PRIVATE_SUMMARY,
        "lines": [
            {"product_id": "469363", "name": "Semi skimmed milk drink 1 L", "quantity": 384, "sales_unit": "ST",
             "unit_net_price": 2.48, "net": 952.32, "vendor_name": "Arla Oy",
             "availability": {"state": "CONFIRMED", "usable_amount": 384, "available_date": "2026-11-16"}},
            {"product_id": "462775", "name": "Fat free milk drink 1 L", "quantity": 51, "sales_unit": "ST",
             "unit_net_price": 2.57, "net": 131.07, "vendor_name": "Arla Oy",
             "availability": {"state": "CONFIRMED", "usable_amount": 51, "available_date": "2026-11-16"}},
        ],
        "totals": {"net": 1083.39, "gross": 1229.64},
    },
    "decision": {"policy_hash": "sha256:0123456789abcdef", "required_roles": ["purchasing_manager"], "fired": [
        {"rule_id": "P-01", "verdict": "APPROVAL", "approver_role": "purchasing_manager",
         "sentence": "The total is above the €750 limit per order of Harbourside Hotel."}]},
    "reliance": [], "record_note": "Recorded in the gateway's order book.",
}
SUPPLIER_TRAIL = {"chain": {"ok": True, "sentence": "The trail is intact."}, "events": [
    {"type": "tta.v1.order.confirmed", "time": "2026-11-15T01:00:00Z", "actor": {"display_name": "The gateway"},
     "sentence": "The order is ordered, with approval by the buyer's purchasing manager.", "rule_ids": ["P-01"],
     "facts": {}}]}
PAGE_SENTENCE = "The manufacturer's page says: contains almond."


def _run(body: str, kitchen: str = "hotel", answers: dict[str, Any] | None = None) -> Any:
    """What a script over the page's own modules prints as JSON, run by node; skipped where node cannot run it."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
    if int(version.stdout.strip().lstrip("v").split(".")[0]) < MIN_NODE:
        pytest.skip(f"node {version.stdout.strip()} does not read the page's scripts as modules")
    prelude = PRELUDE % {"answers": json.dumps(answers or {}), "kitchen": json.dumps(kitchen),
                         "base": json.dumps(SHOP_JS.as_uri() + "/")}
    # The script is this file's own text around the page's source: nothing from outside is run.
    done = subprocess.run([node, "--input-type=module", "-e", prelude + body], capture_output=True,  # noqa: S603
                          text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def _customer(customer_id: str) -> dict[str, Any]:
    """The customer route's answer for one customer, as far as the page reads who holds which role."""
    customer = shipped_customers()[customer_id]
    return {"note": "Synthetic.", "customer": {
        "name": customer.name, "contact": {"name": customer.contact.name, "title": "Kitchen manager"},
        "people": {role.value: name for role, name in customer.people.items()}, "usual": [], "history": []}}


# --- item 2: the menu plan has no decision box of its own, and says nothing once the option is ordered ------------

PLAN = """
const { planCard } = await load("views/plan.js");
const line = { request_line_index: 0, to_order: 0.4, unit: "KG", dishes: ["one"] };
const ingredient = { request_line_index: 0, recipe_product_type: "flour", product_type: "flour", role: "the structure",
  needed: 0.4, in_stock: 0, to_order: 0.4, unit: "KG", status: "TO_ORDER" };
const plan = { notes: [], cannot_be_sourced: [], lines: [line],
  dishes: [{ name: "One dish", left_out: [], ingredients: [ingredient] }] };
const option = { rank: 1, title: "Best confirmed option", lines: [], decision: { verdict: "APPROVAL",
  required_roles: ["purchasing_manager"], fired: [{ rule_id: "P-03", sentence: "Too little is covered." }] } };
const before = String(planCard({ plan, offer: { options: [option] } }, option));
const ordered = { plan, offer: { options: [option] }, order: { order_id: "ord_1", status: "ORDERED" } };
const after = String(planCard(ordered, option));
console.log(JSON.stringify({ before, after }));
"""


def test_the_plan_has_no_decision_box_of_its_own_and_follows_the_order() -> None:
    drawn = _run(PLAN, "bakery")

    assert 'class="verdict wait"' not in drawn["before"]  # the one box with the button is the request page's
    assert "Needs the purchasing manager:" in drawn["before"] and "nothing for flour" in drawn["before"]
    assert "Needs " not in drawn["after"]  # once ordered, the box below says who confirmed: nothing contradicts it


# --- items 3 and 4: the order page ---------------------------------------------------------------------------------

ORDER_PAGE = """
core.app.route = { name: "orders", id: "ord_1" };
core.app.data.orders = [%(order)s];
core.app.data.ready = true;
const orders = await load("views/orders.js");
const buyer = String(orders.view());
core.handlers.reader({ dataset: { reader: "supplier" } });
await settle();
const supplier = String(orders.view());
console.log(JSON.stringify({ buyer, supplier, title: orders.shortTitle(core.app.data.orders[0]) }));
"""


def _order_page() -> dict[str, str]:
    answers = {"/audit?order_id=ord_1&reader=supplier": SUPPLIER_TRAIL}
    drawn: dict[str, str] = _run(ORDER_PAGE % {"order": json.dumps(ORDER)}, "hotel", answers)
    return drawn


def test_the_order_page_has_a_short_title_and_the_summary_as_text() -> None:
    drawn = _order_page()

    title = drawn["title"]
    assert title.startswith("2 products · ") and title.endswith(" · delivery Mon 16 Nov") and len(title) < 60
    head = drawn["buyer"].split("<h1>", 1)[1].split("</h1>", 1)[0]
    assert head == title and PRIVATE_SUMMARY not in head
    assert f'<p class="small">{PRIVATE_SUMMARY}</p>' in drawn["buyer"]  # the summary, as text under the title


def test_valio_aimos_view_of_an_order_shows_nothing_of_the_buyers_private_values() -> None:
    drawn = _order_page()

    buyer, supplier = drawn["buyer"], drawn["supplier"]
    assert "€750 limit" in buyer and "Hanna Laine" in buyer  # the buyer's own view keeps them
    for private in ("750", "Hanna Laine", "tree nuts", "Rules that applied", "Policy fingerprint"):
        assert private not in supplier, private
    assert "This is Valio Aimo's view of the order, not Harbourside Hotel's" in supplier
    assert "What Valio Aimo receives" in supplier and "469363" in supplier and "462775" in supplier
    assert "with approval by the buyer&#39;s purchasing manager" in supplier  # Valio Aimo's own log is there
    assert supplier.count('data-act="reader"') == 2 and 'aria-selected="true"' in supplier


# --- item 7: every step of a log has a title; a paragraph of evidence is said once ---------------------------------

TITLES = """
const { eventName } = await load("views/trail.js");
console.log(JSON.stringify(%(types)s.map((type) => eventName(type))));
"""


def test_every_kind_of_step_has_a_title_a_person_reads() -> None:
    types = [f"tta.v1.{each.value}" for each in AuditEventType] + ["tta.v1.something.new_one"]

    titles = _run(TITLES % {"types": json.dumps(types)})

    assert len(titles) == len(types)
    for kind, title in zip(types, titles, strict=True):
        assert title and title[0].isupper() and "." not in title.rstrip(".") and "_" not in title, (kind, title)
    assert titles[-1] == "Something new one"


WAITING = """
core.app.data.orders = [%(order)s];
core.app.data.approvals = [%(approval)s];
const approvals = await load("views/approvals.js");
console.log(JSON.stringify(String(approvals.view())));
"""


def test_the_waiting_card_says_the_web_pages_paragraph_once() -> None:
    approval = {
        "approval_id": "apr_1", "order_id": "ord_1", "offer_id": "off_1", "option_id": "opt_2", "status": "PENDING",
        "required_roles": ["dietitian"], "decisions": [],
        "reasons": [f"Web evidence for product 465793 is attached for the dietitian: {PAGE_SENTENCE}",
                    "The product data does not rule out an excluded allergen."],
        "evidence": [{"product_id": "465793", "found": True, "source_url": "https://example.org/product",
                      "sentence": PAGE_SENTENCE, "contains": ["almond"], "may_contain": [], "free_from": []}],
    }
    waiting = {**ORDER, "status": "PENDING_APPROVAL"}

    page = _run(WAITING % {"order": json.dumps(waiting), "approval": json.dumps(approval)}, "school")

    assert page.count(PAGE_SENTENCE.replace("'", "&#39;")) == 1  # in the evidence block, which names its source
    assert "Found on the web, not Valio Aimo data" in page
    assert "The product data does not rule out an excluded allergen." in page  # every other reason stays


# --- item 6: the dietitian's allergen settings cannot be loosened on the page ------------------------------------

SETTINGS = """
const customer = await load("customer.js");
await customer.loadCustomer(%(kitchen)s);
const settings = await load("views/settings.js");
const first = String(settings.view());
core.handlers.allergen({ dataset: { code: %(code)s }, checked: false });
core.handlers["allergen-rule"]({ dataset: { code: %(code)s, rule: "DECLARED_ONLY" } });
const { mine } = await load("store.js");
console.log(JSON.stringify({ first, after: String(settings.view()), saved: mine().settings.excluded_allergens }));
"""


def _settings_page(kitchen: str, customer_id: str, code: str) -> dict[str, Any]:
    body = SETTINGS % {"kitchen": json.dumps(kitchen), "code": json.dumps(code)}
    drawn: dict[str, Any] = _run(body, kitchen, {"/customer": _customer(customer_id)})
    return drawn


@pytest.mark.parametrize(("kitchen", "customer_id", "excluded"), [
    ("school", "school-kitchen", ["AN", "AP", "AS"]), ("ward", "allergy-ward", ["AM", "AW"])])
def test_where_a_dietitian_decides_her_exclusions_cannot_be_removed_or_relaxed_on_the_page(
    kitchen: str, customer_id: str, excluded: list[str]
) -> None:
    dietitian = shipped_customers()[customer_id].people[next(
        role for role in shipped_customers()[customer_id].people if role.value == "dietitian")]

    drawn = _settings_page(kitchen, customer_id, excluded[0])

    page = drawn["first"]
    assert page.count('data-change="allergen"') == 14
    locked = [part for part in page.split('<input type="checkbox" data-change="allergen"')[1:]
              if part.split(">", 1)[0].rstrip().endswith("disabled")]
    assert len(locked) == len(excluded) and all(" checked " in part.split(">", 1)[0] for part in locked)
    assert f"Set by {dietitian}, the dietitian:" in page and "cannot be removed or made less strict here" in page
    assert page.count('data-rule="DECLARED_ONLY" disabled') == len(excluded)
    assert 'data-rule="STRICT" disabled' not in page
    # A click that gets through all the same changes nothing: the exclusion stays, under the strict rule.
    assert drawn["after"] == page and drawn["saved"] == excluded


def test_where_one_person_holds_every_role_the_allergen_settings_are_theirs_to_change() -> None:
    drawn = _settings_page("hotel", "hotel-kitchen", "AM")

    assert "the dietitian:" not in drawn["first"]
    assert not [part for part in drawn["first"].split('data-change="allergen"')[1:]
                if part.split(">", 1)[0].rstrip().endswith("disabled")]


# --- item 5: the back office says whose page it is ----------------------------------------------------------------

BACK_OFFICE = """
const backoffice = await load("views/backoffice.js");
console.log(JSON.stringify(String(backoffice.view())));
"""


def test_the_back_office_says_it_is_valio_aimos_page_and_not_the_customers() -> None:
    page = _run(BACK_OFFICE, "hotel")

    assert "<h1>Valio Aimo's back office (demo)</h1>" in page
    assert "You are looking at this page as Valio Aimo, the wholesaler, not as Harbourside Hotel" in page
    assert "A customer never sees it" not in page
