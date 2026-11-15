// Orders: everything this kitchen has ordered, and for each order the audit trail as the buyer or Valio sees it.
// One order is shown as one of two readers, chosen at the top of its page. As the buyer: the order, who confirmed it,
// the rules that applied with the buyer's own limits, and the buyer's log. As Valio Aimo: what an order message
// would carry (products, quantities, prices) and Valio Aimo's view of the log, and nothing else. No limit amount,
// allergen, name or sentence of the buyer's stays on the page then, and the page says whose view it is.
import { app, api, deliveryOf, money, on, refresh, render } from "../core.js";
import { customerKnown, customerNote, historyRows } from "../customer.js";
import { html, longDate, num, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { SYNTHETIC } from "../kitchens.js";
import { active } from "../store.js";
import { plain } from "../words.js";
import { customerPending, netTotal, optionBlock, problemBox, progress, ruleList, signers, spinner, statusTag, stockUnit } from "./parts.js";
import { supplierHead, trailView } from "./trail.js";

// A same-origin path only, such as "/.well-known/jwks.json": never a link the record could point elsewhere.
const LOCAL_PATH = /^\/(?!\/)[A-Za-z0-9._~\/-]*$/;

// The gateway's signature of the order record (P12 W8), when it carries one: it says this gateway answered the
// record, never that Valio Aimo signed it. The shop's own calls carry none, and then nothing is shown.
function proofLine(order) {
  const proof = order.proof;
  if (!proof || typeof proof !== "object") return "";
  const jwks = typeof proof.jwks_path === "string" && LOCAL_PATH.test(proof.jwks_path) ? proof.jwks_path : null;
  return html`<p class="small proof">${icon("shield")}<span><b>${proof.demo_key ? "Signed by this gateway (demo key)" : "Signed by this gateway"}</b>${proof.note ? html`. ${plain(proof.note)}` : ""}${jwks ? html` Check it with the key at <a href="${jwks}">${jwks}</a>.` : ""}</span></p>`;
}

const trail = { orderId: null, reader: "buyer", data: null, problem: null, loading: false };

async function loadTrail() {
  if (!app.route.id) return;
  trail.loading = true;
  trail.problem = null;
  render();
  try {
    trail.data = await api().audit(app.route.id, trail.reader);
    trail.orderId = app.route.id;
  } catch (error) {
    trail.problem = error;
    trail.data = null;
  }
  trail.loading = false;
  render();
}

on("reader", (el) => {
  trail.reader = el.dataset.reader;
  return loadTrail();
});

// A short title: what was ordered, the total and the delivery day. The option's own summary is a paragraph, shown
// as text in the buyer's view (it can name what the buyer excludes, so Valio Aimo's view leaves it out).
export function shortTitle(order) {
  const lines = order.option?.lines || [];
  const what = lines.length === 1 ? lines[0].name : `${lines.length} products`;
  const delivery = deliveryOf(order.option);
  return [what, netTotal(order.option?.totals), delivery ? `delivery ${longDate(delivery)}` : ""].filter(Boolean).join(" · ");
}

// What an order message to Valio Aimo would carry: the products, how many, at which price, and the total.
function supplierLines(option) {
  return html`<table class="table"><thead><tr><th>Product</th><th class="num">Quantity</th><th class="num">Price, before tax</th><th class="num">Line total</th></tr></thead><tbody>
    ${(option.lines || []).map((l) => html`<tr><td>${l.name} <span class="small muted">(${l.product_id})</span></td><td class="num">${num(l.quantity)} ${stockUnit(l.sales_unit)}</td><td class="num">${money(l.unit_net_price)}</td><td class="num">${money(l.net)}</td></tr>`)}
    </tbody></table>
    <div class="kv"><span>Total before tax</span><b>${netTotal(option.totals)}</b></div>`;
}

function readerSwitch() {
  const tab = (reader, label) => html`<button role="tab" aria-selected="${String(trail.reader === reader)}" class="${trail.reader === reader ? "on" : ""}" data-act="reader" data-reader="${reader}">${label}</button>`;
  return html`<div class="right"><div class="small muted">Show this order as</div>
    <div class="seg" role="tablist" aria-label="Whose view of this order">${tab("buyer", active().name)}${tab("supplier", "What Valio Aimo sees")}</div></div>`;
}

function trailCard(title) {
  const t = trail.data;
  return html`<div class="card">
    <div class="card-title"><h3>${title}</h3></div>
    ${trail.loading ? spinner("Reading the trail…") : ""}
    ${trail.problem ? problemBox(trail.problem) : ""}
    ${t && !trail.loading ? trailView(t, trail.reader) : ""}
  </div>`;
}

function reliedOn(order) {
  return html`<div class="card">
          <div class="card-title"><h3>What the order relied on</h3></div>
          <ul class="side-list">${(order.reliance || []).map(
            (r) => html`<li><span><b>${r.product_id}</b> · ${money(r.unit_net_price)} · ${String(r.availability_state).toLowerCase().replaceAll("_", " ")}<br><span class="small muted">${r.rechecked_at ? `checked again ${shortDate(r.rechecked_at)} ${String(r.rechecked_at).slice(11, 16)}` : ""}${r.closing_time ? ` · closing time ${shortDate(r.closing_time)} ${String(r.closing_time).slice(11, 16)}` : ""} · ${r.source === "replay" ? "recorded data" : "live data"}</span></span></li>`
          )}</ul>
          <p class="small muted">${order.record_note}</p>
        </div>`;
}

function detail(order) {
  const supplier = trail.reader === "supplier";
  const approval = app.data.approvals.find((a) => a.order_id === order.order_id);
  const head = html`<div class="page-head">
      <div><div class="crumbs"><a href="#/orders">Orders</a> · ${order.order_id}</div><h1>${shortTitle(order)}</h1>
      <div class="sub">${statusTag(order)}</div></div>
      ${readerSwitch()}
    </div>`;
  if (supplier) {
    return html`${head}
    ${supplierHead(active().name)}
    <div class="grid">
      <section class="stack">
        <div class="card">
          <div class="card-title"><h3>What Valio Aimo receives</h3></div>
          ${supplierLines(order.option)}
        </div>
        ${trailCard("Every step, as Valio Aimo sees it")}
      </section>
      <aside class="side">${reliedOn(order)}</aside>
    </div>`;
  }
  return html`${head}
    <div class="grid">
      <section class="stack">
        <div class="card">
          <div class="card-title"><h3>What was ordered</h3></div>
          <p class="small">${plain(order.option.summary)}</p>
          ${optionBlock(order.option)}
          <p class="small muted">${plain(order.status_sentence)}</p>
          ${proofLine(order)}
          ${approval && order.status === "PENDING_APPROVAL" ? html`<div class="decide">${signers(approval)}${progress(approval)}<div class="row"><a class="btn small" href="#/approvals">Go to approvals</a></div></div>` : ""}
        </div>
        ${trailCard("Audit trail")}
      </section>
      <aside class="side">
        <div class="card">
          <div class="card-title"><h3>Rules that applied</h3></div>
          ${ruleList(order.decision?.fired)}
          ${order.decision?.policy_hash ? html`<p class="small muted">Policy fingerprint <span class="rule-id">${String(order.decision.policy_hash).slice(7, 19)}</span> is stored with the order, so anyone can tell later which rules decided.</p>` : ""}
        </div>
        ${reliedOn(order)}
      </aside>
    </div>`;
}

// The customer file's past orders, as the customer route gives them. Every row says what it is, also at phone width
// where the status column is hidden, and the route's own note says the whole customer is made up. The file gives
// quantities, not totals, so no total is shown.
function pastOrders() {
  if (!customerKnown()) return html`<p class="section-label">Earlier orders</p><div class="card">${customerPending()}</div>`;
  return html`<p class="section-label">Earlier orders · synthetic history</p>
    <div class="card"><table class="table"><thead><tr><th>Delivery</th><th>Products</th><th class="hide-s">Status</th></tr></thead><tbody>
    ${historyRows().map(
      (h) => html`<tr><td class="nowrap">${shortDate(h.date)}</td><td>${h.lines.map((l) => html`<div>${l.label} <span class="muted">× ${num(l.quantity)} ${l.unit}</span></div>`)}<div class="tiny muted">${SYNTHETIC}</div></td><td class="hide-s"><span class="tag">Delivered</span></td></tr>`
    )}
    </tbody></table><p class="small muted">${plain(customerNote())}</p></div>`;
}

export function view() {
  const k = active();
  if (app.route.id) {
    const order = app.data.orders.find((o) => o.order_id === app.route.id);
    if (!order) return app.data.ready ? html`<div class="card empty"><h3>Order not found</h3><p>It may belong to another customer, or the demo order book was emptied.</p><a class="btn" href="#/orders">All orders</a></div>` : spinner("Loading…");
    return detail(order);
  }
  const list = app.data.orders.slice().sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  return html`
    <div class="page-head"><div><div class="crumbs">${k.name}</div><h1>Orders</h1><div class="sub">Every order with who placed it, why, and its audit trail.</div></div></div>
    ${app.data.problem ? problemBox(app.data.problem) : ""}
    <div class="card">
      ${list.length
        ? html`<table class="table"><thead><tr><th>Order</th><th>Products</th><th class="hide-s">Delivery</th><th class="num">Total</th><th>Status</th></tr></thead><tbody>
          ${list.map(
            (o) => html`<tr class="click" data-act="open" data-id="${o.order_id}"><td class="nowrap"><a href="#/orders/${o.order_id}">${o.order_id.slice(4, 10)}</a></td><td>${o.option.lines.map((l) => html`<div>${l.name}</div>`)}</td><td class="hide-s nowrap">${deliveryOf(o.option) ? shortDate(deliveryOf(o.option)) : "–"}</td><td class="num">${netTotal(o.option.totals)}</td><td>${statusTag(o)}</td></tr>`
          )}</tbody></table>`
        : html`<div class="empty"><h3>No orders in this demo yet</h3><p>Orders confirmed on the request page show up here.</p><a class="btn" href="#/">New purchase request</a></div>`}
    </div>
    ${pastOrders()}`;
}

on("open", (el) => {
  location.hash = `#/orders/${encodeURIComponent(el.dataset.id)}`;
});

export function enter() {
  refresh();
  if (app.route.id) {
    trail.reader = "buyer";
    loadTrail();
  }
}
