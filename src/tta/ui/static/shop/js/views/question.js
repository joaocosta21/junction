// The dietitian's question (R6; P4-noisy-data.md M1, M2): an approval that asks about an allergen the product data
// does not rule out is asked as a question with three choices, the safe product first. Every choice is a decision
// the gateway already takes: take the safe product (approve the offer's first option, `option_id`), use this
// product anyway (approve the option proposed), leave it out (reject). The gateway checks each one again; the page
// only offers what it would accept.
import { html } from "../dom.js";
import { icon } from "../icons.js";
import { plain } from "../words.js";
import { hasPerson, netTotal, nobodyHolds, personFor, roleWord } from "./parts.js";

export const DIETITIAN = "dietitian";
const PREPARED_ONLY = "F-10"; // the rule that only asks a person to confirm (tta.policy.human_approval)

// The rules of an order that ask the dietitian: an excluded allergen the product data does not rule out (P-04), or
// an allergen check that is missing (F-03 names the dietitian for it).
export const dietitianRules = (decision) => (decision?.fired || []).filter((r) => r.approver_role === DIETITIAN);

export const asksTheDietitian = (approval, order, needed) =>
  needed.includes(DIETITIAN) && dietitianRules(order?.decision).length > 0;

// The safe product: the offer's first option, when it is not the one proposed and nothing about it asks the
// dietitian. The gateway puts a product whose data rules out every excluded allergen first (L2b, "safe first").
export function safeOption(offer, approval) {
  const first = offer?.options?.[0];
  if (!first || first.option_id === approval.option_id) return null;
  if (first.decision?.verdict === "BLOCK" || dietitianRules(first.decision).length) return null;
  return first;
}

// Who signs for the safe product. Choosing another option starts the approval again with that option's own rules,
// so its signer must hold a role it needs. When only F-10 asks for a person, a role the approval already names
// confirms it, the dietitian included (B0, X5).
export function safeSigner(safe) {
  const fired = safe.decision?.fired || [];
  if (fired.every((r) => r.rule_id === PREPARED_ONLY) && hasPerson(DIETITIAN)) return DIETITIAN;
  return (safe.decision?.required_roles || []).find(hasPerson) || null;
}

const productsOf = (option, rules) => {
  const ids = new Set(rules.map((r) => r.product_id).filter(Boolean));
  const lines = (option?.lines || []).filter((l) => !ids.size || ids.has(l.product_id));
  return lines.map((l) => `${l.name} (${l.product_id})`).join(", ") || "this product";
};

const signs = (role) => html`<span class="tiny muted">${personFor(role)} (${roleWord(role)}) signs</span>`;

function button(act, approval, role, label, { option = null, say = "", tone = "", off = "" } = {}) {
  return html`<button class="btn small ${tone}" data-act="${act}" data-id="${approval.approval_id}" data-role="${role}" ${option ? html`data-option="${option}"` : ""} data-say="${say}" ${off}>${label}</button>`;
}

function safeChoice(approval, safe, off) {
  if (!safe) {
    return html`<li><div><b>No safe product to take</b><p class="small">No other option of this offer has data that rules out every excluded allergen.</p></div></li>`;
  }
  const signer = safeSigner(safe);
  const say = `Took the safe product: ${productsOf(safe, [])}.`;
  return html`<li class="first"><div><b>Take the safe product</b> · ${netTotal(safe.totals)}<p class="small">${plain(safe.summary)}</p>${signer ? signs(signer) : html`<p class="small">${nobodyHolds((safe.decision?.required_roles || [])[0] || "purchasing_manager")}</p>`}</div>
    ${signer ? button("approve", approval, signer, "Take the safe product", { option: safe.option_id, say, off }) : ""}</li>`;
}

// The question, its three choices and who answers. `offer` is null while it is being read, and when it cannot be.
export function allergenQuestion(approval, order, offer, off) {
  const option = order?.option;
  const rules = dietitianRules(order?.decision);
  const doubtful = productsOf(option, rules);
  if (!hasPerson(DIETITIAN)) {
    return html`<section class="question"><h4>${icon("alert")}The agent is not sure about ${doubtful}</h4>
      <p>${nobodyHolds(DIETITIAN)} Nothing is ordered: the order waits until it expires.</p></section>`;
  }
  const safe = offer ? safeOption(offer, approval) : null;
  const many = (option?.lines || []).length > 1;
  return html`<section class="question" aria-label="The dietitian's question">
    <h4>${icon("alert")}The agent is not sure about ${doubtful}</h4>
    <p>The product data does not rule out an allergen this customer excludes: the reasons are above. ${personFor(DIETITIAN)}, the dietitian, chooses one of three.</p>
    <ol class="choices">
      ${offer === undefined ? html`<li><div><b>Take the safe product</b><p class="small">Reading the offer's other options…</p></div></li>`
        : offer === null ? html`<li><div><b>Take the safe product</b><p class="small">The offer's other options cannot be read now, so only the option proposed can be decided here.</p></div></li>`
        : safeChoice(approval, safe, off)}
      <li><div><b>Use ${doubtful} anyway</b> · ${netTotal(option?.totals)}<p class="small">You have checked it. The order is placed as proposed; a note written below goes into the audit trail with it.</p>${signs(DIETITIAN)}</div>
        ${button("approve", approval, DIETITIAN, "Use it anyway", { say: `Used anyway after checking: ${doubtful}.`, tone: "line", off })}</li>
      <li><div><b>Leave ${many ? "the line" : "it"} out</b><p class="small">${many ? "The whole order is rejected, so nothing is ordered: one line cannot be dropped from an order here. Ask again without it." : "The order is rejected, so nothing is ordered."} The reason, and a note written below, go into the audit trail.</p>${signs(DIETITIAN)}</div>
        ${button("reject", approval, DIETITIAN, "Leave it out", { say: `Left out: the product data does not rule out the allergen for ${doubtful}.`, tone: "danger", off })}</li>
    </ol>
  </section>`;
}
