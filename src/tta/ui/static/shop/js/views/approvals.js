// Approvals: what the agent could not order alone, waiting for a named person of this kitchen.
import { app, api, on, pendingApprovals, refresh, render, toast } from "../core.js";
import { cutoff, html, initials, money } from "../dom.js";
import { icon } from "../icons.js";
import { ROLES } from "../kitchens.js";
import { active } from "../store.js";
import { plain } from "../words.js";
import { optionBlock, personFor, problemBox, rolesStillNeeded, signerName, signers } from "./parts.js";

// Only a plain web address becomes a link: never javascript:, data: or anything else a page could carry.
const WEB_LINK = /^https?:\/\//i;

function hostOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

const named = (items) => (Array.isArray(items) && items.length ? items.join(", ") : "nothing named");

// What one manufacturer's page says (task S2). Every word comes from the web and is escaped like any other text.
function evidenceEntry(found) {
  const url = typeof found.source_url === "string" && WEB_LINK.test(found.source_url) ? found.source_url : null;
  if (!found.found || !url) return html`<p class="small">${plain(found.sentence)}</p>`;
  return html`<div class="ev-entry">
    <p><b>Product ${found.product_id}</b>${found.product_name_on_page ? html`, named on the page “${found.product_name_on_page}”` : ""}</p>
    <ul class="findings">
      <li><span>Contains</span>${named(found.contains)}</li>
      <li><span>May contain</span>${named(found.may_contain)}</li>
      <li><span>Free from</span>${named(found.free_from)}</li>
    </ul>
    <p class="small muted">Source: <a href="${url}" title="${url}" target="_blank" rel="noopener noreferrer nofollow">${hostOf(url)}</a>${found.page_title ? html` · page title “${found.page_title}”` : ""}${found.retrieved_at ? html` · read ${cutoff(found.retrieved_at)}` : ""}</p>
  </div>`;
}

// Shown above the reasons, under its own heading, and never as Valio Aimo's data: it changes no status and no
// decision. The same fields and wording as the approvals page of the old pages (templates/_evidence.html).
function evidenceBlock(approval) {
  const entries = (Array.isArray(approval.evidence) ? approval.evidence : []).filter((e) => e && typeof e === "object");
  if (!entries.length) return "";
  return html`<section class="evidence">
    <h4>Manufacturer's page, not Valio Aimo data</h4>
    ${entries.map(evidenceEntry)}
    <p class="small muted">Read from the web through Context.dev. Valio Aimo's data still states nothing about this allergen, so it stays unknown: this changes no status and no decision, and the person approving decides.</p>
  </section>`;
}

const notes = {};
const busy = new Set();

async function decide(el, decision) {
  const { id, role } = el.dataset;
  busy.add(id);
  render();
  try {
    const order = await api().decide(id, role, decision, notes[id] || "", signerName(role));
    delete notes[id];
    toast(order.status === "ORDERED" ? "Approved. The order is placed." : order.status === "REJECTED" ? "Rejected. Nothing was ordered." : "Signed. Waiting for the other approver.");
  } catch (error) {
    toast(error.message);
  }
  busy.delete(id);
  await refresh();
}

on("approve", (el) => decide(el, "APPROVE"));
on("reject", (el) => decide(el, "REJECT"));
on("note", (el) => {
  notes[el.dataset.id] = el.value;
});

function card(approval) {
  const order = app.data.orders.find((o) => o.order_id === approval.order_id);
  const option = order?.option;
  const needed = rolesStillNeeded(approval);
  const k = active();
  const off = busy.has(approval.approval_id) ? "disabled" : "";
  return html`<article class="card">
    <div class="appr-head">
      <div class="t">
        <b>${option ? option.summary : `Order ${approval.order_id}`}</b>
        <div class="small muted">Asked by your agent · order ${approval.order_id}${approval.valid_until ? html` · decide by <b>${cutoff(approval.valid_until)}</b>, then it expires` : ""}</div>
      </div>
      ${option ? html`<span class="tag wait">${money(option.totals.net)}</span>` : ""}
    </div>
    ${evidenceBlock(approval)}
    <ul class="reasons">${(approval.reasons || []).map((r) => html`<li>${icon("clock")}<span>${plain(r)}</span></li>`)}</ul>
    ${option ? optionBlock(option, true) : ""}
    <div class="decide">
      ${signers(approval)}
      <div class="row">
        <label class="sr" for="note-${approval.approval_id}">Note</label>
        <input type="text" id="note-${approval.approval_id}" data-input="note" data-id="${approval.approval_id}" placeholder="Note for the audit trail (optional)" value="${notes[approval.approval_id] || ""}">
      </div>
      <div class="row">
        ${needed.map((role) => {
          const name = personFor(role);
          const isMe = k.person.roles.includes(role);
          return html`<button class="btn small ${isMe ? "" : "line"}" data-act="approve" data-id="${approval.approval_id}" data-role="${role}" ${off}>Approve as ${name.split(" ")[0]} · ${(ROLES[role] || role).toLowerCase()}</button>`;
        })}
        <button class="btn small danger" data-act="reject" data-id="${approval.approval_id}" data-role="${needed[0] || "purchasing_manager"}" ${off}>Reject</button>
        <a class="link quiet" href="#/orders/${approval.order_id}">Details</a>
      </div>
    </div>
  </article>`;
}

export function view() {
  const k = active();
  const waiting = pendingApprovals();
  return html`
    <div class="page-head">
      <div><div class="crumbs">${k.name}</div><h1>Approvals</h1><div class="sub">Orders your agent was not allowed to place alone. An agent can never approve its own order.</div></div>
    </div>
    ${app.data.problem ? problemBox(app.data.problem) : ""}
    <div class="grid">
      <section class="queue">
        ${waiting.length ? waiting.map(card) : html`<div class="card empty"><h3>Nothing waiting</h3><p>When an order is above a limit, has unconfirmed stock or needs a dietitian, it shows up here for the right person.</p></div>`}
      </section>
      <aside class="side">
        <div class="card">
          <div class="card-title"><h3>Who signs what</h3></div>
          <ul class="side-list">${Object.entries(ROLES).map(
            ([role, label]) => html`<li><span class="avatar ${k.id}">${initials(personFor(role))}</span><span><b>${personFor(role)}</b><br><span class="small muted">${label}${k.person.roles.includes(role) ? " · you" : ""}</span></span></li>`
          )}</ul>
          <p class="small muted">In this demo you can sign for anyone of the kitchen. In production each person signs in as themselves.</p>
        </div>
      </aside>
    </div>`;
}

export function enter() {
  refresh();
}
