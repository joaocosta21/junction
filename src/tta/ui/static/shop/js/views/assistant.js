// The request page: the buyer writes what is needed, the gateway reads it into a typed request and answers with
// an offer, and nothing is ordered until the buyer clicks "Confirm order". Not a chat: each result is one typed
// request and its answer, newest first. The agent orders alone only where the buyer switched that on.
import { app, api, deliveryOf, on, refresh, render, toast, verifyRules, withRules } from "../core.js";
import { contact, customerKnown, customerOf, loadCustomer, myRoles } from "../customer.js";
import { clock, html, longDate, num, unit } from "../dom.js";
import { ROLES, allergenName } from "../kitchens.js";
import { icon } from "../icons.js";
import { confirm, dismiss, prepare, review } from "../learning.js";
import { active, mine, save } from "../store.js";
import { plain } from "../words.js";
import { exclusionsSummary, flagBox, whyBlock } from "./answer-parts.js";
import { confirmedBy as confirmedOn, hasPerson, netTotal, nobodyHolds, optionBlock, personFor, problemBox, rolesStillNeeded, signerName, spinner, substituteNote } from "./parts.js";
import { failedAnswer, forPeople, problemOf } from "./refusal.js";
import { hideReorder, reorderPanel, reorderShown } from "./reorder.js";
import { side } from "./side.js";
import { loadWhyNot, suggestionsBox } from "./suggestions.js";
import { openInterface, typedRequest } from "./typed.js";

const SOURCES = {
  model: "read by Gemini",
  recording: "read from a recorded Gemini answer",
  "hand-built": "read from a hand-written answer",
  "rule-based": "read by fixed rules, no model",
  example: "example, sent as a typed request",
  suggestion: "a suggestion you added, sent as its own typed request",
  reorder: "what you usually order, sent as the gateway wrote it",
  standing: "a standing order renewed once, sent as the gateway wrote it",
};
const CONFIRM_NOTE = "Confirmed on the shop's request page.";

const findTurn = (id) => mine().thread.find((t) => t.id === id);
const chosenOf = (turn) => turn.offer?.options?.find((o) => o.option_id === turn.chosen) || turn.offer?.options?.[0];
const isFirst = (turn, option) => Boolean(option) && option === turn.offer?.options?.[0];
// The order of a result as the gateway has it now, so an order confirmed on the Approvals page shows here too.
const orderOf = (turn) => (turn.order ? app.data.orders.find((o) => o.order_id === turn.order.order_id) || turn.order : null);
const roleName = (role) => (ROLES[role] || role).toLowerCase();
// "Hanna Laine (purchasing manager)"; the role alone while the customer route has not named anybody.
const names = (roles) => roles.map((r) => (hasPerson(r) ? `${personFor(r)} (${roleName(r)})` : `the ${roleName(r)}`)).join(" and ");

function update(turn) {
  save();
  render();
  return turn;
}

// ---- asking -----------------------------------------------------------------------------------------------

// A reading that holds no typed request: the reader's own sentence and question, if it gave one.
function unread(reading) {
  const error = new Error(reading?.sentence || "");
  error.status = null;
  error.problem = reading || {};
  return error;
}

async function ask(text, typed = null) {
  text = text.trim();
  if (!text) return;
  const k = active();
  const turn = { id: `t${Date.now().toString(36)}`, text, at: new Date().toISOString(), phase: "reading" };
  mine().thread.push(turn);
  app.ui.draft = "";
  update(turn);
  let step = "rules";
  try {
    await verifyRules(); // never ask under rules the gateway has not confirmed
    step = "reading";
    let request;
    if (typed) {
      request = structuredClone(typed);
      turn.reading = { source: "example" };
    } else {
      const reading = await withRules(() => api().read(text));
      if (!reading?.request?.lines?.length) throw unread(reading);
      request = reading.request;
      turn.reading = { source: reading.source, sentence: reading.sentence };
    }
    step = "offer";
    const prepared = prepare(request, k, mine(), app.data.authority?.profile);
    turn.applied = prepared.applied;
    turn.sent = prepared.request;
    await answerWith(turn, prepared.request);
  } catch (error) {
    turn.phase = "failed";
    turn.problem = problemOf(error, step);
    update(turn);
  }
}

// The offer for a typed request, then what it suggests and does not, then the one order placed without a click.
async function answerWith(turn, request) {
  turn.phase = "looking";
  update(turn);
  turn.offer = await withRules(() => api().offer(request));
  turn.flags = review(turn.offer, mine());
  turn.phase = "done";
  update(turn);
  loadWhyNot(turn);
  await act(turn);
}

// A request the gateway wrote (a suggestion's, "you usually order this", a standing order's renewal), sent unchanged
// as a new request with a result of its own: the gateway knows it again (a suggestion's names the suggestion it
// accepts, so the acceptance is recorded). The answer is an offer like any other; nothing is ordered by the click.
export async function sendAsWritten(source, text, request, extra = {}) {
  const turn = { id: `t${Date.now().toString(36)}`, text, at: new Date().toISOString(), phase: "looking", reading: { source }, sent: request, ...extra };
  mine().thread.push(turn);
  update(turn);
  toast("Sent as a new request: its offer is the first result.");
  let step = "rules";
  try {
    await verifyRules(); // never ask under rules the gateway has not confirmed
    step = "offer";
    await answerWith(turn, request);
  } catch (error) {
    turn.phase = "failed";
    turn.problem = problemOf(error, step);
    update(turn);
  }
  return turn;
}

// "Add": the suggestion's own request. Nothing is added to the offer that showed it.
function accept(suggestion, from = null) {
  if (from) from.added = { ...(from.added || {}), [suggestion.suggestion_id]: true };
  return sendAsWritten("suggestion", suggestion.name, suggestion.accept_request, { suggestion });
}

// The only order placed without a click: the buyer switched ordering alone on (a setting, off in every shipped
// profile), the gateway confirms that setting is in force, and its decision is that the agent may order alone
// (every statement confirmed, no rule asks for a person). Everything else waits for "Confirm order".
async function act(turn) {
  const first = turn.offer?.options?.[0];
  if (!first || turn.order || turn.flags?.length) return;
  const alone = app.data.authority?.profile?.auto_order_enabled === true;
  if (alone && first.decision?.verdict === "AUTO") await place(turn, first.option_id, false);
}

// The signed-in person signs each role the order still needs that they hold: their click is the confirmation.
async function signMine(turn) {
  const order = turn.order;
  if (order?.status !== "PENDING_APPROVAL" || !order.approval_id) return;
  const approval = app.data.approvals.find((a) => a.approval_id === order.approval_id);
  const needed = approval ? rolesStillNeeded(approval) : order.decision?.required_roles || [];
  for (const role of needed.filter((r) => myRoles().includes(r))) {
    turn.order = await api().decide(order.approval_id, role, "APPROVE", CONFIRM_NOTE, signerName(role));
    turn.confirmedBy = [...(turn.confirmedBy || []), { name: personFor(role), role }];
    update(turn);
  }
}

async function place(turn, optionId, sign) {
  turn.busy = true;
  turn.problem = null;
  update(turn);
  try {
    const key = `shop.${active().id}.${turn.offer.offer_id}.${optionId}`;
    if (sign) await loadCustomer(); // who signs is the customer file's person, never a name the page made up
    await verifyRules(); // the order is judged again when placed, under the rules in force then
    turn.order = await withRules(() => api().order(turn.offer.offer_id, optionId, key));
    if (sign) await signMine(turn);
  } catch (error) {
    turn.problem = problemOf(error, "order");
  }
  turn.busy = false;
  update(turn);
  await refresh();
}

async function signPending(turn) {
  turn.busy = true;
  turn.problem = null;
  update(turn);
  try {
    await signMine(turn);
  } catch (error) {
    turn.problem = problemOf(error, "order");
  }
  turn.busy = false;
  update(turn);
  await refresh();
}

function askAgain(turn, text) {
  mine().thread = mine().thread.filter((t) => t !== turn);
  delete app.ui.redraft[turn.id];
  if (turn.reading?.source === "suggestion" && turn.suggestion) return accept(turn.suggestion);
  if (["reorder", "standing"].includes(turn.reading?.source) && turn.sent) return sendAsWritten(turn.reading.source, turn.text, turn.sent);
  const example = active().examples.find((e) => e.text === text);
  return ask(text, example?.request || null);
}

on("ask", (form) => ask(form.elements.text.value));
on("reorder-hide", () => hideReorder());
on("reorder-go", () => {
  const r = reorderShown();
  if (!r?.request) return;
  hideReorder();
  return sendAsWritten("reorder", "Order the same again", r.request);
});
on("suggest-add", (el) => {
  const from = findTurn(el.dataset.turn);
  const suggestion = from?.offer?.suggestions?.find((s) => s.suggestion_id === el.dataset.id);
  if (!suggestion?.accept_request || from.added?.[suggestion.suggestion_id]) return;
  return accept(suggestion, from);
});
on("example", (el) => {
  const example = active().examples[Number(el.dataset.i)];
  return ask(example.text, example.request);
});
on("draft", (el) => {
  app.ui.draft = el.value;
});
on("redraft", (el) => {
  app.ui.redraft[el.dataset.turn] = el.value;
});
on("confirm", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (turn && !turn.busy && !turn.order) return place(turn, el.dataset.option, true);
});
on("sign", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (turn && !turn.busy) return signPending(turn);
});
on("choose", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (!turn || turn.order) return;
  turn.chosen = el.dataset.option;
  turn.problem = null;
  update(turn);
});
on("retry", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (turn) return askAgain(turn, turn.text);
});
on("reask", (form) => {
  const turn = findTurn(form.dataset.turn);
  if (turn) return askAgain(turn, form.elements.text.value);
});
on("flag-yes", async (el) => {
  const turn = findTurn(el.dataset.turn);
  confirm(mine(), el.dataset.rule);
  turn.flags = turn.flags.filter((f) => f.ruleId !== el.dataset.rule);
  turn.resolved = `${el.dataset.brand} only from now on. Asking again with that.`;
  turn.superseded = true;
  update(turn);
  const example = active().examples.find((e) => e.text === turn.text);
  return ask(turn.text, example?.request || turn.offer.request);
});
on("flag-no", async (el) => {
  const turn = findTurn(el.dataset.turn);
  dismiss(mine(), el.dataset.rule);
  turn.flags = turn.flags.filter((f) => f.ruleId !== el.dataset.rule);
  turn.resolved = "Noted: other brands are fine for this kitchen.";
  update(turn);
  await act(turn);
});
on("clear", () => {
  mine().thread = [];
  save();
  render();
});

// ---- line 1: what was asked -------------------------------------------------------------------------------

function readAs(request) {
  const parts = (request?.lines || []).map((l) => {
    const terms = (l.name_terms || []).join(" ");
    const type = l.product_type ? l.product_type.replaceAll("_", " ") : "";
    const what = l.product_ids?.length ? `product ${l.product_ids.join(", ")}` : [terms, type].filter(Boolean).join(" ") || "products";
    const claims = (l.required_claims || []).map((c) => c.replace(/^FREE_FROM_/, "").toLowerCase().replaceAll("_", " ") + "-free").join(", ");
    const without = (l.exclude_allergens || []).map((c) => allergenName(c).toLowerCase()).join(", ");
    return `${num(l.quantity)} ${unit(l.unit)} ${claims ? claims + " " : ""}${what}${without ? `, without ${without}` : ""}`;
  });
  return `${parts.join(" + ")}${request?.needed_by ? `, by ${longDate(request.needed_by)}` : ""}`;
}

function asked(turn) {
  const request = turn.offer?.request || turn.sent;
  const wrote = ["example", "suggestion", "reorder", "standing"].includes(turn.reading?.source) ? "" : `You wrote “${turn.text}”`;
  const data = turn.offer ? (turn.offer.source === "replay" ? "recorded Valio Aimo data" : "live Valio Aimo data") : "";
  const meta = [request ? wrote : "", SOURCES[turn.reading?.source], data, turn.at ? clock(turn.at) : ""].filter(Boolean).join(" · ");
  // What the reading itself says a person should know, e.g. "No allergen rule was given for …: read as strict,
  // the safe reading." Sentences about keys or routes are for developers and stay out (forPeople).
  const reading = turn.reading?.sentence ? forPeople(turn.reading.sentence) : [];
  return html`<div class="asked">
    <span class="label">Asked</span>
    <div class="read">
      <b>${request ? readAs(request) : turn.text}</b>
      ${meta ? html`<div class="small muted">${meta}</div>` : ""}
      ${reading.length ? html`<p class="reading-note small">${icon("info")}<span>${reading.join(" ")}</span></p>` : ""}
      ${turn.applied?.length ? html`<div class="applied">${turn.applied.map((a) => html`<span class="tag ${a.tone}">${a.text}</span>`)}</div>` : ""}
    </div>
  </div>`;
}

// ---- line 3: what needs a person, and why, next to the outcome --------------------------------------------

const CANNOT_ALONE = /^The agent cannot place this order alone:\s*/;
const IT_NEEDS = /\s*It needs [^.]*\.\s*$/;
// The decision's sentence without what the box already says in its heading.
const why = (sentence) => plain(sentence).replace(/^Prepared: confirm to order\.?\s*/i, "");

function needsLine(roles, sentence) {
  const text = why(sentence);
  if (roles.length && CANNOT_ALONE.test(text)) return `Needs ${names(roles)}: ${text.replace(CANNOT_ALONE, "").replace(IT_NEEDS, "").replace(/\.$/, "")}.`;
  return [roles.length ? `Needs ${names(roles)}.` : "", text].filter(Boolean).join(" ");
}

// "Confirmed by Marko Heikkinen (purchasing manager, finance)": one name once, with every role it signed. From the
// gateway's record of the approval while it waits (a person may have signed on the Approvals page), else from
// the signatures given on this page.
function confirmedBy(turn, approval = null) {
  const byName = new Map();
  for (const c of turn.confirmedBy || []) byName.set(c.name, [...(byName.get(c.name) || []), roleName(c.role)]);
  const signed = approval ? confirmedOn(approval) : [...byName];
  if (!signed.length) return "Confirmed";
  return `Confirmed by ${signed.map(([name, roles]) => `${name} (${roles.join(", ")})`).join(" and ")}`;
}

function orderBox(turn, order) {
  const delivery = deliveryOf(order.option);
  const when = delivery ? ` · delivery ${longDate(delivery)}` : "";
  const trail = html`<a class="link" href="#/orders/${order.order_id}">Order and audit trail</a>`;
  if (order.status === "ORDERED") {
    const alone = order.placed_by === "AGENT";
    // Names only when this page saw every role sign; else the gateway's sentence below names who approved.
    const required = order.decision?.required_roles || [];
    const seenAll = required.every((r) => (turn.confirmedBy || []).some((c) => c.role === r));
    return html`<div class="verdict ok">${icon("checkCircle")}<div><b>${alone ? "Ordered by your agent" : seenAll ? confirmedBy(turn) : "Confirmed"}${when}</b>
      <p>${plain(order.status_sentence)}</p>
      ${alone ? html`<p class="small">You let the agent order alone in Settings. It does so only when every statement is confirmed and no rule asks for a person.</p>` : ""}
      <div class="actions">${trail}</div></div></div>`;
  }
  if (order.status === "PENDING_APPROVAL") {
    const approval = app.data.approvals.find((a) => a.order_id === order.order_id);
    const needed = approval ? rolesStillNeeded(approval) : order.decision?.required_roles || [];
    const canSign = needed.some((r) => myRoles().includes(r));
    const waitingFor = needed.length ? `waiting for ${names(needed)}` : "waiting for approval";
    const signed = approval ? confirmedOn(approval).length > 0 : Boolean(turn.confirmedBy?.length);
    const head = signed ? `${confirmedBy(turn, approval)}; ${waitingFor}` : waitingFor[0].toUpperCase() + waitingFor.slice(1);
    return html`<div class="verdict wait">${icon("clock")}<div><b>${head}</b><p>${plain(order.status_sentence)}</p>
      <div class="actions">${canSign ? html`<button class="btn small" data-act="sign" data-turn="${turn.id}" ${turn.busy ? "disabled" : ""}>Confirm order</button>` : ""}<a class="btn small line" href="#/approvals">Open approvals</a>${trail}</div></div></div>`;
  }
  return html`<div class="verdict stop">${icon("stop")}<div><b>${order.status === "REJECTED" ? "Rejected: nothing was ordered" : "Expired: nothing was ordered"}</b><p>${plain(order.status_sentence)}</p></div></div>`;
}

function verdictBox(turn, option) {
  const order = orderOf(turn);
  if (order) return orderBox(turn, order);
  if (turn.superseded) return "";
  const d = option.decision || {};
  const button = html`<button class="btn small" data-act="confirm" data-turn="${turn.id}" data-option="${option.option_id}" ${turn.busy ? "disabled" : ""}>Confirm order</button>`;
  if (d.verdict === "BLOCK") {
    return html`<div class="verdict stop">${icon("stop")}<div><b>This cannot be ordered, not even with approval</b><p>${plain(d.sentence)}</p></div></div>`;
  }
  if (turn.flags?.length && isFirst(turn, option)) {
    return html`<div class="verdict info">${icon("info")}<div><b>Waiting for your answer before ordering</b><p>${d.verdict === "AUTO" ? "Your agent could order this alone, but the brand question below comes first." : why(d.sentence)}</p></div></div>`;
  }
  if (d.verdict === "AUTO") {
    return html`<div class="verdict ok">${icon("checkCircle")}<div><b>Your agent may order this alone</b><p>${why(d.sentence)}</p><div class="actions">${button}</div></div></div>`;
  }
  const needed = d.required_roles || [];
  // A role nobody of this customer holds: no button the gateway would refuse later. Said only once the customer
  // route has answered; before, the page knows nobody and claims nothing.
  const unheld = customerKnown() ? needed.filter((r) => !hasPerson(r)) : [];
  if (unheld.length) {
    return html`<div class="verdict stop">${icon("stop")}<div><b>Nobody here can confirm this option</b>
      <p>${unheld.map(nobodyHolds).join(" ")} ${why(d.sentence)}</p>
      <p class="small">Nothing is ordered. Choose another option below, or ask again without it.</p>
    </div></div>`;
  }
  const others = needed.filter((r) => !myRoles().includes(r));
  const after = !others.length ? "" : others.length === needed.length ? `Your confirmation sends it to ${names(others)}, who signs it.` : `After you confirm, it also needs ${names(others)}.`;
  return html`<div class="verdict wait">${icon("clock")}<div><b>Prepared: confirm to order</b>
    <p>${needsLine(needed, d.sentence)}</p>
    <div class="actions">${button}</div>
    ${after ? html`<p class="small">${after}</p>` : ""}
  </div></div>`;
}

// ---- the result card ---------------------------------------------------------------------------------------

function verdictTag(option) {
  const v = option.decision?.verdict;
  if (v === "AUTO") return html`<span class="tag ok">Agent may order alone</span>`;
  if (v === "BLOCK") return html`<span class="tag stop">Cannot be ordered</span>`;
  return html`<span class="tag wait">Needs a person</span>`;
}

function others(turn, chosen) {
  const rest = (turn.offer.options || []).filter((o) => o !== chosen);
  if (!rest.length || !mine().prefs.alternatives) return "";
  const locked = Boolean(turn.order) || Boolean(turn.superseded);
  return html`<div class="others"><h4>Alternative products</h4>${rest.map(
    (o) => html`<div class="other">
      <div class="what"><b>${plain(o.title)}</b> · ${netTotal(o.totals)}<div class="small muted">${plain(o.summary)}</div>${o.lines.map((l) => substituteNote(l, { table: false }))}</div>
      ${verdictTag(o)}
      ${locked || o.decision?.verdict === "BLOCK" ? "" : html`<button class="btn small line" data-act="choose" data-turn="${turn.id}" data-option="${o.option_id}">Choose</button>`}
    </div>`
  )}</div>`;
}

const card = (turn, body) => html`<article class="answer">${asked(turn)}${body}</article>`;

function nothingOffered(turn) {
  const offer = turn.offer;
  return html`<div class="answer-body">
    <div class="verdict stop">${icon("stop")}<div><b>Nothing can be offered for this request</b><p>Looked at ${offer.candidates_considered ?? 0} products: ${exclusionsSummary(offer) || "none matched"}.</p>${(offer.notes || []).map((n) => html`<p>${plain(n)}</p>`)}</div></div>
    ${suggestionsBox(turn)}
    ${typedRequest(turn)}
  </div>`;
}

function answer(turn) {
  const prefs = mine().prefs;
  if (turn.phase === "reading") return card(turn, spinner(turn.reading?.source === "example" ? "Sending the typed request…" : "Reading the text into a typed request…"));
  if (turn.phase === "looking") return card(turn, spinner("Checking price and availability with Valio Aimo…"));
  if (turn.phase === "failed") return card(turn, html`<div class="answer-body">${failedAnswer(turn)}</div>`);
  const option = chosenOf(turn);
  if (!option) return card(turn, nothingOffered(turn));
  const first = isFirst(turn, option);
  return card(turn, html`<div class="answer-body">
    <div class="label-row"><span class="label">Suggested</span><span class="small muted">${plain(option.title)}</span></div>
    <p class="headline">${plain(option.summary)}</p>
    ${optionBlock(option, prefs.short)}
    ${turn.resolved ? html`<p class="small muted">${turn.resolved}</p>` : ""}
    ${first ? (turn.flags || []).map((f) => flagBox(turn, f)) : ""}
    ${verdictBox(turn, option)}
    ${turn.problem ? html`${problemBox(turn.problem)}<div class="actions"><button class="btn small line" data-act="retry" data-turn="${turn.id}">Ask again</button></div>` : ""}
    ${others(turn, option)}
    ${turn.superseded ? "" : suggestionsBox(turn)}
    ${prefs.short && !prefs.explain ? "" : whyBlock(turn.offer, option, prefs.explain)}
    ${typedRequest(turn)}
  </div>`);
}

// ---- view --------------------------------------------------------------------------------------------------

export function view() {
  const k = active();
  const c = customerOf();
  const me = contact();
  const results = mine().thread;
  return html`
    <div class="page-head">
      <div><div class="crumbs">${[k.name, c?.customer_number ? `customer ${c.customer_number}` : "", c?.address].filter(Boolean).join(" · ")}</div><h1>Purchase request</h1>
        <div class="sub">${me ? `Signed in as ${me.name}, ${me.title.toLowerCase()}. ` : ""}Nothing is ordered until you confirm it.</div></div>
      ${results.length ? html`<div class="right"><button class="link quiet" data-act="clear">Clear results</button></div>` : ""}
    </div>
    ${app.data.problem ? problemBox(app.data.problem) : ""}
    ${reorderPanel()}
    <div class="grid">
      <section>
        <div class="ask">
          <h2>What is needed, how much, and by when</h2>
          <p>The text is read into a typed request: product, quantity, unit, date and allergens. The agent checks price and availability with Valio Aimo and prepares the order for you to confirm.</p>
          <form data-act="ask">
            <label class="sr" for="ask-text">Request</label>
            <textarea id="ask-text" name="text" rows="2" data-send data-input="draft" placeholder="e.g. 40 litres of lactose-free milk by Monday">${app.ui.draft || ""}</textarea>
            <button class="btn" type="submit">Check price and stock</button>
          </form>
          <div class="examples"><span>Examples:</span>${k.examples.map((e, i) => html`<button class="chip" data-act="example" data-i="${i}">${e.text}</button>`)}</div>
          ${openInterface()}
        </div>
        <div class="results">
          ${results.length
            ? results.slice().reverse().map(answer)
            : html`<div class="card empty"><h3>No requests yet</h3><p>Write one above, or start from an example: examples are sent as typed requests.</p></div>`}
        </div>
      </section>
      ${side()}
    </div>`;
}

export function enter() {
  refresh();
}
