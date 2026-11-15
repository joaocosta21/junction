// The request page: the buyer writes what is needed, the gateway reads it into a typed request and answers with
// an offer, and nothing is ordered until the buyer clicks "Confirm order". Not a chat: each result is one typed
// request and its answer, newest first. The agent orders alone only where the buyer switched that on.
// One box for two kinds of request: a sentence goes to the reader, as for any product; one it does not read as a
// product request goes to the recipe planner (plan.js), which says whether it names a dish of the gateway's recipe
// table. A product request costs the one round trip it always did; a dish sentence costs one more.
import { app, api, deliveryOf, on, refresh, render, reveal, toast, verifyRules, withRules } from "../core.js";
import { contact, customerKnown, customerOf, loadCustomer, productLabel, unitWord } from "../customer.js";
import { clock, html, longDate, num } from "../dom.js";
import { MENU_EXAMPLES, allergenName } from "../kitchens.js";
import { icon } from "../icons.js";
import { confirm, dismiss, prepare, review } from "../learning.js";
import { active, mine, save } from "../store.js";
import { plain } from "../words.js";
import { REASONS, exclusionsSummary, flagBox, whyBlock } from "./answer-parts.js";
import { loadEvidence } from "./evidence.js";
import { hasPerson, netTotal, nobodyHolds, optionLines, optionTotals, personFor, problemBox, rolesStillNeeded, signerName, spinner, substituteNote, summaryParts, whatDiffers } from "./parts.js";
import { planCard, planReadAs } from "./plan.js";
import { DIETITIAN, askedOf, dietitianRules, isMine, otherPeople, ownQuestion, personWords, reasonOf, said } from "./question.js";
import { failedAnswer, forPeople, problemOf } from "./refusal.js";
import { regularBar } from "./regular.js";
import { hideReorder, reorderShown } from "./reorder.js";
import { side } from "./side.js";
import { loadWhyNot, suggestionsBox } from "./suggestions.js";
import { openInterface, typedRequest } from "./typed.js";

const SOURCES = {
  model: "read by a model",
  recording: "read from a recorded answer of a model",
  "hand-built": "read from a hand-written answer",
  "rule-based": "read by fixed rules, no model",
  example: "example, sent as a typed request",
  suggestion: "a suggestion you added, sent as its own typed request",
  reorder: "what you usually order, sent as the gateway wrote it",
  standing: "a standing order renewed once, sent as the gateway wrote it",
  plan: "planned from the recipe table by fixed rules, no model",
};
// Who read the text, in the page's words. A model is named as the gateway reports it (`Reading.model`), never by
// a name the page holds: "read by the model <id>", or "a model" when the reading names none.
const BY_A_MODEL = ["model", "recording"];
function sourceWords(reading) {
  const words = SOURCES[reading?.source];
  const model = String(reading?.model || "").trim();
  if (!words || !model || !BY_A_MODEL.includes(reading.source)) return words;
  return words.replace("a model", `the model ${model}`);
}
const CONFIRM_NOTE = "Confirmed on the shop's request page.";

const findTurn = (id) => mine().thread.find((t) => t.id === id);
const chosenOf = (turn) => turn.offer?.options?.find((o) => o.option_id === turn.chosen) || turn.offer?.options?.[0];
const isFirst = (turn, option) => Boolean(option) && option === turn.offer?.options?.[0];
// The order of a result as the gateway has it now, so an order somebody else decided shows here too.
const orderOf = (turn) => (turn.order ? app.data.orders.find((o) => o.order_id === turn.order.order_id) || turn.order : null);

// A result whose request was sent again in another form (a suggestion accepted from it, its usual quantity) is
// replaced by the newer one: only that one can be ordered. A newer request that failed replaces nothing.
const replacementOf = (turn) => mine().thread.find((t) => t.replaces === turn.id && t.phase !== "failed");
// Nothing more is ordered from it: a newer result took its place, or the question it asked was answered and asked
// again (`superseded`). A result that holds an order keeps showing it.
const isReplaced = (turn) => !turn.order && (Boolean(turn.superseded) || Boolean(replacementOf(turn)));

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

// `menu`: a dish sentence the page offers as an example, sent to the planner without asking the reader first.
async function ask(text, typed = null, { menu = false } = {}) {
  text = text.trim();
  if (!text) return;
  const k = active();
  const turn = { id: `t${Date.now().toString(36)}`, text, at: new Date().toISOString(), phase: "reading" };
  mine().thread.push(turn);
  app.ui.draft = "";
  reveal(turn.id); // the page goes to the result: the answer is read where the window is
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
      const { reading, refusal } = menu ? {} : await readText(text);
      if (!reading?.request?.lines?.length) {
        if (await planInstead(turn, text, menu ? null : refusal || unread(reading))) return;
      }
      request = reading.request;
      turn.reading = { source: reading.source, sentence: reading.sentence, model: reading.model };
    }
    step = "offer";
    const prepared = prepare(request, k, mine(), app.data.authority?.profile);
    turn.applied = prepared.applied;
    turn.sent = prepared.request;
    await answerWith(turn, prepared.request);
  } catch (error) {
    turn.phase = "failed";
    turn.problem = problemOf(error, error?.step || step);
    reveal(turn.id, { again: true });
    update(turn);
  }
}

// The reader's answer, or its refusal when it asks a question (422) or cannot read at all (503): such a sentence may
// name a dish. Any other refusal (a rate limit, no connection, settings not in force) is thrown as it is.
const MAY_NAME_A_DISH = [422, 503];
async function readText(text) {
  try {
    return { reading: await withRules(() => api().read(text)) };
  } catch (error) {
    if (!MAY_NAME_A_DISH.includes(error?.status)) throw error;
    return { refusal: error };
  }
}

// The sentence planned from the gateway's recipe table. True: planned, the plan and its offer are on the result.
// A refusal about a dish of the table (no servings, two days) is the question shown; a sentence that names no dish
// of it keeps the reader's question (`readerError`), with the planner's list of dishes when it named an unknown one.
async function planInstead(turn, text, readerError) {
  turn.phase = "planning";
  update(turn);
  try {
    turn.plan = await withRules(() => api().plan(text));
  } catch (error) {
    const p = error?.problem || {};
    const aboutADish = Array.isArray(p.dishes_named) && p.dishes_named.length > 0;
    if (!readerError || aboutADish || error?.status !== 422) {
      error.step = error?.status === 422 ? "reading" : "plan";
      error.menu = true;
      throw error;
    }
    // The planner's own sentence helps beside the reader's question when it knew something of the text: a dish
    // the recipe table does not have, an ingredient it names dishes for, a dish built around one.
    const knew = [p.unknown_dishes, p.ingredients_named].some((list) => Array.isArray(list) && list.length) || Boolean(p.built_around);
    if (knew) readerError.dishNote = error.message;
    readerError.step = "reading";
    throw readerError;
  }
  turn.reading = { source: "plan" };
  turn.sent = turn.plan.request;
  try {
    await answerWithPlan(turn);
  } catch (error) {
    if (error && !error.step) error.step = "plan"; // the plan was made: what failed is reading its offer
    throw error;
  }
  return true;
}

// The manufacturer's page for each option that asks the person signed in an allergen question on the result itself
// (question.js, `ownQuestion`): no approval exists yet to carry it, so it is read here, from the recordings.
function loadOwnEvidence(turn) {
  if (!isMine(DIETITIAN)) return;
  for (const option of turn.offer?.options || []) {
    if (dietitianRules(option.decision).length) loadEvidence(turn, option);
  }
}

// The plan's offer, read from this book as it was made, then what it suggests and the one order placed without a
// click (`act`). No brand question: the plan's lines are the recipe's, not a product the buyer named.
async function answerWithPlan(turn) {
  turn.phase = "looking";
  update(turn);
  if (turn.plan.offer_id) turn.offer = await withRules(() => api().getOffer(turn.plan.offer_id));
  turn.flags = [];
  turn.phase = "done";
  reveal(turn.id, { again: true });
  update(turn);
  if (!turn.offer) return;
  loadWhyNot(turn);
  loadOwnEvidence(turn);
  await act(turn);
}

// The offer for a typed request, then what it suggests and does not, then the one order placed without a click.
async function answerWith(turn, request) {
  turn.phase = "looking";
  update(turn);
  turn.offer = await withRules(() => api().offer(request));
  turn.flags = review(turn.offer, mine());
  turn.phase = "done";
  reveal(turn.id, { again: true });
  update(turn);
  loadWhyNot(turn);
  loadOwnEvidence(turn);
  await act(turn);
}

// A request the gateway wrote (a suggestion's, "you usually order this", a standing order's renewal), sent unchanged
// as a new request with a result of its own: the gateway knows it again (a suggestion's names the suggestion it
// accepts, so the acceptance is recorded). The answer is an offer like any other; nothing is ordered by the click.
// `extra.replaces`: the result this request takes the place of. The usual quantity a result's own bar offers
// (regular.js sends the request that result carries) replaces that result too.
export async function sendAsWritten(source, text, request, extra = {}) {
  const from = extra.replaces ? null : mine().thread.find((t) => t.regular?.usualRequest === request);
  const turn = { id: `t${Date.now().toString(36)}`, text, at: new Date().toISOString(), phase: "looking", reading: { source }, sent: request, ...(from ? { replaces: from.id } : {}), ...extra };
  mine().thread.push(turn);
  reveal(turn.id); // the page goes to the new result, the first one: its offer is the one to confirm
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
    reveal(turn.id, { again: true });
    update(turn);
  }
  return turn;
}

// "Add", "Switch", "Use …": the suggestion's own request, which is the request of the result that showed it with
// the suggestion taken, so the new result replaces that one. Nothing is added to the offer that showed it.
function accept(suggestion, from = null) {
  const shownOn = from || mine().thread.find((t) => (t.offer?.suggestions || []).some((s) => s.suggestion_id === suggestion.suggestion_id));
  if (shownOn) shownOn.added = { ...(shownOn.added || {}), [suggestion.suggestion_id]: true };
  return sendAsWritten("suggestion", suggestion.name, suggestion.accept_request, { suggestion, ...(shownOn ? { replaces: shownOn.id } : {}) });
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

// The signed-in person's one decision. The gateway signs it for every role they hold that the order still needs
// (tta.ui.shop_api), so one click is their whole part, whatever rules asked. `decision` REJECT: they leave it out.
async function signMine(turn, { decision = "APPROVE", note = CONFIRM_NOTE } = {}) {
  const order = turn.order;
  if (order?.status !== "PENDING_APPROVAL" || !order.approval_id) return;
  const approval = app.data.approvals.find((a) => a.approval_id === order.approval_id);
  const needed = approval ? rolesStillNeeded(approval) : order.decision?.required_roles || [];
  const role = needed.find(isMine);
  if (!role) return;
  turn.order = await api().decide(order.approval_id, role, decision, note, signerName(role));
  turn.signedBy = personFor(role);
  turn.leftOut = decision === "REJECT";
  update(turn);
}

// `how`: the decision and its note, when the click was one of the three choices of a question asked on the result.
async function place(turn, optionId, sign, how = {}) {
  turn.busy = true;
  turn.problem = null;
  turn.chosen = optionId;
  update(turn);
  try {
    const key = `shop.${active().id}.${turn.offer.offer_id}.${optionId}`;
    if (sign) await loadCustomer(); // who signs is the customer file's person, never a name the page made up
    await verifyRules(); // the order is judged again when placed, under the rules in force then
    turn.order = await withRules(() => api().order(turn.offer.offer_id, optionId, key));
    if (sign) await signMine(turn, how);
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
on("menu-example", (el) => {
  const example = (MENU_EXAMPLES[active().id] || [])[Number(el.dataset.i)];
  if (example) return ask(example.text, null, { menu: true });
});
on("draft", (el) => {
  app.ui.draft = el.value;
});
on("redraft", (el) => {
  app.ui.redraft[el.dataset.turn] = el.value;
});
on("confirm", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (!turn || turn.busy || turn.order || isReplaced(turn)) return;
  const { decision, say } = el.dataset;
  return place(turn, el.dataset.option, true, { decision: decision || "APPROVE", note: say || CONFIRM_NOTE });
});
on("sign", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (turn && !turn.busy) return signPending(turn);
});
on("choose", (el) => {
  const turn = findTurn(el.dataset.turn);
  if (!turn || turn.order || isReplaced(turn)) return;
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

// "without milk and without cereals containing gluten": each allergen with its own "without", and no "with"
// inside it that would read as the opposite ("without cereals with gluten").
const WITHOUT = { AW: "cereals containing gluten" };
const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

// `names`: product names the sender of a written request knew (a standing order's lines), by product id, for the
// moment before the offer names them.
function readAs(request, names = {}) {
  const named = (id) => (names[id] ? `${names[id]} (${id})` : productLabel(id));
  const parts = (request?.lines || []).map((l) => {
    const terms = (l.name_terms || []).join(" ");
    const type = l.product_type ? l.product_type.replaceAll("_", " ") : "";
    const what = l.product_ids?.length ? l.product_ids.map(named).join(", ") : [terms, type].filter(Boolean).join(" ") || "products";
    const claims = (l.required_claims || []).map((c) => c.replace(/^FREE_FROM_/, "").toLowerCase().replaceAll("_", " ") + "-free").join(", ");
    const without = listed((l.exclude_allergens || []).map((c) => `without ${WITHOUT[c] || allergenName(c).toLowerCase()}`));
    return `${num(l.quantity)} ${unitWord(l.unit)} ${claims ? claims + " " : ""}${what}${without ? `, ${without}` : ""}`;
  });
  return `${parts.join(" + ")}${request?.needed_by ? `, by ${longDate(request.needed_by)}` : ""}`;
}
// A standing order renewed once is asked under its own name ("Weekly lactose-free milk, hotel kitchen", the
// result's text), then what this renewal holds.
const renewalOf = (turn) => (turn.reading?.source === "standing" && turn.text ? `${turn.text}, renewed once: ` : "");

function asked(turn) {
  const request = turn.offer?.request || turn.sent;
  const wrote = ["example", "suggestion", "reorder", "standing"].includes(turn.reading?.source) ? "" : `You wrote “${turn.text}”`;
  const data = turn.offer ? (turn.offer.source === "replay" ? "recorded Valio Aimo data" : "live Valio Aimo data") : "";
  const meta = [request ? wrote : "", sourceWords(turn.reading), data, turn.at ? clock(turn.at) : ""].filter(Boolean).join(" · ");
  // What the reading itself says a person should know, e.g. "No allergen rule was given for …: read as strict,
  // the safe reading." Sentences about keys or routes are for developers and stay out (forPeople).
  const reading = turn.reading?.sentence ? forPeople(turn.reading.sentence) : [];
  const read = turn.plan ? planReadAs(turn.plan) || turn.text : request ? `${renewalOf(turn)}${readAs(request, turn.names)}` : turn.text;
  return html`<div class="asked">
    <span class="label">Asked</span>
    <div class="read">
      <b>${read}</b>
      ${meta ? html`<div class="small muted">${meta}</div>` : ""}
      ${reading.length ? html`<p class="reading-note small">${icon("info")}<span>${reading.join(" ")}</span></p>` : ""}
      ${turn.applied?.length ? html`<div class="applied">${turn.applied.map((a) => html`<span class="tag ${a.tone}">${a.text}</span>`)}</div>` : ""}
    </div>
  </div>`;
}

// ---- line 3: what needs a person, and why, next to the outcome --------------------------------------------
// One person confirms. A decision the person signed in can make is asked right here, before the button; a decision
// that is somebody else's (the dietitian of the ward and the school) is sent to them by name. No role is shown as a
// label: the person signed in is "you".

// The decision's sentence without what the box already says in its heading.
const why = (sentence) => said(sentence).replace(/^Prepared: confirm to order\.?\s*/i, "");
const PREPARED_ONLY = "F-10"; // the rule that only asks a person to confirm (tta.policy.human_approval)
const onlyPrepared = (decision) => (decision?.fired || []).every((r) => r.rule_id === PREPARED_ONLY);
const PREPARED = "Your agent prepared this order. Nothing is ordered until you confirm it.";
const andList = (items) => items.join(" and ");
// The gateway's sentence of an order's outcome, as a person reads it: who decided, by name, with no role in
// brackets and no rule id (both stay in the order's log).
const ROLE_AFTER_NAME = /\s\((?:purchasing manager|finance|dietitian)(?:, (?:purchasing manager|finance|dietitian))*\)/g;
const RULES_ACCEPTED = /: rules? [^.:]* asked for a human and (?:was|were) accepted/;
const outcome = (sentence) => said(sentence).replace(ROLE_AFTER_NAME, "").replace(RULES_ACCEPTED, "");
// Why an option needs a person. For a dish (a result with a plan) the planner's own note of that option says it
// as a cook reads it (which ingredients are covered, what arrives when), where the policy's sentence counts request
// lines: the note of `plan.notes` that starts "Option <rank>, ", from after its totals. No such note: the policy's.
const AFTER_TOTALS = "with tax. ";
const IT_NEEDS = /\s*It needs [^.]*\.\s*$/;
function planReason(turn, option) {
  const start = `Option ${option?.rank}, `;
  const note = (turn?.plan?.notes || []).find((n) => typeof n === "string" && n.startsWith(start));
  const at = note ? note.indexOf(AFTER_TOTALS) : -1;
  // Who it needs is said by the box itself, by name ("Needs your decision"): the note's last words are left out.
  return at < 0 ? "" : plain(note.slice(at + AFTER_TOTALS.length)).replace(IT_NEEDS, "").trim();
}
const reasonFor = (turn, option, decision) => planReason(turn, option) || reasonOf(decision?.sentence);

// An order the person signed in confirmed themselves: what it cost, and why it needed them (the gateway's reason).
const youDecided = (turn, order) => `Ordered for ${netTotal(order.option?.totals)}.${onlyPrepared(order.decision) ? "" : ` Why it needed your confirmation: ${reasonFor(turn, order.option, order.decision)}`}`;

function orderBox(turn, order) {
  const delivery = deliveryOf(order.option);
  const when = delivery ? ` · delivery ${longDate(delivery)}` : "";
  const trail = html`<a class="link" href="#/orders/${order.order_id}">Order and audit trail</a>`;
  const required = order.decision?.required_roles || [];
  if (order.status === "ORDERED") {
    const alone = order.placed_by === "AGENT";
    // The name only when this person's confirmation was the whole of it; else the gateway's sentence names who decided.
    const byMe = Boolean(turn.signedBy) && required.every(isMine);
    return html`<div class="verdict ok">${icon("checkCircle")}<div><b>${alone ? "Ordered by your agent" : byMe ? `Confirmed by ${turn.signedBy}` : "Confirmed"}${when}</b>
      <p>${byMe ? youDecided(turn, order) : outcome(order.status_sentence)}</p>
      ${alone ? html`<p class="small">You let the agent order alone in Settings. It does so only when every statement is confirmed and no rule asks for a person.</p>` : ""}
      <div class="actions">${trail}</div></div></div>`;
  }
  if (order.status === "PENDING_APPROVAL") {
    const approval = app.data.approvals.find((a) => a.order_id === order.order_id);
    const needed = approval ? rolesStillNeeded(approval) : required;
    const others = otherPeople(needed);
    if (needed.some(isMine)) {
      return html`<div class="verdict wait">${icon("clock")}<div><b>Needs your decision</b><p>${onlyPrepared(order.decision) ? PREPARED : reasonFor(turn, order.option, order.decision)}</p>
        <div class="actions"><button class="btn small" data-act="sign" data-turn="${turn.id}" ${turn.busy ? "disabled" : ""}>Confirm order</button>${trail}</div>
        ${others.length ? html`<p class="small">It then waits for ${andList(others.map(personWords))}.</p>` : ""}</div></div>`;
    }
    const who = andList(others.map(personWords));
    const asked = askedOf(order.decision, needed);
    return html`<div class="verdict wait">${icon("clock")}<div><b>${who ? `Sent to ${who}` : "Waiting for a decision"}</b>
      <p>${turn.signedBy ? "You confirmed your part. " : ""}Nothing is ordered until ${who ? andList(others.map((o) => o.name)) : "a person"} decides${asked.length ? `: ${asked.join(" ")}` : "."}</p>
      <div class="actions"><a class="btn small line" href="#/approvals">Waiting for someone else</a>${trail}</div></div></div>`;
  }
  const head = order.status !== "REJECTED" ? "Expired: nothing was ordered" : turn.leftOut ? "Left out: nothing was ordered" : "Rejected: nothing was ordered";
  return html`<div class="verdict stop">${icon("stop")}<div><b>${head}</b><p>${outcome(order.status_sentence)}</p><div class="actions">${trail}</div></div></div>`;
}

function verdictBox(turn, option) {
  const order = orderOf(turn);
  if (order) return orderBox(turn, order);
  if (turn.superseded) return "";
  const d = option.decision || {};
  const off = turn.busy ? "disabled" : "";
  const button = (label) => html`<button class="btn small" data-act="confirm" data-turn="${turn.id}" data-option="${option.option_id}" ${off}>${label}</button>`;
  if (d.verdict === "BLOCK") {
    return html`<div class="verdict stop">${icon("stop")}<div><b>This cannot be ordered, not even with approval</b><p>${said(d.sentence)}</p></div></div>`;
  }
  if (turn.flags?.length && isFirst(turn, option)) {
    return html`<div class="verdict info">${icon("info")}<div><b>Waiting for your answer before ordering</b><p>${d.verdict === "AUTO" ? "Your agent could order this alone, but the brand question below comes first." : onlyPrepared(d) ? PREPARED : reasonFor(turn, option, d)}</p></div></div>`;
  }
  if (d.verdict === "AUTO") {
    return html`<div class="verdict ok">${icon("checkCircle")}<div><b>Your agent may order this alone</b><p>${why(d.sentence)}</p><div class="actions">${button("Confirm order")}</div></div></div>`;
  }
  const needed = d.required_roles || [];
  // A role nobody of this customer holds: no button the gateway would refuse later. Said only once the customer
  // route has answered; before, the page knows nobody and claims nothing.
  const unheld = customerKnown() ? needed.filter((r) => !hasPerson(r)) : [];
  if (unheld.length) {
    return html`<div class="verdict stop">${icon("stop")}<div><b>Nobody here can confirm this option</b>
      <p>${unheld.map(nobodyHolds).join(" ")} ${reasonFor(turn, option, d)}</p>
      <p class="small">Nothing is ordered. Choose another option below, or ask again without it.</p>
    </div></div>`;
  }
  // Somebody else's decision: said plainly, with what they will be asked, and one button that sends it to them.
  const others = otherPeople(needed);
  if (others.length) {
    const names = andList(others.map((o) => o.name));
    const theirs = askedOf(d, needed.filter((r) => !isMine(r)));
    const mine = askedOf(d, needed.filter(isMine));
    return html`<div class="verdict wait">${icon("clock")}<div><b>This needs ${andList(others.map(personWords))}</b>
      <p>${names} will be asked: ${theirs.join(" ") || reasonFor(turn, option, d)}</p>
      ${mine.length ? html`<p>Sending it is also your own confirmation: ${mine.join(" ")}</p>` : ""}
      <div class="actions">${button(`Send to ${names}`)}</div>
      <p class="small">The order then waits for ${names}. Nothing is ordered until then.</p>
    </div></div>`;
  }
  // Their own decision. An allergen question is asked as its three choices; anything else is one confirmation.
  if (isMine(DIETITIAN) && dietitianRules(d).length) return ownQuestion(turn, option, off);
  return html`<div class="verdict wait">${icon("clock")}<div><b>${onlyPrepared(d) ? "Prepared: confirm to order" : "Needs your decision"}</b>
    <p>${onlyPrepared(d) ? PREPARED : reasonFor(turn, option, d)}</p>
    <div class="actions">${button("Confirm order")}</div>
  </div></div>`;
}

// ---- the result card ---------------------------------------------------------------------------------------

function verdictTag(option) {
  const v = option.decision?.verdict;
  if (v === "AUTO") return html`<span class="tag ok">Agent may order alone</span>`;
  if (v === "BLOCK") return html`<span class="tag stop">Cannot be ordered</span>`;
  return html`<span class="tag wait">Needs a person</span>`;
}

// What the label above an option claims, from the gateway's own kind of option (`OptionKind`). Its suggestion is
// its first option, unless that one is itself an alternative with something not confirmed (no stock figure, an
// allergen not ruled out): then nothing is called suggested. An option the person picked is their choice.
const NOT_CONFIRMED = "ALTERNATIVE_UNCONFIRMED";
const isSuggestion = (turn, option) => isFirst(turn, option) && option.kind !== NOT_CONFIRMED;
// An option the gateway offers for a later day than asked says so in its title ("delivered Monday 16 Nov, 3 days
// later than asked"): its stock may be confirmed, so the label says what is true of it, the date.
const LATER_THAN_ASKED = /\blater than asked\b/i;
const isLater = (option) => LATER_THAN_ASKED.test(option?.title || "");
function optionLabel(turn, option) {
  if (isSuggestion(turn, option)) return "Suggested";
  if (!isFirst(turn, option)) return "Your choice";
  return isLater(option) ? "Later than asked" : "No confirmed option";
}

// An option that is not the one shown: what it offers and costs in the gateway's first words, then its substitutes.
// Where the summary goes on to say what a substitute differs in, that part is folded ("What differs") and the
// substitute's own sentence, which says the same, is not printed beside it.
function otherSummary(option) {
  const [first, rest] = summaryParts(option);
  return html`<div class="small muted">${plain(first)}</div>${option.lines.map((l) => substituteNote(l, { sentence: !rest, table: false }))}${whatDiffers(rest)}`;
}

function others(turn, chosen) {
  const rest = (turn.offer.options || []).filter((o) => o !== chosen);
  if (!rest.length || !mine().prefs.alternatives) return "";
  const locked = Boolean(turn.order) || isReplaced(turn);
  return html`<div class="others"><h4>Other options</h4>${rest.map(
    (o) => html`<div class="other">
      <div class="what"><b>${plain(o.title)}</b> · ${netTotal(o.totals)}${isSuggestion(turn, o) ? html` <span class="tag info">Suggested</span>` : ""}${otherSummary(o)}</div>
      ${verdictTag(o)}
      ${locked || o.decision?.verdict === "BLOCK" ? "" : html`<button class="btn small line" data-act="choose" data-turn="${turn.id}" data-option="${o.option_id}">Choose</button>`}
    </div>`
  )}</div>`;
}

// `id`: where the page scrolls to when the request is sent (main.js), and where its folds are known from (core.js).
const card = (turn, body, state = "") => html`<article class="answer ${state}" id="result-${turn.id}">${asked(turn)}${body}</article>`;

// A result a newer one replaced: what was asked, and one line that says so. No option, no button, no suggestion.
function replacedCard(turn) {
  return card(turn, html`<div class="answer-body"><p class="replaced">${icon("info")}<span>${turn.resolved ? `${turn.resolved} ` : ""}Replaced by the newer request above. Nothing is ordered from this one.</span></p></div>`, "was-replaced");
}

// The offer with no note the plan above it already says (the later recording is said once).
function withoutPlanNotes(turn) {
  const said = new Set(turn.plan?.notes || []);
  return said.size ? { ...turn.offer, notes: (turn.offer.notes || []).filter((n) => !said.has(n)) } : turn.offer;
}

// Why the products of an offer were left out, each reason once with how many it holds, most first: the gateway's
// own sentence per product (`excluded[].sentence`), e.g. "The product declares that it contains milk, which the
// buyer excludes." A product with no sentence is counted under its reason's words.
function leftOutReasons(offer) {
  const counts = new Map();
  for (const e of offer.excluded || []) {
    const why = plain(e.sentence || "") || REASONS[e.reason] || String(e.reason || "").toLowerCase().replaceAll("_", " ");
    counts.set(why, (counts.get(why) || 0) + 1);
  }
  return [...counts].sort((a, b) => b[1] - a[1]);
}

// No option: how many products were checked and why each was left out, said first and in whole sentences ("26
// products checked, 26 left out"); the gateway's own notes and the products by name are one fold away.
function nothingOffered(turn) {
  const offer = turn.offer;
  const checked = offer.candidates_considered ?? 0;
  const out = offer.excluded || [];
  const reasons = leftOutReasons(offer);
  const notes = (offer.notes || []).map((n) => html`<p class="small">${plain(n)}</p>`);
  const counted = (n) => (n === out.length && reasons.length === 1 ? `All ${num(n)}` : `${num(n)} of them`);
  return html`<div class="answer-body">
    <div class="verdict stop">${icon("stop")}<div><b>Nothing can be offered for this request</b>
      ${reasons.length
        ? html`<p>${num(checked)} ${checked === 1 ? "product" : "products"} checked, ${num(out.length)} left out.${reasons.length === 1 ? ` ${counted(reasons[0][1])}: ${reasons[0][0]}` : ""}</p>
          ${reasons.length > 1 ? html`<ul class="asks">${reasons.map(([why, n]) => html`<li>${counted(n)}: ${why}</li>`)}</ul>` : ""}`
        : html`<p>Looked at ${num(checked)} products: ${exclusionsSummary(offer) || "none matched"}.</p>${notes}`}
    </div></div>
    ${reasons.length
      ? html`<details class="why fold"><summary>${icon("right")}The ${num(out.length)} ${out.length === 1 ? "product" : "products"} left out, and the gateway's notes</summary>
          <div class="why-body"><ul class="left-out">${out.map((e) => html`<li>${e.name || "Product"} (${e.product_id})</li>`)}</ul><div>${notes}</div></div></details>`
      : ""}
    ${suggestionsBox(turn)}
    ${typedRequest(turn)}
  </div>`;
}

function answer(turn) {
  const prefs = mine().prefs;
  if (turn.phase === "reading") return card(turn, spinner(turn.reading?.source === "example" ? "Sending the typed request…" : "Reading the text into a typed request…"));
  if (turn.phase === "planning") return card(turn, spinner("Planning from the recipe table: servings, ingredients, then price and stock with Valio Aimo…"));
  if (turn.phase === "looking") return card(turn, spinner("Checking price and availability with Valio Aimo…"));
  if (turn.phase === "failed") return card(turn, html`<div class="answer-body">${failedAnswer(turn)}</div>`);
  if (isReplaced(turn)) return replacedCard(turn);
  const option = chosenOf(turn);
  // A recipe plan with nothing to order leads with its own lines. With an option, what is offered, its total and
  // the button come first, and the recipe's rows follow them (below).
  const plan = turn.plan ? html`<div class="answer-body">${planCard(turn, option)}</div>` : "";
  if (turn.plan && !turn.offer) return card(turn, plan);
  if (!option) return card(turn, html`${plan}${nothingOffered(turn)}`);
  const first = isFirst(turn, option);
  const [summary, differs] = summaryParts(option);
  // What is offered, what it costs and the button come first, so that a window shows them without scrolling; the
  // product lines follow. A request that repeats a regular order is said once, in one line under the headline.
  // What a substitute of the option differs in is one fold under the headline, in the gateway's words.
  return card(turn, html`<div class="answer-body">
    <div class="label-row"><span class="label">${optionLabel(turn, option)}</span><span class="small muted">${plain(option.title)}</span></div>
    <p class="headline">${plain(summary)}</p>
    ${whatDiffers(differs)}
    ${regularBar(turn)}
    ${turn.resolved ? html`<p class="small muted">${turn.resolved}</p>` : ""}
    ${optionTotals(option)}
    ${verdictBox(turn, option)}
    ${first ? (turn.flags || []).map((f) => flagBox(turn, f)) : ""}
    ${turn.problem ? html`${problemBox(turn.problem)}<div class="actions"><button class="btn small line" data-act="retry" data-turn="${turn.id}">Ask again</button></div>` : ""}
    ${turn.plan ? planCard(turn, option) : ""}
    ${optionLines(option, prefs.short)}
    ${others(turn, option)}
    ${suggestionsBox(turn)}
    ${prefs.short && !prefs.explain ? "" : whyBlock(withoutPlanNotes(turn), option, prefs.explain)}
    ${typedRequest(turn)}
  </div>`);
}

// ---- view --------------------------------------------------------------------------------------------------

// "You usually order this", asked each time a customer is opened (reorder.js reads it; "Not now" hides it until
// then): a compact block under the request box, never above it. What it is and its two buttons at once; the
// gateway's own account of it (how often, what is not in it and why) is folded under them.
function reorderPrompt() {
  const r = reorderShown();
  if (!r) return "";
  const whyNot = (Array.isArray(r.why_not) ? r.why_not : []).filter((w) => typeof w === "string" && w.trim());
  const counted = (line) => (Number(line.orders_considered) > 0 ? ` (in ${line.orders_matching} of the last ${line.orders_considered} orders)` : "");
  return html`<section class="reorder" role="status" aria-label="You usually order this" id="reorder-prompt">
    <div class="reorder-row">${icon("refresh")}
      <p><b>You usually order this:</b> ${r.lines.map((l, i) => html`${i ? ", " : ""}${l.name || `product ${l.product_id}`} × ${num(l.quantity)} ${unitWord(l.unit)}`)}</p>
      <div class="actions"><button class="btn small" data-act="reorder-go">Order the same again</button><button class="btn small line" data-act="reorder-hide">Not now</button></div>
    </div>
    <details class="why"><summary>${icon("right")}Why, and what is not in it</summary><div class="why-body">
      ${r.sentence ? html`<p>${plain(r.sentence)}</p>` : ""}
      <ul class="left-out">${r.lines.map((l) => html`<li>${l.name || "Product"} (${l.product_id}) × ${num(l.quantity)} ${unitWord(l.unit)}${counted(l)}</li>`)}${whyNot.map((w) => html`<li>${plain(w)}</li>`)}</ul>
      ${r.note ? html`<p class="small muted">${plain(r.note)}</p>` : ""}
      <p class="small muted">“Order the same again” asks for an offer at today's prices and stock. Nothing is ordered until you confirm it.</p>
    </div></details>
  </section>`;
}

// What is true of ordering for this customer now, as the gateway applies it (never this browser's copy).
function orderingLine() {
  return app.data.authority?.profile?.auto_order_enabled === true
    ? "Your agent orders alone only what is fully confirmed and asks no rule for a person; everything else waits for you to confirm it."
    : "Nothing is ordered until you confirm it.";
}

export function view() {
  const k = active();
  const c = customerOf();
  const me = contact();
  const results = mine().thread;
  return html`
    <div class="page-head">
      <div><div class="crumbs">${[k.name, c?.customer_number ? `customer ${c.customer_number}` : "", c?.address].filter(Boolean).join(" · ")}</div><h1>Purchase request</h1>
        <div class="sub">${me ? `Demo, no login: you are acting as ${me.name}, ${me.title.toLowerCase()}. ` : ""}${orderingLine()}</div></div>
      ${results.length ? html`<div class="right"><button class="link quiet" data-act="clear">Clear results</button></div>` : ""}
    </div>
    ${app.data.problem ? problemBox(app.data.problem) : ""}
    <div class="grid">
      <section>
        <div class="ask">
          <h2>What is needed, how much, and by when</h2>
          <p>The text is read into a typed request: product, quantity, unit, date and allergens. The agent checks price and availability with Valio Aimo and prepares the order for you to confirm. Or name a dish and how many servings: its ingredients are planned from the recipe table.</p>
          <form data-act="ask">
            <label class="sr" for="ask-text">Request</label>
            <textarea id="ask-text" name="text" rows="2" data-send data-input="draft" placeholder="e.g. 40 litres of lactose-free milk by Monday">${app.ui.draft || ""}</textarea>
            <button class="btn" type="submit">Check price and stock</button>
          </form>
          <div class="examples"><span>Examples:</span>${k.examples.map((e, i) => html`<button class="chip" data-act="example" data-i="${i}">${e.text}</button>`)}${(MENU_EXAMPLES[k.id] || []).map((e, i) => html`<button class="chip" data-act="menu-example" data-i="${i}">${e.text}</button>`)}</div>
          ${openInterface()}
        </div>
        ${reorderPrompt()}
        <div class="results ${results.length ? "some" : ""}">
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
