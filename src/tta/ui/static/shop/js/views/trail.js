// The audit trail of one order, as the buyer or as Valio Aimo reads it. Valio Aimo's view ("all the steps and
// decisions", "why it made that decision and the logic behind it and product considered", 14 Nov 2026) adds,
// folded under a step, the rules that decided (`facts.decision.rules`) and the products considered and left out
// (`facts.offer.left_out`), grouped by reason. The gateway masks what Valio Aimo may not see; the view says so,
// so a masked value is not taken for a gap. Every value is the gateway's and is escaped like any other text.
import { html, realTime } from "../dom.js";
import { icon } from "../icons.js";
import { ROLES } from "../kitchens.js";
import { plain } from "../words.js";
import { REASONS } from "./answer-parts.js";

const EVENT_NAMES = {
  "request.received": "Request received",
  "request.parsed": "Request read",
  "lookup.performed": "Price and stock checked",
  "offer.created": "Offer made",
  "policy.evaluated": "Rules checked",
  "approval.requested": "Sent for approval",
  "approval.decided": "Approval decided",
  "order.confirmed": "Ordered",
  "order.placed_by_agent": "Ordered by the agent",
  "order.rejected": "Rejected",
  "order.expired": "Expired",
  "authorisation.refused": "Refused",
};

// Left out for a requirement of the buyer's (an allergen it excludes): Valio Aimo gets neither the products nor
// how many, and no total that would give the number by subtraction. With the catalog, a count per product type
// names the allergen (`tta.audit.readers.REASONS_OF_THE_BUYER`). The line is printed whatever the buyer excludes.
const REASONS_OF_THE_BUYER = ["ALLERGEN_DECLARED", "ALLERGEN_NOT_STATED"];
const NOT_SHOWN_OR_COUNTED = "Products left out for a requirement of the buyer's, if any, are not shown or counted.";
const MAX_NAMED_PER_REASON = 10;
export const MASKED = "Limit amounts and allergens are not shown to Valio Aimo";

function eventName(type) {
  const key = String(type).replace(/^tta\.v1\./, "");
  return EVENT_NAMES[key] || key;
}

const list = (value) => (Array.isArray(value) ? value.filter((x) => x && typeof x === "object") : []);
const roleWord = (role) => (ROLES[role] || "person").toLowerCase();

// The outcome of one rule, with the role that must sign: the words of `tta.audit.supplier_decisions`.
function outcome(rule) {
  if (rule.verdict === "BLOCK") return "the order cannot be placed";
  if (rule.verdict === "APPROVAL") return `approval by the buyer's ${roleWord(rule.approver_role)}`;
  return "no approval needed";
}

function rulesPart(rules) {
  if (!rules.length) return "";
  return html`<div><h4>Rules that applied</h4><ul class="why-list">${rules.map(
    (r) => html`<li>${icon(r.verdict === "BLOCK" ? "stop" : "clock", r.verdict === "BLOCK" ? "no" : "maybe")}<span>
      <span class="rule-id">${r.rule_id}</span> ${plain(r.title)}${r.product_id ? html`, on product ${r.product_id}` : ""}
      <span class="small muted">· ${r.fixed ? html`${icon("lock")}a fixed rule` : "a rule the buyer set"} · ${outcome(r)}</span></span></li>`
  )}</ul><p class="small muted">The strictest outcome among the rules that applied decides.</p></div>`;
}

// The products left out, one line per reason: "2 cannot be delivered: Valio semi skimmed milk 0,5 l (464440), …".
function byReason(leftOut) {
  const groups = new Map();
  for (const one of leftOut) groups.set(one.reason, [...(groups.get(one.reason) || []), one]);
  return [...groups].sort((a, b) => b[1].length - a[1].length);
}

function leftOutPart(offer) {
  if (!offer) return "";
  const leftOut = list(offer.left_out).filter((one) => !REASONS_OF_THE_BUYER.includes(one.reason));
  const considered = Number.isFinite(Number(offer.candidates_considered)) ? Number(offer.candidates_considered) : null;
  const head = `${considered !== null ? `Looked at ${considered} products. ` : ""}Left out for a reason in Valio Aimo's own data`;
  return html`<div><h4>${head}</h4>
    ${leftOut.length ? html`<ul class="left-out">${byReason(leftOut).map(([reason, items]) => {
      const named = items.slice(0, MAX_NAMED_PER_REASON).map((i) => `${i.name || "Product"} (${i.product_id})`).join(", ");
      const more = items.length > MAX_NAMED_PER_REASON ? ` and ${items.length - MAX_NAMED_PER_REASON} more` : "";
      return html`<li><b>${items.length} ${REASONS[reason] || String(reason).toLowerCase().replaceAll("_", " ")}</b>: ${named}${more}</li>`;
    })}</ul>` : html`<p class="small muted">None.</p>`}
    <p class="small muted">${NOT_SHOWN_OR_COUNTED}</p></div>`;
}

// The fold under one step of Valio Aimo's view, when the step carries a decision or products left out.
function supplierFold(facts) {
  const rules = list(facts?.decision?.rules);
  const offer = facts?.offer && typeof facts.offer === "object" ? facts.offer : null;
  const left = leftOutPart(offer);
  if (!rules.length && !left) return "";
  const label = [rules.length ? `${rules.length} rule${rules.length === 1 ? "" : "s"} and their outcome` : "", left ? "products left out" : ""].filter(Boolean).join(", ");
  return html`<details class="why fold"><summary>${icon("right")}${label[0].toUpperCase() + label.slice(1)}</summary>
    <div class="why-body">${rulesPart(rules)}${left}</div></details>`;
}

function step(event, reader) {
  const who = event.actor?.display_name || event.actor?.kind || "";
  const ids = Array.isArray(event.rule_ids) ? event.rule_ids : [];
  return html`<li><div class="ev">${realTime(event.time)} · <b>${eventName(event.type)}</b>${who ? ` · ${who}` : ""}</div>
    <p>${plain(event.sentence)}</p>
    ${ids.length ? html`<div class="ev">${ids.map((r) => html`<span class="rule-id">${r}</span> `)}</div>` : ""}
    ${reader === "supplier" ? supplierFold(event.facts) : ""}</li>`;
}

function supplierHead() {
  return html`<div class="valio-view">${icon("shield")}<div><b>What Valio Aimo sees</b>
    <p>Every step and decision: each rule that applied with its outcome, the logic, and the products considered and left out. ${MASKED}; a role stands for each person's name; notes and your own words stay out.</p></div></div>`;
}

export function trailView(view, reader) {
  const events = list(view?.events);
  const chain = view?.chain || {};
  return html`
    ${reader === "supplier" ? supplierHead() : ""}
    <div class="verdict ${chain.ok ? "ok" : "stop"}">${icon(chain.ok ? "shield" : "alert")}<div><b>${chain.ok ? "Trail intact" : "Trail does not verify"}</b><p>${chain.sentence || ""}</p></div></div>
    <p class="small muted">Each step is stamped with the real time it happened. Prices, stock and closing times are judged at the clock shown at the top of the page.</p>
    ${events.length ? html`<ol class="timeline" aria-label="Events">${events.map((e) => step(e, reader))}</ol>` : html`<p class="muted small">No step recorded for this order yet.</p>`}`;
}
