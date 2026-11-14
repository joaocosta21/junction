// Pieces several views share: product rows, status tags, rule lists, who signs.
import { cutoff, html, initials, money, num, shortDate, tile, titleCase, unit } from "../dom.js";
import { icon } from "../icons.js";
import { ROLES } from "../kitchens.js";
import { active } from "../store.js";

export function stockLine(a) {
  if (!a) return html`<div class="stock"><span class="dot"></span>No availability data</div>`;
  const u = unit(a.sales_unit);
  switch (a.state) {
    case "CONFIRMED":
      return html`<div class="stock"><span class="dot ok"></span>${num(a.usable_amount)} ${u} in stock · delivery ${shortDate(a.available_date)}${a.closing_time ? html` · order by ${cutoff(a.closing_time)}` : ""}</div>`;
    case "QUANTITY_NOT_CONFIRMED":
      return html`<div class="stock"><span class="dot wait"></span>Stock not confirmed by Valio Aimo${a.available_date ? html` · delivery ${shortDate(a.available_date)}` : ""}</div>`;
    case "CUTOFF_PASSED":
      return html`<div class="stock"><span class="dot stop"></span>Order cut-off passed</div>`;
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

export function optionBlock(option, compact = false) {
  const t = option.totals;
  return html`<div class="lines">
    ${option.lines.map((l) => productLine(l, compact))}
    <div class="totals">
      <span class="muted small">${t.is_ceiling ? "At most · variable weight" : "Total before tax"}${t.excludes_deposits ? " · deposits not included" : ""}</span>
      <span><b>${money(t.net)}</b> <span class="muted small">${money(t.gross)} with VAT</span></span>
    </div>
  </div>`;
}

export function statusTag(order) {
  switch (order.status) {
    case "ORDERED":
      return order.placed_by === "AGENT"
        ? html`<span class="tag ok">${icon("check")}Ordered by agent</span>`
        : html`<span class="tag ok">${icon("check")}Ordered, approved</span>`;
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

export function rolesStillNeeded(approval) {
  const signed = new Set((approval.decisions || []).flatMap((d) => (d.role ? [d.role] : d.roles || [])));
  return (approval.required_roles || []).filter((r) => !signed.has(r));
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
    (r) => html`<li>${icon(r.verdict === "BLOCK" ? "stop" : "clock", r.verdict === "BLOCK" ? "no" : "maybe")}<span><span class="rule-id">${r.rule_id}</span> ${r.sentence}${r.fixed ? html` <span class="tag">${icon("lock")}fixed rule</span>` : ""}</span></li>`
  )}</ul>`;
}

export function problemBox(error) {
  if (!error) return "";
  return html`<div class="problem"><b>${error.title || "Something went wrong"}</b>${error.message || error.detail || ""}</div>`;
}

export function spinner(text) {
  return html`<div class="working"><span class="spinner"></span>${text}</div>`;
}
