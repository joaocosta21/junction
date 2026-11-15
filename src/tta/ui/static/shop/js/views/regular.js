// "This is one of your regular orders": a bar at the top of a result, above its options, when what was asked for
// repeats what this customer orders regularly. Every word and figure is the gateway's, computed from the customer's
// past orders and standing orders (GET /shop/api/regular?offer_id=…), read once per result:
//   - a product is already on a standing order (amber): the request would be on top of it. "See the standing order".
//   - the request is regular and on no standing order (neutral): "Make it a standing order" posts the gateway's own
//     set-up body (POST /shop/api/standing-orders); that orders nothing, and each renewal is an offer a person confirms.
//   - a regular product at a clearly different quantity (amber): "Yes, 90 L is right" dismisses the bar; "Use my usual
//     30 L" sends the gateway's request at the usual quantity as a new request (assistant.js), with a result of its own.
// No finding, an answer the page cannot read, or a failed fetch: nothing is shown. Nothing here orders anything.
import { on, render } from "../core.js";
import { unitWord } from "../customer.js";
import { html, num } from "../dom.js";
import { icon } from "../icons.js";
import { memory, mine, save } from "../store.js";
import { plain } from "../words.js";
import { sendAsWritten } from "./assistant.js";

const BASE = "/shop/api";
const STANDING_ORDERS = "#/standing";
const ON_STANDING = "ALREADY_ON_STANDING_ORDER";
const NOT_STANDING = "REGULAR_NOT_STANDING";
const DIFFERENT = "REGULAR_DIFFERENT_QUANTITY";
const FINDINGS = [ON_STANDING, NOT_STANDING, DIFFERENT];
const AMBER = [ON_STANDING, DIFFERENT];
const NOT_SET_UP = "The standing order was not set up.";
const SENT_AT_USUAL = "Sent as a new request at your usual quantity: its offer is the result above this one.";

const isObject = (x) => Boolean(x) && typeof x === "object";
const findTurn = (id) => mine().thread.find((t) => t.id === id);
// Results being read or acted on now, and those whose read failed (not asked again until the page is loaded again).
const reading = new Set();
const failed = new Set();
const busy = new Set();

// The shop's own calls, as api.js makes them: the same two headers, the customer's own book.
async function call(kitchen, method, path, body) {
  const headers = { "X-Shop-Request": "1", "X-Shop-Kitchen": kitchen };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(BASE + path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) throw new Error(isObject(data) && typeof data.detail === "string" ? data.detail : "");
  return data;
}

// The answer as the bar needs it, or null for one with no finding or one the page cannot read.
function finding(answer) {
  if (!isObject(answer) || !FINDINGS.includes(answer.finding)) return null;
  if (typeof answer.sentence !== "string" || !answer.sentence.trim()) return null;
  return {
    finding: answer.finding,
    sentence: answer.sentence,
    lines: (Array.isArray(answer.lines) ? answer.lines : []).filter(isObject),
    standingOrderRequest: isObject(answer.standing_order_request) ? answer.standing_order_request : null,
    usualRequest: isObject(answer.usual_request) ? answer.usual_request : null,
  };
}

// Read once per result, for the customer that asked. A failure shows nothing and is not stored.
async function load(turn) {
  const offerId = turn.offer?.offer_id;
  if (!offerId || reading.has(turn.id) || failed.has(turn.id)) return;
  reading.add(turn.id);
  const kitchen = memory.active;
  try {
    const answer = await call(kitchen, "GET", `/regular?offer_id=${encodeURIComponent(offerId)}`);
    turn.regular = finding(answer);
    save();
  } catch {
    failed.add(turn.id);
  }
  reading.delete(turn.id);
  render();
}

function settle(turn, state) {
  turn.regularState = state;
  save();
  render();
}

on("regular-hide", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (turn) settle(turn, { hidden: true });
});

on("regular-make", async (el) => {
  const turn = findTurn(el.dataset.turn);
  const body = turn?.regular?.standingOrderRequest;
  if (!body || busy.has(turn.id) || turn.regularState?.done) return;
  busy.add(turn.id);
  render();
  try {
    const made = await call(memory.active, "POST", "/standing-orders", body);
    const said = isObject(made) && typeof made.sentence === "string" && made.sentence.trim() ? made.sentence : "Set up as a standing order. Nothing is ordered by this: each renewal is an offer you confirm.";
    busy.delete(turn.id);
    settle(turn, { done: said, standing: true });
  } catch (error) {
    busy.delete(turn.id);
    settle(turn, { problem: [NOT_SET_UP, error?.message || ""].filter(Boolean).join(" ") });
  }
});

on("regular-usual", async (el) => {
  const turn = findTurn(el.dataset.turn);
  const request = turn?.regular?.usualRequest;
  if (!request || busy.has(turn.id) || turn.regularState?.done) return;
  settle(turn, { done: SENT_AT_USUAL });
  return sendAsWritten("reorder", turn.text || "At your usual quantity", request, { replaces: turn.id });
});

// ---- the bar ---------------------------------------------------------------------------------------------------

const amount = (quantity, unit) => `${num(quantity)} ${unitWord(unit)}`;
// The lines asked for at a clearly different quantity than the usual one.
const different = (r) => r.lines.filter((l) => ["MORE", "LESS"].includes(l.comparison) && Number.isFinite(Number(l.quantity)) && Number.isFinite(Number(l.usual_quantity)));

function buttons(turn, r) {
  const id = turn.id;
  const waiting = busy.has(id) ? "disabled" : "";
  if (r.finding === ON_STANDING) return html`<a class="btn small line" href="${STANDING_ORDERS}">See the standing order</a>`;
  if (r.finding === NOT_STANDING) {
    return html`${r.standingOrderRequest ? html`<button class="btn small" data-act="regular-make" data-turn="${id}" ${waiting}>${busy.has(id) ? "Setting up…" : "Make it a standing order"}</button>` : ""}
      <button class="btn small line" data-act="regular-hide" data-turn="${id}" ${waiting}>Not now</button>`;
  }
  const lines = different(r);
  const one = lines.length === 1 ? lines[0] : null;
  const yes = one ? `Yes, ${amount(one.quantity, one.unit)} is right` : "Yes, these quantities are right";
  const usual = one ? `Use my usual ${amount(one.usual_quantity, one.unit)}` : "Use my usual quantities";
  return html`<button class="btn small line" data-act="regular-hide" data-turn="${id}">${yes}</button>
    ${r.usualRequest ? html`<button class="btn small" data-act="regular-usual" data-turn="${id}">${usual}</button>` : ""}`;
}

// The bar of one result; empty when there is nothing to say. The first call for a result starts its one read.
export function regularBar(turn) {
  if (!turn?.offer?.offer_id || turn.superseded) return "";
  if (turn.regular === undefined) {
    load(turn);
    return "";
  }
  const r = turn.regular;
  const state = turn.regularState || {};
  if (!r || !FINDINGS.includes(r.finding) || state.hidden) return "";
  if (state.done) {
    return html`<div class="regular-bar done" role="status">${icon("checkCircle")}<div><p>${plain(state.done)}</p>
      ${state.standing ? html`<div class="actions"><a class="btn small line" href="${STANDING_ORDERS}">See the standing orders</a></div>` : ""}</div></div>`;
  }
  const amber = AMBER.includes(r.finding);
  return html`<div class="regular-bar ${amber ? "amber" : ""}" role="status" aria-label="One of your regular orders">${icon(amber ? "alert" : "refresh")}<div>
    <p>${plain(r.sentence)}</p>
    ${state.problem ? html`<p class="small"><b>${plain(state.problem)}</b></p>` : ""}
    <div class="actions">${buttons(turn, r)}</div>
  </div></div>`;
}
