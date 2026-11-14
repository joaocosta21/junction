// Pieces several views share: product rows, status tags, rule lists, who signs. Availability is said in the
// words of Valio Aimo's webshop: "available in storage", "Delivery date", "Closing time", "Deliverable".
import { cutoff, html, initials, money, num, shortDate, tile, titleCase, unit } from "../dom.js";
import { icon } from "../icons.js";
import { ROLES } from "../kitchens.js";
import { active } from "../store.js";
import { plain } from "../words.js";

export function stockLine(a) {
  if (!a) return html`<div class="stock"><span class="dot"></span>No availability data</div>`;
  const u = unit(a.sales_unit);
  switch (a.state) {
    case "CONFIRMED":
      return html`<div class="stock"><span class="dot ok"></span>${num(a.usable_amount)} ${u} available in storage${a.available_date ? html` · Delivery date ${shortDate(a.available_date)}` : ""}${a.closing_time ? html` · Closing time ${cutoff(a.closing_time)}` : ""}</div>`;
    case "QUANTITY_NOT_CONFIRMED":
      return html`<div class="stock"><span class="dot wait"></span>${a.available_date ? html`Deliverable ${shortDate(a.available_date)}, quantity not confirmed` : "Quantity not confirmed by Valio Aimo"}</div>`;
    case "CUTOFF_PASSED":
      return html`<div class="stock"><span class="dot stop"></span>Closing time passed${a.closing_time ? html` (${cutoff(a.closing_time)})` : ""}</div>`;
    default:
      return html`<div class="stock"><span class="dot stop"></span>${titleCase(String(a.state).replaceAll("_", " "))}</div>`;
  }
}

export function productLine(line, compact = false) {
  const u = unit(line.sales_unit);
  if (compact) {
    return html`<div class="pline">
      <div class="thumb">${tile(line)}</div>
      <div><div class="pname">${line.name}</div><div class="pid">${num(line.quantity)} ${u} × ${money(line.unit_net_price)}</div></div>
      <div class="pprice"><b>${money(line.net)}</b></div>
    </div>`;
  }
  return html`<div class="pline">
    <div class="thumb">${tile(line)}</div>
    <div>
      <div class="pname">${line.name}</div>
      <div class="pid">${line.product_id} · ${titleCase(line.vendor_name || "")}</div>
      ${stockLine(line.availability)}
    </div>
    <div class="pprice"><b>${money(line.net)}</b><span>${num(line.quantity)} ${u} × ${money(line.unit_net_price)}</span></div>
  </div>`;
}

// A product sold by weight makes the total an estimate: Valio Aimo invoices the weight delivered, which can be
// above or below the weight ordered (Valio Aimo, 14 Nov 2026, P9b-booth-answers.md Q16). Never "at most".
// `is_ceiling` is the field's name today; `is_estimate` is read too, should the field be renamed (P9b Q16-2).
export const isEstimate = (totals) => totals?.is_estimate === true || totals?.is_ceiling === true;
export const ESTIMATE_NOTE = "an estimate: sold by weight, Valio Aimo invoices the weight delivered";

// A total as one figure: "about €506,40" when it is an estimate.
export function netTotal(totals) {
  if (!totals) return money(null);
  return isEstimate(totals) ? `about ${money(totals.net)}` : money(totals.net);
}

export function optionBlock(option, compact = false) {
  const t = option.totals || {};
  const estimate = isEstimate(t);
  const about = estimate ? "about " : "";
  return html`<div class="lines">
    ${option.lines.map((l) => productLine(l, compact))}
    <div class="totals">
      <span class="muted small">Total (VAT 0 %)${estimate ? html` · <span class="estimate">${ESTIMATE_NOTE}</span>` : ""}${t.excludes_deposits ? " · deposits not included" : ""}</span>
      <span class="nowrap"><b>${about}${money(t.net)}</b> <span class="muted small">${about}${money(t.gross)} with VAT</span></span>
    </div>
  </div>`;
}

export function statusTag(order) {
  switch (order.status) {
    case "ORDERED":
      // "Ordered by your agent" only for an order the agent placed alone, which the buyer switched on.
      return order.placed_by === "AGENT"
        ? html`<span class="tag ok">${icon("check")}Ordered by your agent</span>`
        : html`<span class="tag ok">${icon("check")}Confirmed</span>`;
    case "PENDING_APPROVAL":
      return html`<span class="tag wait">${icon("clock")}Waiting for approval</span>`;
    case "REJECTED":
      return html`<span class="tag stop">Rejected</span>`;
    case "EXPIRED":
      return html`<span class="tag stop">Expired</span>`;
    default:
      return html`<span class="tag">${order.status}</span>`;
  }
}

export const personFor = (role) => active().people[role] || ROLES[role] || role;
// The name the audit trail prints for whoever signs in this role.
export const signerName = (role) => `${personFor(role)}, ${active().name}`;

// The roles an approval has obtained: those of each decision that approved, as the gateway counts them
// (`Approval.roles_obtained`). A decision with no `decision` field is read as an approval.
const approved = (approval) => (approval.decisions || []).filter((d) => (d.decision ?? "APPROVE") === "APPROVE");
const rolesOf = (decision) => (decision.role ? [decision.role] : decision.roles || []);

export function rolesStillNeeded(approval) {
  const signed = new Set(approved(approval).flatMap(rolesOf));
  return (approval.required_roles || []).filter((r) => !signed.has(r));
}

// kitchens.js writes a role nobody holds as "No dietitian named": nobody on this page can sign for it.
const NOBODY = /^No\s/;
export const hasPerson = (role) => Boolean(active().people[role]) && !NOBODY.test(active().people[role]);

const roleWord = (role) => (ROLES[role] || role).toLowerCase();
// "Hanna Laine, Harbourside Hotel" is how the trail names a signer (signerName): the page shows the person.
function personOf(decision, role) {
  const signed = String(decision.approver_name || "").trim();
  const suffix = `, ${active().name}`;
  const name = signed.endsWith(suffix) ? signed.slice(0, -suffix.length) : signed;
  return name || personFor(role);
}

// Who has confirmed, from the gateway's record of the approval: [name, [role words]], one name once.
export function confirmedBy(approval) {
  const required = new Set(approval.required_roles || []);
  const byName = new Map();
  for (const d of approved(approval)) {
    for (const role of rolesOf(d).filter((r) => required.has(r))) {
      const name = personOf(d, role);
      byName.set(name, [...(byName.get(name) || []), roleWord(role)]);
    }
  }
  return [...byName];
}

const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

// One line under the signers: who has confirmed, and who is still awaited, in names and roles.
export function progress(approval) {
  const done = confirmedBy(approval).map(([name, roles]) => `${name} (${roles.join(", ")})`);
  const awaited = rolesStillNeeded(approval).map((r) => (hasPerson(r) ? `${personFor(r)} (${roleWord(r)})` : `a ${roleWord(r)}, and none is named for ${active().name}`));
  return html`<p class="progress small">${done.length ? html`<b>Confirmed by</b> ${listed(done)}.` : "Nobody has confirmed yet."} ${awaited.length ? html`<b>Still awaited:</b> ${listed(awaited)}.` : "Nobody else is awaited."}</p>`;
}

export function signers(approval) {
  const needed = new Set(rolesStillNeeded(approval));
  return html`<div class="signers">${(approval.required_roles || []).map((role) => {
    const name = personFor(role);
    return html`<span class="signer ${needed.has(role) ? "" : "done"}"><span class="avatar ${active().id}">${initials(name)}</span>${name} · ${ROLES[role] || role}${needed.has(role) ? "" : html` ${icon("check")}`}</span>`;
  })}</div>`;
}

export function ruleList(fired) {
  if (!fired?.length) return html`<p class="muted small">No rule asked for a human.</p>`;
  return html`<ul class="why-list">${fired.map(
    (r) => html`<li>${icon(r.verdict === "BLOCK" ? "stop" : "clock", r.verdict === "BLOCK" ? "no" : "maybe")}<span><span class="rule-id">${r.rule_id}</span> ${plain(r.sentence)}${r.fixed ? html` <span class="tag">${icon("lock")}fixed rule</span>` : ""}</span></li>`
  )}</ul>`;
}

export function problemBox(error) {
  if (!error) return "";
  return html`<div class="problem"><b>${error.title || "Something went wrong"}</b>${plain(error.message || error.detail || "")}</div>`;
}

export function spinner(text) {
  return html`<div class="working"><span class="spinner"></span>${text}</div>`;
}
