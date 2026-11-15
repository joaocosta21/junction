// Standing orders ("Standard orders" in Valio Aimo's webshop): what this customer orders on a cadence, read from
// GET /shop/api/standing-orders with each order's trend, or from the customer file when that route does not answer.
// Every standing order can be renewed once from its card, at its usual quantity or at one the person types: the
// gateway writes that renewal as a request (POST /shop/api/standing-orders/{id}/renewal), and the page sends it as a
// new request (assistant.js), whose offer a person confirms like any other. A quantity far from the usual one is not
// refused here: the offer says so, and the person decides. A trend says the customer orders more, or less, week
// after week; "Renew once at 84 L" posts its request unchanged, the same way. The quantity a standing order stores
// does not change here. The past orders are the customer file's, labelled synthetic.
import { Refusal } from "../api.js";
import { api, on, render } from "../core.js";
import { customerKnown, customerNote, customerOf, historyRows, productLabel, unitWord, usualUnit } from "../customer.js";
import { html, num, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { SYNTHETIC } from "../kitchens.js";
import { active, memory } from "../store.js";
import { plain } from "../words.js";
import { sendAsWritten } from "./assistant.js";
import { customerPending, spinner } from "./parts.js";
import { forPeople } from "./refusal.js";

// `renewing`: the standing order whose renewal is on its way; `refused`: why a renewal was not sent or the gateway's
// refusal of it, by standing order, said under the button that was used until the next try; `typed`: this week's
// quantity of each line as the person typed it, by standing order and line (none typed: the stored quantity).
const state = { kitchen: null, list: null, problem: null, loading: false, renewing: null, refused: {}, typed: {} };

const isObject = (x) => x && typeof x === "object";
// One standing order of the route's answer, whether it comes as the order itself or wrapped with its trend.
const orderOf = (item) => (isObject(item?.standing_order) ? { ...item.standing_order, trend: item.trend ?? item.standing_order.trend } : item);

function listOf(answer) {
  const items = Array.isArray(answer) ? answer : Array.isArray(answer?.standing_orders) ? answer.standing_orders : null;
  if (!items) throw new Error("The gateway's answer lists no standing orders.");
  return items.map(orderOf).filter((so) => isObject(so) && so.standing_order_id);
}

async function load() {
  const kitchen = memory.active;
  if (state.kitchen !== kitchen) {
    state.typed = {};
    state.refused = {};
  }
  state.kitchen = kitchen;
  state.loading = true;
  state.problem = null;
  render();
  try {
    const list = listOf(await api().standingOrders());
    if (state.kitchen === kitchen) state.list = list;
  } catch (error) {
    if (state.kitchen === kitchen) {
      state.list = null;
      state.problem = error.message || "The gateway did not answer.";
    }
  }
  state.loading = false;
  render();
}

// ---- renewing once ---------------------------------------------------------------------------------------------

const BASE = "/shop/api";
const TREND = "trend"; // the button of the trend box
const TYPED = "typed"; // the card's own renewal, at the quantities in its fields
const NOT_A_QUANTITY = "Write this week's quantity as a number above 0, for example 290. Nothing was sent.";
// A quantity as the gateway takes it: above 0, at most 1,000,000, at most three decimals; a comma or a point.
const QUANTITY = /^\d{1,7}(?:[.,]\d{1,3})?$/;
const MAX_QUANTITY = 1000000;

const shown = () => state.list || (state.problem ? fromTheFile() : []);
const findOrder = (id) => shown().find((one) => one.standing_order_id === id);
const linesOf = (so) => (so.lines || []).filter(isObject);
const unitOf = (line) => (line.unit ? unitWord(line.unit) : usualUnit(line.product_id));

// This week's quantity of one line as the field holds it: what was typed, else the stored quantity.
const typedOf = (so, index) => state.typed[so.standing_order_id]?.[index] ?? String(Number(linesOf(so)[index].quantity));

function quantityOf(text) {
  const written = String(text).trim();
  if (!QUANTITY.test(written)) return null;
  const value = Number(written.replace(",", "."));
  return value > 0 && value <= MAX_QUANTITY ? value : null;
}

// One quantity per line, in order; null when a field does not hold a quantity.
function quantitiesOf(so) {
  const values = linesOf(so).map((_, index) => quantityOf(typedOf(so, index)));
  return values.every((value) => value !== null) ? values : null;
}

// The gateway writes the renewal: the standing order's own request at these quantities, naming the standing order
// (tta.ui.shop_api). The call offers and orders nothing.
async function renewalRequest(id, quantities) {
  let response;
  try {
    response = await fetch(`${BASE}/standing-orders/${encodeURIComponent(id)}/renewal`, {
      method: "POST",
      headers: { "X-Shop-Request": "1", "X-Shop-Kitchen": memory.active, "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(quantities.length ? { quantities } : {}),
    });
  } catch {
    throw new Refusal(0, { title: "No connection", detail: "The gateway could not be reached. Check that it is running." });
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Refusal(response.status, data);
  return data;
}

const refuse = (id, from, problem) => {
  state.renewing = null;
  state.refused = { ...state.refused, [id]: { ...problem, from } };
  render();
};

// The renewal is sent from here; its offer is shown as a result card on the request page, where it is confirmed. A
// renewal the gateway refuses keeps the person here, with the gateway's own sentence under the button they used.
async function send(so, from, request) {
  const id = so.standing_order_id;
  const names = Object.fromEntries(linesOf(so).filter((l) => l.product_id && l.name).map((l) => [l.product_id, l.name]));
  const turn = await sendAsWritten("standing", so.name || id, request, { names });
  if (turn.phase === "failed") return refuse(id, from, turn.problem);
  state.renewing = null;
  state.typed = { ...state.typed, [id]: undefined };
  location.hash = "#/";
}

function begin(id) {
  state.renewing = id;
  state.refused = { ...state.refused, [id]: null };
  render();
}

on("standing-renew", async (el) => {
  const so = findOrder(el.dataset.id);
  const request = so?.trend?.accept_request;
  if (!isObject(request) || state.renewing) return;
  begin(so.standing_order_id);
  return send(so, TREND, request);
});

on("standing-quantity", (el) => {
  const id = el.dataset.id;
  state.typed = { ...state.typed, [id]: { ...(state.typed[id] || {}), [el.dataset.line]: el.value } };
  state.refused = { ...state.refused, [id]: null };
  render();
});

on("standing-renew-at", async (form) => {
  const so = findOrder(form.dataset.id);
  if (!so || state.renewing) return;
  const id = so.standing_order_id;
  const quantities = quantitiesOf(so);
  if (!quantities) return refuse(id, TYPED, { message: NOT_A_QUANTITY });
  begin(id);
  let request;
  try {
    request = await renewalRequest(id, quantities);
  } catch (error) {
    return refuse(id, TYPED, { message: error.message, title: error.title });
  }
  return send(so, TYPED, request);
});

function refusedLine(so, from) {
  const problem = state.refused[so.standing_order_id];
  if (!problem || problem.from !== from) return "";
  const said = forPeople(problem.message);
  return html`<p class="small" role="alert"><b>Not renewed:</b> ${said.length ? said.join(" ") : problem.title || "The gateway refused the renewal."}</p>`;
}

// ---- one standing order ----------------------------------------------------------------------------------------

function lineRow(line) {
  const u = line.unit ? unitWord(line.unit) : usualUnit(line.product_id);
  return html`<li><b>${line.name ? `${line.name} (${line.product_id})` : productLabel(line.product_id)}</b> × ${num(line.quantity)} ${u}</li>`;
}

function trendBox(so) {
  const t = so.trend;
  if (!isObject(t) || !t.sentence) return html`<p class="small muted">No change of quantity is suggested for it.</p>`;
  const amount = `${num(t.suggested_quantity)} ${unitWord(t.unit)}`;
  return html`<div class="verdict info">${icon("chart")}<div><b>Ordered more, or less, week after week</b>
    <p>${plain(t.sentence)}</p>
    ${isObject(t.accept_request) && t.suggested_quantity !== undefined ? html`<div class="actions"><button class="btn small" data-act="standing-renew" data-id="${so.standing_order_id}" ${state.renewing ? "disabled" : ""}>${state.renewing === so.standing_order_id ? "Sending…" : `Renew once at ${amount}`}</button></div>
    ${refusedLine(so, TREND)}` : ""}
  </div></div>`;
}

// The card's own renewal: one field per line, filled in with the stored quantity, and one button that says what it
// sends. One line: the button names the quantity; several: each field is named by its product.
function renewBox(so) {
  const id = so.standing_order_id;
  const lines = linesOf(so);
  const quantities = quantitiesOf(so);
  const one = lines.length === 1;
  const at = !quantities ? "" : one ? ` at ${num(quantities[0])} ${unitOf(lines[0])}` : lines.length ? " at these quantities" : "";
  const field = (line, index) => {
    const name = `standing-q-${id}-${index}`;
    const stored = `${num(line.quantity)} ${unitOf(line)}`;
    return html`<div class="field"><div><label for="${name}">${one ? "This week's quantity" : line.name || productLabel(line.product_id)}</label>
      <div class="help">The standing order stores ${stored}. Change it here for this one renewal.</div></div>
      <span class="money"><input type="text" inputmode="decimal" autocomplete="off" id="${name}" data-input="standing-quantity" data-id="${id}" data-line="${index}" value="${typedOf(so, index)}" aria-label="This week's quantity of ${line.name || productLabel(line.product_id)}, in ${unitOf(line)}"><span>${unitOf(line)}</span></span></div>`;
  };
  return html`<form class="decide" data-act="standing-renew-at" data-id="${id}" aria-label="Renew ${so.name || id} once">
    ${lines.map(field)}
    <div class="row"><button class="btn small" type="submit" ${state.renewing ? "disabled" : ""}>${state.renewing === id ? "Sending…" : `Renew once${at}`}</button></div>
    ${refusedLine(so, TYPED)}
    <p class="small muted">The stored quantity does not change, and nothing is ordered until you confirm the offer. A quantity far from what you usually order is flagged there, for you to decide.</p>
  </form>`;
}

// The customer file's past orders of this standing order's products, each row labelled synthetic.
function pastOrders(so) {
  if (!customerKnown()) return customerPending();
  const ids = new Set((so.lines || []).map((l) => l.product_id));
  const rows = historyRows()
    .map((h) => ({ date: h.date, lines: h.lines.filter((l) => ids.has(l.productId)) }))
    .filter((h) => h.lines.length);
  if (!rows.length) return html`<p class="small muted">No past order of its products in this customer's history.</p>`;
  return html`<details class="why"><summary>${icon("right")}Past orders of its products (${rows.length}) · synthetic</summary>
    <div class="why-body"><ul class="left-out">${rows.map((h) => html`<li>${shortDate(h.date)} · ${h.lines.map((l) => `${num(l.quantity)} ${l.unit} of ${l.label}`).join(", ")} <span class="tiny muted">· ${SYNTHETIC}</span></li>`)}</ul></div>
  </details>`;
}

function card(so) {
  const every = Number(so.cadence_days) > 0 ? `every ${so.cadence_days} days` : "";
  return html`<article class="card">
    <div class="card-title"><h3>${so.name || so.standing_order_id}</h3>${every ? html`<span class="tag">${every}</span>` : ""}</div>
    <ul class="side-list">${linesOf(so).map(lineRow)}</ul>
    ${trendBox(so)}
    ${renewBox(so)}
    ${pastOrders(so)}
  </article>`;
}

// ---- view ------------------------------------------------------------------------------------------------------

function fromTheFile() {
  return (customerOf()?.standing_orders || []).filter((so) => isObject(so) && so.standing_order_id);
}

export function view() {
  const k = active();
  if (state.kitchen !== memory.active) return spinner("Reading the standing orders…");
  const list = shown();
  return html`
    <div class="page-head"><div><div class="crumbs">${k.name}</div><h1>Standing orders (Standard orders)</h1>
      <div class="sub">What ${k.name} orders again and again. A renewal is a new request: an offer at today's prices and stock, which a person confirms.</div></div></div>
    ${state.problem ? html`<p class="small muted">The standing orders and their trends could not be read from the gateway: ${plain(state.problem)}${list.length ? " Shown here as the customer file holds them, without trends." : ""}</p>` : ""}
    ${state.loading && !state.list ? spinner("Reading the standing orders…") : ""}
    <section class="queue">${list.length ? list.map(card) : state.loading ? "" : html`<div class="card empty"><h3>No standing orders</h3><p>${k.name} has no standing order in this demo.</p></div>`}</section>
    ${customerNote() ? html`<p class="small muted">${plain(customerNote())}</p>` : ""}`;
}

export function enter() {
  load();
}
