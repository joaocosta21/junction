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

// ---- a substitute: what it gives up, in numbers (R5; P10-formula.md F3, F8) ----------------------------------

const NUTRIENTS = { fat: "Fat", saturated_fat: "Saturated fat", protein: "Protein", carbohydrate: "Carbohydrate", sugars: "Sugars", salt: "Salt" };
const BASIS = { G: "Per 100 g", ML: "Per 100 ml" };
// Whether the substitute keeps the formula: `formula.outcome` (tta.contracts.product.FormulaOutcome) as a tag.
const FORMULA_TAGS = {
  SAME_PRODUCT_OTHER_PACK: ["ok", "Same product, other pack"],
  SAME_BRAND: ["ok", "Keeps the formula"],
  OTHER_BRAND: ["ok", "Keeps the formula, other brand"],
  DIFFERENT: ["stop", "Different formula"],
  NOT_KNOWN: ["wait", "Formula cannot be compared"],
};
const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

// Two columns of numbers: the product asked for and the substitute, for each nutrient whose figures differ, with
// those outside our tolerance marked. Every figure is the gateway's (`formula.differences`).
function formulaTable(formula) {
  const rows = formula?.differences || [];
  if (!rows.length) return "";
  const basis = BASIS[formula.basis] || "Per 100 g or 100 ml";
  return html`<table class="formula">
    <thead><tr><th scope="col">${basis}</th><th scope="col" class="num">Asked for</th><th scope="col" class="num">This product</th></tr></thead>
    <tbody>${rows.map((d) => html`<tr class="${d.within_tolerance ? "" : "off"}"><th scope="row">${NUTRIENTS[d.nutrient] || plain(d.nutrient)}</th><td class="num">${num(d.original)} g</td><td class="num">${num(d.other)} g${d.within_tolerance ? "" : html` <span class="tag stop">outside our tolerance</span>`}</td></tr>`)}</tbody>
  </table>
  <p class="tiny muted">Only the nutrients whose figures differ are listed.</p>`;
}

// "Last resort": the substitute lacks a dietary claim of the product asked for, and no substitute that keeps it
// can be supplied, so a person decides (B7, as João clarified it on 14 Nov 2026).
function lastResort(s) {
  const claims = (s.claims_lost || []).map((c) => `“${plain(c).toLowerCase()}”`);
  const what = !claims.length ? "a dietary claim of the product asked for"
    : `${listed(claims)}, ${claims.length > 1 ? "claims" : "a claim"} of the product asked for`;
  return `Last resort: it does not carry ${what}, and no substitute that keeps ${claims.length > 1 ? "them" : "it"} can be supplied. A person decides.`;
}

// A substitute line: what it stands in for, whether it keeps the formula, "Last resort", and what it gives up as the
// gateway wrote it. `sentence`: the gives-up sentence; `table`: the two columns of numbers.
export function substituteNote(line, { sentence = true, table = true } = {}) {
  const s = line.substitute;
  if (!s) return "";
  const tag = FORMULA_TAGS[s.formula?.outcome];
  const formula = s.formula?.sentence || "";
  const extra = formula && !String(s.gives_up || "").includes(formula.replace(/\.$/, "")) ? ` ${plain(formula)}` : "";
  return html`<div class="subst">
    <div class="subst-head"><span class="tag info">Substitute</span>${s.last_resort ? html`<span class="tag stop">Last resort</span>` : ""}${tag ? html`<span class="tag ${tag[0]}">${tag[1]}</span>` : ""}<span class="small">in place of ${s.original_name || "the product asked for"} (${s.original_id})</span></div>
    ${sentence ? html`<p class="small">${s.last_resort ? html`<b>${lastResort(s)}</b> ` : ""}${plain(s.gives_up)}${extra}</p>` : ""}
    ${table ? formulaTable(s.formula) : ""}
  </div>`;
}

// A substitute line always says what it gives up, with its numbers: in short answers too, since the formula is what
// a bakery decides on (Valio Aimo, 14 Nov 2026: "for cakes ... the formula ... can make a difference").
export function productLine(line, compact = false) {
  const u = unit(line.sales_unit);
  const note = substituteNote(line);
  if (compact) {
    return html`<div class="pline">
      <div class="thumb">${tile(line)}</div>
      <div><div class="pname">${line.name}</div><div class="pid">${num(line.quantity)} ${u} × ${money(line.unit_net_price)}</div>${note}</div>
      <div class="pprice"><b>${money(line.net)}</b></div>
    </div>`;
  }
  return html`<div class="pline">
    <div class="thumb">${tile(line)}</div>
    <div>
      <div class="pname">${line.name}</div>
      <div class="pid">${line.product_id} · ${titleCase(line.vendor_name || "")}</div>
      ${stockLine(line.availability)}
      ${note}
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

export const roleWord = (role) => (ROLES[role] || role).toLowerCase();
// The gateway's own answer when the page signs for such a role (tta.ui.shop_api, NOBODY_HOLDS): said up front, so
// no button is offered that the gateway would refuse.
export const nobodyHolds = (role) => `Nobody at ${active().name} holds the role ${roleWord(role)}, so nobody there can sign for it.`;
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
