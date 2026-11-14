// The folded parts of a result: why this answer, the products left out, and the brand question.
import { html, titleCase } from "../dom.js";
import { icon } from "../icons.js";
import { plain } from "../words.js";
import { ruleList } from "./parts.js";

// Why a product was left out, after its count (the codes of `tta.contracts.common.ExclusionReason`). "Closing
// time" is the word of Valio Aimo's webshop.
export const REASONS = {
  CUTOFF_PASSED: "closing time passed",
  NOT_DELIVERABLE: "cannot be delivered",
  OUT_OF_STOCK: "out of stock",
  BLOCKED: "sales blocked",
  PORTION_PACK: "single-serve portions",
  NOT_A_PORTION_PACK: "not single-serve portions",
  PACK_SIZE_UNKNOWN: "pack size unknown",
  LATE_FOR_NEEDED_BY: "arrives too late",
  PRICE_UNAVAILABLE: "no valid price",
  SUBSTITUTE_ADDS_ALLERGEN: "a substitute that would add an allergen",
  ALLERGEN_DECLARED: "declares an excluded allergen",
  ALLERGEN_NOT_STATED: "allergen not stated",
  QUANTITY_NOT_CONFIRMED: "quantity not confirmed",
  DELIVERY_DATE_NOT_CONFIRMED: "delivery date not confirmed",
  NOT_IN_RECORDING: "not in the recorded data",
  LABEL_MISSING: "missing a required label",
};

export function exclusionsSummary(offer) {
  const counts = {};
  for (const e of offer.excluded || []) counts[e.reason] = (counts[e.reason] || 0) + 1;
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([r, n]) => `${n} ${REASONS[r] || String(r).toLowerCase().replaceAll("_", " ")}`)
    .join(" · ");
}

const CHECK_ICONS = { MET: ["check", "yes"], NOT_MET: ["x", "no"] };

export function whyBlock(offer, option, open) {
  const doubts = (option.lines || []).flatMap((l) => (l.claims || []).filter((c) => c.status !== "CONFIRMED").map((c) => ({ ...c, product: l.name })));
  const checks = option.constraint_checks || [];
  return html`<details class="why" ${open ? "open" : ""}>
    <summary>${icon("right")}Why this answer</summary>
    <div class="why-body">
      <div><h4>Rules checked</h4>${ruleList(option.decision?.fired)}</div>
      <div><h4>What you asked for</h4><ul class="why-list">${checks.map((c) => {
        const [name, tone] = CHECK_ICONS[c.result] || ["info", "maybe"];
        return html`<li>${icon(name, tone)}<span>${plain(c.sentence)}</span></li>`;
      })}</ul></div>
      ${doubts.length
        ? html`<div><h4>Not confirmed by Valio Aimo</h4><ul class="why-list">${doubts.map((c) => html`<li>${icon("info", "maybe")}<span><b>${String(c.claim).replaceAll("_", " ")}</b> · ${plain(c.sentence)}</span></li>`)}</ul></div>`
        : html`<div><h4>Data</h4><p class="muted small">Price, stock, delivery date, allergens and origin are confirmed for every product.</p></div>`}
      <div><h4>Looked at ${offer.candidates_considered ?? 0} products, left out ${offer.excluded?.length || 0}</h4>
        <p class="small muted">${exclusionsSummary(offer) || "None left out."}</p>
        ${(offer.notes || []).map((n) => html`<p class="small muted">${plain(n)}</p>`)}
      </div>
      ${option.comparison?.sentence ? html`<div><h4>Delivery and footprint</h4><p class="small muted">${plain(option.comparison.sentence)}</p></div>` : ""}
    </div>
  </details>`;
}

export function flagBox(turn, flag) {
  return html`<div class="flag">
    <div class="flag-head">${icon("alert")}Different brand than you usually buy</div>
    <p>The best match is from <b>${flag.vendors.filter(Boolean).map(titleCase).join(", ") || "another supplier"}</b>. You normally take <b>${flag.brand}</b> for dairy. Should the agent stick to ${flag.brand}?</p>
    <div class="actions">
      <button class="btn small dark" data-act="flag-yes" data-turn="${turn.id}" data-rule="${flag.ruleId}" data-brand="${flag.brand}">Yes, ${flag.brand} only</button>
      <button class="btn small line" data-act="flag-no" data-turn="${turn.id}" data-rule="${flag.ruleId}">Other brands are fine</button>
    </div>
    <div class="basis">Why the agent asks: ${flag.basis.toLowerCase()}. It has not learned this from you yet. Your answer is remembered for next time.</div>
  </div>`;
}
