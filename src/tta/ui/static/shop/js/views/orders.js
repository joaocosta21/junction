// Orders: everything this kitchen has ordered, and for each order the audit trail as the buyer or Valio sees it.
import { app, api, deliveryOf, on, refresh, render } from "../core.js";
import { html, longDate, money, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { active } from "../store.js";
import { plain } from "../words.js";
import { netTotal, optionBlock, problemBox, progress, ruleList, signers, spinner, statusTag } from "./parts.js";
import { trailView } from "./trail.js";

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

function detail(order) {
  const k = active();
  const approval = app.data.approvals.find((a) => a.order_id === order.order_id);
  const t = trail.data;
  return html`
    <div class="page-head">
      <div><div class="crumbs"><a href="#/orders">Orders</a> · ${order.order_id}</div><h1>${plain(order.option.summary)}</h1>
      <div class="sub">${statusTag(order)} ${deliveryOf(order.option) ? html`<span class="tag info">${icon("truck")}${longDate(deliveryOf(order.option))}</span>` : ""}</div></div>
    </div>
    <div class="grid">
      <section class="stack">
        <div class="card">
          <div class="card-title"><h3>What was ordered</h3></div>
          ${optionBlock(order.option)}
          <p class="small muted">${plain(order.status_sentence)}</p>
          ${approval && order.status === "PENDING_APPROVAL" ? html`<div class="decide">${signers(approval)}${progress(approval)}<div class="row"><a class="btn small" href="#/approvals">Go to approvals</a></div></div>` : ""}
        </div>
        <div class="card">
          <div class="card-title"><h3>Audit trail</h3>
            <div class="seg" role="tablist">
              <button class="${trail.reader === "buyer" ? "on" : ""}" data-act="reader" data-reader="buyer">${k.name}</button>
              <button class="${trail.reader === "supplier" ? "on" : ""}" data-act="reader" data-reader="supplier">What Valio Aimo sees</button>
            </div>
          </div>
          ${trail.loading ? spinner("Reading the trail…") : ""}
          ${trail.problem ? problemBox(trail.problem) : ""}
          ${t && !trail.loading ? trailView(t, trail.reader) : ""}
        </div>
      </section>
      <aside class="side">
        <div class="card">
          <div class="card-title"><h3>Rules that applied</h3></div>
          ${ruleList(order.decision?.fired)}
          ${order.decision?.policy_hash ? html`<p class="small muted">Policy fingerprint <span class="rule-id">${String(order.decision.policy_hash).slice(7, 19)}</span> is stored with the order, so anyone can tell later which rules decided.</p>` : ""}
        </div>
        <div class="card">
          <div class="card-title"><h3>What the order relied on</h3></div>
          <ul class="side-list">${(order.reliance || []).map(
            (r) => html`<li><span><b>${r.product_id}</b> · ${money(r.unit_net_price)} · ${String(r.availability_state).toLowerCase().replaceAll("_", " ")}<br><span class="small muted">${r.rechecked_at ? `checked again ${shortDate(r.rechecked_at)} ${String(r.rechecked_at).slice(11, 16)}` : ""}${r.closing_time ? ` · closing time ${shortDate(r.closing_time)} ${String(r.closing_time).slice(11, 16)}` : ""} · ${r.source === "replay" ? "recorded data" : "live data"}</span></span></li>`
          )}</ul>
          <p class="small muted">${order.record_note}</p>
        </div>
      </aside>
    </div>`;
}

function pastOrders() {
  const k = active();
  return html`<p class="section-label">Earlier orders · demo history</p>
    <div class="card"><table class="table"><thead><tr><th>Delivery</th><th>Products</th><th class="num">Total</th><th class="hide-s">Status</th></tr></thead><tbody>
    ${k.history.map(
      (h) => html`<tr><td class="nowrap">${shortDate(h.date)}</td><td>${h.lines.map((l) => html`<div>${l[0]} <span class="muted">× ${l[1]} ${l[2]}</span></div>`)}</td><td class="num">${money(h.lines.reduce((s, l) => s + l[3], 0))}</td><td class="hide-s"><span class="tag">Delivered</span></td></tr>`
    )}
    </tbody></table><p class="small muted">Made-up history for the demo: it is what the agent's "learned" notes refer to.</p></div>`;
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
