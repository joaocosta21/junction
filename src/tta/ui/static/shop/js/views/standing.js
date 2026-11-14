// Standing orders ("Standard orders" in Valio Aimo's webshop): what this customer orders on a cadence, read from
// GET /shop/api/standing-orders with each order's trend, or from the customer file when that route does not answer.
// A trend says the customer orders more, or less, week after week; "Renew once at 84 L" posts its request unchanged
// as a new request (assistant.js), whose offer a person confirms like any other. The quantity a standing order
// stores does not change here. The past orders are the customer file's, labelled synthetic.
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

// `renewing`: the standing order whose renewal is on its way; `refused`: the gateway's refusal of a renewal, by
// standing order, said under its button until the next try.
const state = { kitchen: null, list: null, problem: null, loading: false, renewing: null, refused: {} };

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

// The renewal is sent from here; its offer is shown as a result card on the request page, where it is confirmed. A
// renewal the gateway refuses keeps the person here, with the gateway's own sentence under the button.
on("standing-renew", async (el) => {
  const so = (state.list || []).find((one) => one.standing_order_id === el.dataset.id);
  const request = so?.trend?.accept_request;
  if (!isObject(request) || state.renewing) return;
  const id = so.standing_order_id;
  state.renewing = id;
  state.refused = { ...state.refused, [id]: null };
  render();
  const turn = await sendAsWritten("standing", so.name || id, request);
  state.renewing = null;
  if (turn.phase === "failed") {
    state.refused = { ...state.refused, [id]: turn.problem };
    render();
    return;
  }
  location.hash = "#/";
});

function refusedLine(so) {
  const problem = state.refused[so.standing_order_id];
  if (!problem) return "";
  const said = forPeople(problem.message);
  return html`<p class="small"><b>Not renewed:</b> ${said.length ? said.join(" ") : problem.title || "The gateway refused the renewal."}</p>`;
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
    ${refusedLine(so)}
    <p class="small">This renews it once, as a new request at today's prices and stock: the quantity the standing order stores does not change, and nothing is ordered until you confirm it.</p>` : ""}
  </div></div>`;
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
    <ul class="side-list">${(so.lines || []).filter(isObject).map(lineRow)}</ul>
    ${trendBox(so)}
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
  const list = state.list || (state.problem ? fromTheFile() : []);
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
