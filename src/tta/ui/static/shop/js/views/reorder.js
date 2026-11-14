// "You usually order this": when a customer is opened or switched to, the gateway says what it ordered week after
// week (GET /shop/api/reorder) and the page shows it as a notification at the top of the request view, not a
// blocking dialog. "Order the same again" posts the gateway's request unchanged (assistant.js): the answer is an
// offer on a normal result card, prepared, and a person confirms it as always. "Not now" hides it until the
// customer is opened again. No answer, or no lines: no panel.
import { app, render } from "../core.js";
import { gateway } from "../api.js";
import { unitWord } from "../customer.js";
import { html, num, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { memory } from "../store.js";
import { plain } from "../words.js";

const lineOf = (line) => line && typeof line === "object" && line.product_id;

// Read for the customer being opened. Written into that customer's data, so a switch meanwhile cannot mix two.
export async function loadReorder() {
  const data = app.data;
  try {
    const answer = await gateway(memory.active).reorder();
    const lines = Array.isArray(answer?.lines) ? answer.lines.filter(lineOf) : [];
    data.reorder = lines.length && answer.request ? { ...answer, lines } : null;
  } catch {
    data.reorder = null; // no route yet, or no answer: the page offers nothing it cannot back
  }
  render();
}

export const reorderShown = () => (app.data.reorder && !app.data.reorderDismissed ? app.data.reorder : null);

function lineRow(line) {
  const counted = Number.isFinite(Number(line.orders_considered)) && Number(line.orders_considered) > 0
    ? ` · in ${line.orders_matching} of the last ${line.orders_considered} orders` : "";
  const last = line.last_ordered_on ? ` · last ${shortDate(line.last_ordered_on)}` : "";
  return html`<li><b>${line.name || "Product"} (${line.product_id})</b> × ${num(line.quantity)} ${unitWord(line.unit)}<span class="small muted">${counted}${last}</span></li>`;
}

export function reorderPanel() {
  const r = reorderShown();
  if (!r) return "";
  const whyNot = (Array.isArray(r.why_not) ? r.why_not : []).filter((w) => typeof w === "string" && w.trim());
  return html`<section class="reorder" role="status" aria-label="You usually order this">
    <div class="reorder-head">${icon("refresh")}<b>You usually order this</b>
      <button class="icon-btn reorder-x" data-act="reorder-hide" aria-label="Not now">${icon("x")}</button></div>
    ${r.sentence ? html`<p>${plain(r.sentence)}</p>` : ""}
    <ul class="reorder-lines">${r.lines.map(lineRow)}</ul>
    ${whyNot.length ? html`<details class="why"><summary>${icon("right")}Not in it, and why</summary><div class="why-body"><ul class="left-out">${whyNot.map((w) => html`<li>${plain(w)}</li>`)}</ul></div></details>` : ""}
    ${r.note ? html`<p class="tiny muted">${plain(r.note)}</p>` : ""}
    <div class="actions">
      <button class="btn small" data-act="reorder-go">Order the same again</button>
      <button class="btn small line" data-act="reorder-hide">Not now</button>
    </div>
    <p class="tiny muted">The click asks for an offer at today's prices and stock. Nothing is ordered until you confirm it.</p>
  </section>`;
}

export function hideReorder() {
  app.data.reorderDismissed = true;
  render();
}
