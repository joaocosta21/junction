// Valio Aimo back office: what the agent channel sold, what the suggestions brought, and which sales could not be
// made. It is Valio Aimo's screen of this demonstration, not the customer's: the gateway counts every figure from
// Valio Aimo's view of the audit trail of this browser's order books (GET /shop/api/backoffice, tta.api.insights),
// so a customer's limits, allergens, names and own words are not in it. The page computes nothing: each number and
// each sentence is the gateway's, shown in the page's own money and number format.
import { money, on, render } from "../core.js";
import { html, num } from "../dom.js";
import { icon } from "../icons.js";
import { active, memory } from "../store.js";

// Whose page this is, said where the header still names the customer chosen for the shop: the visitor is looking at
// it as Valio Aimo. It sits beside the customer's pages only because one visitor walks both sides of the demo.
const whose = () => `You are looking at this page as Valio Aimo, the wholesaler, not as ${active().name}, the customer chosen at the top of the page. It stands beside the customer's pages here so that one visitor can see both sides of the demonstration: a customer is never shown it.`;
// The shortfalls count the product asked for; what a substitute sold is in the orders above, not in these rows.
const OF_THE_PRODUCT_ASKED = "Each line counts confirmed stock of the product that was asked for. Where a substitute was offered in its place and a person accepted it, that sale is in “Sold through the agent” above, not in these lines.";
const UNITS = { L: "L", KG: "kg", UNIT: "units" };
const PERIODS = [["today", "Today"], ["all", "All time"]];
const state = { period: "today", data: null, error: null, loading: false, asked: 0 };

async function read(period) {
  let response;
  try {
    response = await fetch(`/shop/api/backoffice?period=${encodeURIComponent(period)}`, {
      headers: { "X-Shop-Request": "1", "X-Shop-Kitchen": memory.active },
      credentials: "same-origin",
    });
  } catch {
    throw new Error("The gateway could not be reached. Check that it is running.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || `The gateway answered ${response.status}.`);
  return body;
}

async function load() {
  const asked = ++state.asked;
  state.loading = true;
  state.error = null;
  render();
  try {
    const data = await read(state.period);
    if (asked !== state.asked) return; // a later click answered first
    state.data = data;
  } catch (error) {
    if (asked !== state.asked) return;
    state.error = error.message;
  }
  state.loading = false;
  render();
}

export const enter = load;
on("bo-period", (el) => {
  state.period = el.dataset.period;
  return load();
});
on("bo-refresh", load);

// ---- parts ----------------------------------------------------------------------------------------------------

const list = (value) => (Array.isArray(value) ? value.filter((x) => x && typeof x === "object") : []);
const unitWord = (code) => UNITS[code] || String(code || "").toLowerCase();
const euros = (value) => money(value ?? 0);

function tile(value, label, tone = "") {
  return html`<div class="bo-tile ${tone}"><b>${value}</b><span>${label}</span></div>`;
}

function counted(block) {
  const rows = list(block?.counted);
  if (!rows.length) return "";
  return html`<details class="why fold"><summary>${icon("right")}How is this counted?</summary>
    <div class="why-body"><dl class="bo-how">${rows.map((r) => html`<dt>${r.figure}</dt><dd>${r.how}</dd>`)}</dl></div></details>`;
}

function detail(label, body) {
  return html`<details class="why fold"><summary>${icon("right")}${label}</summary><div class="why-body">${body}</div></details>`;
}

function sold(demand) {
  const confirmed = Number(demand.confirmed_by_person) + Number(demand.placed_by_agent);
  const rows = [
    ["Requests received", demand.requests],
    ["Offers made", demand.offers],
    ["Orders prepared", demand.orders_prepared],
    ["Confirmed by a person", demand.confirmed_by_person],
    ["Placed by the agent alone", demand.placed_by_agent],
    ["Waiting for a person", demand.waiting],
    ["Rejected", demand.rejected],
    ["Expired", demand.expired],
  ];
  return html`<section class="card bo-block" aria-labelledby="bo-sold">
    <div class="card-title">${icon("chart")}<h2 id="bo-sold">Sold through the agent</h2></div>
    <div class="bo-tiles">
      ${tile(num(confirmed), confirmed === 1 ? "order confirmed" : "orders confirmed", "lead")}
      ${tile(euros(demand.confirmed_net_eur), "confirmed, before tax")}
      ${tile(euros(demand.waiting_net_eur), "waiting for a person")}
    </div>
    <p class="bo-say">${demand.sentence}</p>
    ${detail("Every step, from request to order", html`<div class="bo-scroll"><table class="table bo-table"><tbody>${rows.map(
      ([label, value]) => html`<tr><td>${label}</td><td class="num">${num(value)}</td></tr>`
    )}</tbody></table></div>`)}
    ${counted(demand)}
  </section>`;
}

function kindTable(found) {
  const rows = list(found.by_kind);
  if (!rows.length) return html`<p class="small muted">No suggestion was shown or accepted in this period.</p>`;
  return html`<div class="bo-scroll"><table class="table bo-table">
    <thead><tr><th>Kind</th><th class="num">Shown</th><th class="num">Accepted</th><th class="num">Ordered</th><th class="num">Added</th><th class="num">Saved for buyers</th></tr></thead>
    <tbody>${rows.map((r) => html`<tr class="${r.own ? "bo-own" : ""}">
      <td>${r.label}${r.own ? html` <span class="tag info">shown apart</span>` : ""}</td>
      <td class="num">${num(r.shown)}</td><td class="num">${num(r.accepted)}</td><td class="num">${num(r.ordered)}</td>
      <td class="num">${euros(r.added_net_eur)}</td><td class="num">${euros(r.saved_net_eur)}</td></tr>`)}</tbody>
  </table></div>
  <p class="small muted">${found.own_silent}</p>
  ${Number(found.not_valued) ? html`<p class="small muted">${num(found.not_valued)} accepted suggestion${Number(found.not_valued) === 1 ? "" : "s"} could not be valued from the two offers and count in neither amount.</p>` : ""}`;
}

function suggestions(found) {
  return html`<section class="card bo-block" aria-labelledby="bo-sug">
    <div class="card-title">${icon("tag")}<h2 id="bo-sug">Suggestions</h2></div>
    <div class="bo-flow" role="group" aria-label="Shown, accepted, ordered">
      ${tile(num(found.shown), "shown", "lead")}<span class="bo-arrow" aria-hidden="true">${icon("right")}</span>
      ${tile(num(found.accepted), "accepted")}<span class="bo-arrow" aria-hidden="true">${icon("right")}</span>
      ${tile(num(found.ordered), "ordered")}
    </div>
    <div class="bo-tiles two">
      ${tile(euros(found.added_net_eur), "added to baskets, before tax")}
      ${tile(euros(found.saved_net_eur), "saved for buyers", "good")}
    </div>
    <p class="bo-say">${found.sentence}</p>
    ${detail("By kind of suggestion", kindTable(found))}
    ${counted(found)}
  </section>`;
}

function shortfall(row) {
  const reasons = list(row.reasons);
  return html`<li><p>${row.sentence}</p>${reasons.length ? html`<p class="small muted">Why: ${reasons.map(
    (r, i) => html`${i ? "; " : ""}${num(r.products)} product${Number(r.products) === 1 ? "" : "s"} ${r.label}`
  )}.</p>` : ""}</li>`;
}

function topProducts(rows) {
  if (!rows.length) return html`<p class="small muted">No product that matched a request was left unconfirmed.</p>`;
  return html`<div class="bo-scroll"><table class="table bo-table">
    <thead><tr><th>Product</th><th class="num">Times</th><th>Reason</th></tr></thead>
    <tbody>${rows.map((r) => html`<tr><td>${r.name || "Product"} <span class="small muted">(${r.product_id})</span></td>
      <td class="num">${num(r.times)}</td><td>${r.reason_label}</td></tr>`)}</tbody></table></div>`;
}

function missed(found) {
  const totals = list(found.not_confirmed);
  const rows = list(found.shortfalls);
  const subs = found.substitutes || {};
  return html`<section class="card bo-block" aria-labelledby="bo-missed">
    <div class="card-title">${icon("alert")}<h2 id="bo-missed">Sales we could not make</h2></div>
    ${totals.length ? html`<div class="bo-tiles">
      ${totals.map((t, i) => tile(`${num(t.quantity)} ${unitWord(t.unit)}`, "asked for, not confirmed", i ? "" : "lead warn"))}
      ${tile(euros(found.value_net_eur), "at offered prices, before tax")}
    </div>` : ""}
    <p class="bo-say">${found.sentence}</p>
    ${rows.length ? html`<p class="small muted">${OF_THE_PRODUCT_ASKED}</p><ul class="bo-short">${rows.map(shortfall)}</ul>` : ""}
    ${Number(subs.offered) > 0 ? html`<p class="bo-say"><b>Sold as a substitute instead:</b> ${num(subs.accepted ?? 0)} order${Number(subs.accepted) === 1 ? "" : "s"} with a substitute confirmed by a person, of ${num(subs.offered ?? 0)} offered; ${num(subs.refused ?? 0)} refused.</p>` : ""}
    ${detail("Products most often asked for and not confirmed", topProducts(list(found.top_products)))}
    ${counted(found)}
  </section>`;
}

function body() {
  const data = state.data;
  if (state.error) {
    return html`<div class="verdict stop" role="alert">${icon("alert")}<div><b>The figures could not be read</b><p>${state.error}</p>
      <div class="actions"><button class="btn small dark" data-act="bo-refresh">Try again</button></div></div></div>`;
  }
  if (!data) return html`<div class="card empty"><p>Counting…</p></div>`;
  if (data.empty) {
    return html`<div class="card empty"><h3>Nothing to show yet</h3><p>${data.empty_sentence}</p>
      ${state.period === "today" ? html`<p class="small">Looking at today only. <button class="link" data-act="bo-period" data-period="all">Show all time</button></p>` : ""}
      <p><a class="btn small" href="#/">Make a request</a></p></div>`;
  }
  return html`${sold(data.demand || {})}${suggestions(data.suggestions || {})}${missed(data.missed || {})}`;
}

export function view() {
  const data = state.data;
  return html`
    <div class="page-head bo-head">
      <div><div class="crumbs">Valio Aimo · the wholesaler's side of the demonstration</div><h1>Valio Aimo's back office (demo)</h1><div class="sub">What the buying agents brought, and where sales were lost.</div></div>
      <div class="right bo-tools">
        <div class="seg" role="group" aria-label="Period">${PERIODS.map(
          ([id, label]) => html`<button class="${state.period === id ? "on" : ""}" data-act="bo-period" data-period="${id}" aria-pressed="${String(state.period === id)}">${label}</button>`
        )}</div>
        <button class="btn small line" data-act="bo-refresh" ${state.loading ? "disabled" : ""}>${icon("refresh")}${state.loading ? "Counting…" : "Count again"}</button>
      </div>
    </div>
    <div class="valio-view" role="status">${icon("shield")}<div><b>Valio Aimo's screen, not the customer's</b>
      <p>${whose()}</p>
      ${data ? html`<p>${data.note}</p><p class="small muted">${data.period_sentence} ${data.never_here}</p>` : ""}</div></div>
    ${body()}`;
}
