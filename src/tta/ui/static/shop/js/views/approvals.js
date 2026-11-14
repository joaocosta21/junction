// "Waiting for someone else": the orders that wait for a person other than the one signed in. One person confirms
// an order; a second person decides only where a kitchen really has one, and only what is theirs (the dietitian of
// the ward and the school, for allergen questions). What the person signed in can decide is asked on the request
// itself (assistant.js), so it is here only when that result is gone from the request page.
// For the demonstration, one visitor walks the whole flow: one labelled control decides as the other person.
import { app, api, on, pendingApprovals, refresh, render, toast } from "../core.js";
import { contact, customerKnown } from "../customer.js";
import { cutoff, html } from "../dom.js";
import { evidenceBlock } from "./evidence.js";
import { icon } from "../icons.js";
import { plain } from "../words.js";
import { confirmedBy, customerPending, netTotal, optionBlock, problemBox, rolesStillNeeded, signerName } from "./parts.js";
import { DIETITIAN, allergenQuestion, asksTheDietitian, isMine, otherPeople, personWords, roleOf, said } from "./question.js";

const notes = {};
const busy = new Set();
// The offer of each approval that asks the dietitian, read once: its first option is the safe product. `null`: it
// could not be read, so only the option proposed can be decided.
const offers = new Map();

async function readOffer(offerId) {
  offers.set(offerId, undefined);
  try {
    offers.set(offerId, await api().getOffer(offerId));
  } catch {
    offers.set(offerId, null);
  }
  render();
}

function offerOf(approval) {
  if (!offers.has(approval.offer_id)) readOffer(approval.offer_id);
  return offers.get(approval.offer_id);
}
// The roles signed from this page, per approval: their button goes the moment the gateway accepts the signature,
// before the approvals are read again. It only ever hides a button; what is still awaited is the gateway's record.
const signedHere = new Map();
// The approvals the visitor chose to decide as the other person, for the demonstration.
const actingAs = new Set();

const andList = (items) => items.join(" and ");
// The roles the approval still needs: the gateway's record, less any role just signed here.
const stillNeeded = (approval) => rolesStillNeeded(approval).filter((r) => !signedHere.get(approval.approval_id)?.has(r));
const needsMe = (approval) => stillNeeded(approval).some(isMine);
// Every order that waits. The menu entry counts them and is hidden when there is none (main.js).
export const waitingCount = () => pendingApprovals().length;
// What the menu entry says: an order waits for somebody else, unless every one left waits for the person signed in.
export const waitingLabel = () => (pendingApprovals().length && pendingApprovals().every(needsMe) ? "Needs your decision" : "Waiting for someone else");

const afterDecision = (order, awaited) =>
  order.status === "ORDERED" ? "Decided. The order is placed."
    : order.status === "REJECTED" ? "Decided. Nothing was ordered."
    : awaited ? `Confirmed. Still waiting for ${awaited}.` : "Confirmed.";

// `data-option`: another option of the offer (the safe product); `data-say`: the note when none was written, so the
// audit trail says which of the three choices was taken. One decision signs every role its person holds.
async function decide(el, decision) {
  const { id, role, option, say } = el.dataset;
  busy.add(id);
  render();
  let told = null;
  try {
    const order = await api().decide(id, role, decision, notes[id] || say || "", signerName(role), option);
    delete notes[id];
    signedHere.set(id, new Set([...(signedHere.get(id) || []), role]));
    await refresh(); // the approval as the gateway has it now: who has decided, who is still awaited
    signedHere.delete(id);
    const approval = app.data.approvals.find((a) => a.approval_id === id);
    told = afterDecision(order, approval ? andList(otherPeople(stillNeeded(approval)).map(personWords)) : "");
  } catch (error) {
    told = error.message;
  }
  busy.delete(id);
  toast(told);
}

on("approve", (el) => decide(el, "APPROVE"));
on("reject", (el) => decide(el, "REJECT"));
on("act-as", (el) => {
  actingAs.add(el.dataset.id);
  render();
});
on("note", (el) => {
  notes[el.dataset.id] = el.value;
});

const noteField = (approval) => html`<div class="row">
    <label class="sr" for="note-${approval.approval_id}">Note</label>
    <input type="text" id="note-${approval.approval_id}" data-input="note" data-id="${approval.approval_id}" placeholder="Note for the order's log (optional)" value="${notes[approval.approval_id] || ""}">
  </div>`;

// The two plain buttons of a decision that is not an allergen question.
const yesNo = (approval, role, off, yes) => html`<div class="row">
    <button class="btn small" data-act="approve" data-id="${approval.approval_id}" data-role="${role}" ${off}>${yes}</button>
    <button class="btn small danger" data-act="reject" data-id="${approval.approval_id}" data-role="${role}" ${off}>Reject</button>
  </div>`;

// The part of the person signed in: here only when its result is gone from the request page.
function myPart(approval, order, needed, off) {
  const question = asksTheDietitian(approval, order, needed) && isMine(DIETITIAN);
  const then = otherPeople(needed);
  return html`<div class="decide">
    <p class="progress small"><b>Needs your decision.</b>${then.length ? ` It then waits for ${andList(then.map(personWords))}.` : ""}</p>
    ${question ? allergenQuestion(approval, order, offerOf(approval), off) : ""}
    ${noteField(approval)}
    ${question ? "" : yesNo(approval, needed.find(isMine), off, "Confirm order")}
  </div>`;
}

// The part of somebody else: who it waits for, and the one control that decides as them in this demonstration.
function theirPart(approval, order, needed, off) {
  const other = otherPeople(needed)[0];
  const me = contact()?.name;
  const mineDone = confirmedBy(approval).some(([name]) => name === me);
  const waits = html`<p class="progress small"><b>Waiting for ${personWords(other)}.</b>${mineDone ? " You confirmed your part." : ""}</p>`;
  if (!actingAs.has(approval.approval_id)) {
    return html`<div class="decide">${waits}
      <div class="row"><button class="btn small line" data-act="act-as" data-id="${approval.approval_id}">Decide as ${other.name}, ${roleOf(other)} (demonstration)</button></div>
      <p class="small muted">One visitor walks the whole flow in this demonstration. In production ${other.name} signs in and decides, and nobody else can.</p>
    </div>`;
  }
  const question = other.role === DIETITIAN && asksTheDietitian(approval, order, needed);
  return html`<div class="decide">${waits}
    <p class="small"><b>You are deciding as ${other.name}, ${roleOf(other)} (demonstration).</b> The log names ${other.name}.</p>
    ${question ? allergenQuestion(approval, order, offerOf(approval), off) : ""}
    ${noteField(approval)}
    ${question ? "" : yesNo(approval, other.role, off, "Approve")}
  </div>`;
}

function card(approval) {
  const order = app.data.orders.find((o) => o.order_id === approval.order_id);
  const option = order?.option;
  const needed = stillNeeded(approval);
  const off = busy.has(approval.approval_id) ? "disabled" : "";
  return html`<article class="card">
    <div class="appr-head">
      <div class="t">
        ${option ? html`<div class="small muted">${plain(option.title)}</div>` : ""}
        <b>${option ? plain(option.summary) : `Order ${approval.order_id}`}</b>
        <div class="small muted">Order ${approval.order_id}${approval.valid_until ? html` · decide by <b>${cutoff(approval.valid_until)}</b>, then it expires` : ""} · <a class="link quiet" href="#/orders/${approval.order_id}">Details</a></div>
      </div>
      ${option ? html`<span class="tag wait">${netTotal(option.totals)}</span>` : ""}
    </div>
    ${evidenceBlock(approval)}
    <ul class="reasons">${(approval.reasons || []).map((r) => html`<li>${icon("clock")}<span>${said(r)}</span></li>`)}</ul>
    ${option ? optionBlock(option, true) : ""}
    ${!customerKnown() ? html`<div class="decide">${customerPending()}</div>`
      : needed.some(isMine) ? myPart(approval, order, needed, off)
      : otherPeople(needed).length ? theirPart(approval, order, needed, off)
      : ""}
  </article>`;
}

export function view() {
  const waiting = pendingApprovals();
  const mine = customerKnown() ? waiting.filter(needsMe) : [];
  const theirs = waiting.filter((a) => !mine.includes(a));
  return html`
    <div class="page-head">
      <div><h1>Waiting for someone else</h1><div class="sub">Orders that wait for a person other than you. A decision that is yours is asked on the request itself.</div></div>
    </div>
    ${app.data.problem ? problemBox(app.data.problem) : ""}
    <section class="queue">
      ${mine.length ? html`<h2>Needs your decision</h2>${mine.map(card)}${theirs.length ? html`<h2>Waiting for someone else</h2>` : ""}` : ""}
      ${theirs.map(card)}
      ${waiting.length ? "" : html`<div class="card empty"><h3>Nothing is waiting</h3><p>When a decision belongs to someone else, such as an allergen question for the dietitian, the order waits here for them. Your own decisions are asked on the request itself.</p></div>`}
    </section>`;
}

export function enter() {
  refresh();
}
