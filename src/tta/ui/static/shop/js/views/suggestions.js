// The box under an offer (P15 R4b): what the customer's past orders suggest, and Valio Aimo's own suggestion last
// and apart. Every word and figure is the gateway's: the sentence, the effect in money, the orders counted. "Add"
// (or "Switch", "Renew once at …": the button says what the request does) posts the suggestion's own request,
// unchanged, as a new request (assistant.js): the answer is a new offer on a new result, and nothing is added to
// this one. "Not now" hides a suggestion on this result only. What was not suggested, and why, comes from
// GET /shop/api/suggestions (the buyer's view).
import { api, on, render } from "../core.js";
import { unitWord } from "../customer.js";
import { html, money, num, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { mine, save } from "../store.js";
import { plain } from "../words.js";

const FROM_VALIO = "FROM_SUPPLIER"; // the brief's proactive selling agent: shown last and apart (P15 section 4.2)
const TREND = "QUANTITY_TREND";
const STANDING_ORDERS = "#/standing"; // this page's standing orders, with their trends
const findTurn = (id) => mine().thread.find((t) => t.id === id);

// ---- what was not suggested, read once per result --------------------------------------------------------------

export async function loadWhyNot(turn) {
  if (!turn.offer?.suggestions?.length || turn.whyNot) return;
  const gateway = api(); // the book of the customer that asked, even if the visitor switches meanwhile
  try {
    turn.whyNot = await gateway.suggestions(turn.offer.offer_id);
    turn.whyNotProblem = null;
  } catch (error) {
    turn.whyNotProblem = error.message || "The gateway did not answer.";
  }
  save();
  render();
}

on("suggest-hide", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (!turn) return;
  turn.notNow = [...new Set([...(turn.notNow || []), el.dataset.id])];
  save();
  render();
});
on("suggest-show", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (!turn) return;
  turn.notNow = [];
  save();
  render();
});

// ---- one suggestion --------------------------------------------------------------------------------------------

// "33,10 € more" or "42,00 € less", before tax: what accepting changes in money.
function effect(s) {
  const n = Number(s.effect?.net_change_eur);
  if (s.effect?.net_change_eur === null || s.effect?.net_change_eur === undefined || !Number.isFinite(n)) return "";
  if (n === 0) return html`<span class="tag">Same price</span>`;
  return n > 0
    ? html`<span class="tag wait">${money(n)} more, before tax</span>`
    : html`<span class="tag ok">${money(-n)} less, before tax</span>`;
}

// What it was counted from, in the evidence's own numbers.
function evidenceLine(e) {
  if (!e) return "";
  const span = e.first_order && e.last_order ? ` (${shortDate(e.first_order)} to ${shortDate(e.last_order)})` : "";
  const share = e.orders_matching > 0 ? `${e.orders_matching} of the` : "none of the";
  const counted = e.orders_considered > 0 ? `In ${share} ${e.orders_considered} past orders counted${span}.` : "";
  const source = {
    SYNTHETIC_HISTORY: "From a synthetic order history.",
    ORDER_BOOK: "From orders placed through this gateway.",
    CATALOG: "From the catalog and Valio Aimo's prices, not from past orders.",
    SUPPLIER: `Suggested by Valio Aimo from its catalog, not from your orders${e.synthetic ? " (the past orders counted are synthetic)" : ""}.`,
  }[e.source] || (e.synthetic ? "From a synthetic order history." : "");
  return [counted, source].filter(Boolean).join(" ");
}

function why(s) {
  const e = s.evidence || {};
  const values = Array.isArray(e.values) ? e.values : [];
  const checks = [...new Set(Array.isArray(s.checks) ? s.checks : [])];
  return html`<details class="why sugg-why"><summary>${icon("right")}Why?</summary>
    <div class="why-body">
      <p class="small">${evidenceLine(e)}</p>
      ${values.length ? html`<p class="small muted">The figures counted: ${values.map(num).join(", ")}.</p>` : ""}
      ${checks.length ? html`<ul class="why-list">${checks.map((c) => html`<li>${icon("check", "yes")}<span>${plain(c)}</span></li>`)}</ul>` : ""}
    </div>
  </details>`;
}

// The trend's sentence asks "Store 84 L?", but its request renews the standing order once, at that quantity, and the
// quantity the standing order stores does not change: the button says what it does, and links the standing orders.
const isTrend = (s) => s.kind === TREND || Boolean(s.standing_order_id);

// Each button says what its request does: a new line is added; a line of the request is switched to another product
// (a cheaper one with the same formula, a larger pack, the usual product) or to the usual quantity; a standing
// order is renewed once.
function addLabel(s) {
  const amount = `${num(s.quantity)} ${unitWord(s.unit)}`;
  if (isTrend(s)) return `Renew once at ${amount}`;
  if (s.request_line_index === null || s.request_line_index === undefined) return "Add";
  return s.kind === "USUAL_QUANTITY" ? `Use ${amount}` : "Switch";
}

function actions(turn, s) {
  const added = turn.added?.[s.suggestion_id];
  if (added) return html`<p class="small"><b>Sent as a new request:</b> its offer is the result above this one.</p>`;
  const label = addLabel(s);
  const add = s.accept_request
    ? html`<button class="btn small" data-act="suggest-add" data-turn="${turn.id}" data-id="${s.suggestion_id}">${label}</button>`
    : "";
  return html`<div class="actions">${add}<button class="btn small line" data-act="suggest-hide" data-turn="${turn.id}" data-id="${s.suggestion_id}">Not now</button>
    ${isTrend(s) ? html`<a class="link small" href="${STANDING_ORDERS}">Standing orders</a>` : ""}</div>
    ${isTrend(s) && add ? html`<p class="tiny muted">This renews the standing order once, as a new request: the quantity the standing order stores does not change.</p>` : ""}`;
}

function item(turn, s) {
  return html`<li class="sugg">
    <p>${plain(s.sentence)}</p>
    ${effect(s) ? html`<div class="sugg-meta">${effect(s)}</div>` : ""}
    ${why(s)}
    ${actions(turn, s)}
  </li>`;
}

// ---- the box ---------------------------------------------------------------------------------------------------

function whyNot(turn) {
  if (turn.whyNotProblem) return html`<p class="tiny muted">What was not suggested could not be read: ${plain(turn.whyNotProblem)}</p>`;
  const view = turn.whyNot;
  if (!view) return "";
  const rows = [...(view.dropped || []), ...(view.held_back || [])].filter((d) => d && typeof d === "object");
  const notes = (view.notes || []).filter(Boolean);
  if (!rows.length && !notes.length) return "";
  return html`<details class="why"><summary>${icon("right")}Not suggested, and why</summary>
    <div class="why-body">
      ${rows.length ? html`<ul class="left-out">${rows.map((d) => html`<li><b>${d.name || "Product"} (${d.product_id})</b>: ${plain(d.summary || d.sentence || "")}</li>`)}</ul>` : ""}
      ${notes.map((n) => html`<p class="small muted">${plain(n)}</p>`)}
    </div>
  </details>`;
}

// What the gateway's note says (a suggestion never adds itself to an order; its request is sent as a new one), in a
// person's words: the note itself names a field (`accept_request`), which is for developers.
const NEVER_ADDS_ITSELF = "Nothing is added to this order by itself: “Add” makes a new offer with it, which you confirm like any other.";

export function suggestionsBox(turn) {
  const all = (turn.offer?.suggestions || []).filter((s) => s && typeof s === "object" && s.suggestion_id);
  if (!all.length) return "";
  const hidden = new Set(turn.notNow || []);
  const shown = all.filter((s) => !hidden.has(s.suggestion_id));
  if (!shown.length) {
    return html`<section class="suggest"><p class="small muted">${all.length === 1 ? "The suggestion is" : `The ${all.length} suggestions are`} hidden for this result. <button class="link" data-act="suggest-show" data-turn="${turn.id}">Show again</button></p></section>`;
  }
  const buyer = shown.filter((s) => s.kind !== FROM_VALIO);
  const valio = shown.filter((s) => s.kind === FROM_VALIO);
  return html`<section class="suggest" aria-label="Suggestions">
    ${buyer.length ? html`<h4>${icon("memory")}Suggested from your past orders</h4><ul class="sugg-list">${buyer.map((s) => item(turn, s))}</ul>` : ""}
    ${valio.length ? html`<h4 class="apart">${icon("store")}Suggested by Valio Aimo, not from your orders</h4><ul class="sugg-list">${valio.map((s) => item(turn, s))}</ul>` : ""}
    ${whyNot(turn)}
    <p class="tiny muted">${NEVER_ADDS_ITSELF}</p>
  </section>`;
}
