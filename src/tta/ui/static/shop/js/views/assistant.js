// The assistant: the buyer says what is needed, the agent answers with an offer it may or may not order alone.
import { app, api, dataToday, deliveryOf, on, pendingApprovals, refresh, render, spendToday, toast } from "../core.js";
import { clock, html, isoDay, longDate, money, num, shortDate, titleCase, unit } from "../dom.js";
import { icon } from "../icons.js";
import { ROLES, allergenName, allergenRule } from "../kitchens.js";
import { confirm, dismiss, prepare, review } from "../learning.js";
import { active, mine, save } from "../store.js";
import { optionBlock, personFor, problemBox, rolesStillNeeded, ruleList, signerName, spinner } from "./parts.js";

const SOURCES = {
  model: "read by Gemini",
  recording: "read from a recorded Gemini answer",
  "hand-built": "read from a hand-written answer",
  "rule-based": "read by fixed rules, no model",
  example: "example request, sent as typed",
};

const REASONS = {
  CUTOFF_PASSED: "order cut-off passed",
  NOT_DELIVERABLE: "cannot be delivered",
  OUT_OF_STOCK: "out of stock",
  BLOCKED: "sales blocked",
  PORTION_PACK: "single-serve portions",
  PACK_SIZE_UNKNOWN: "pack size unknown",
  LATE_FOR_NEEDED_BY: "arrives too late",
  PRICE_UNAVAILABLE: "no valid price",
  ALLERGEN_DECLARED: "declares an excluded allergen",
  ALLERGEN_NOT_STATED: "allergen not stated",
  QUANTITY_NOT_CONFIRMED: "stock not confirmed",
  DELIVERY_NOT_CONFIRMED: "delivery date not confirmed",
  NOT_IN_RECORDING: "not in the recorded data",
  LABEL_MISSING: "missing a required label",
};

const findTurn = (id) => mine().thread.find((t) => t.id === id);

function update(turn) {
  save();
  render();
  return turn;
}

// ---- asking -----------------------------------------------------------------------------------------------

async function ask(text, typed = null) {
  text = text.trim();
  if (!text) return;
  const k = active();
  const turn = { id: `t${Date.now().toString(36)}`, text, at: new Date().toISOString(), phase: "reading" };
  mine().thread.push(turn);
  app.ui.draft = "";
  update(turn);
  try {
    let request;
    if (typed) {
      request = structuredClone(typed);
      turn.reading = { source: "example" };
    } else {
      const reading = await api().read(text);
      request = reading.request;
      turn.reading = { source: reading.source, sentence: reading.sentence };
    }
    const prepared = prepare(request, k, mine());
    turn.applied = prepared.applied;
    turn.phase = "looking";
    update(turn);
    turn.offer = await api().offer(prepared.request);
    turn.flags = review(turn.offer, mine());
    turn.phase = "done";
    update(turn);
    await act(turn);
  } catch (error) {
    turn.phase = "failed";
    turn.problem = { title: error.title, message: error.message, status: error.status };
    update(turn);
  }
}

// What the agent does on its own once the offer is in: order within its authority, or send it for approval.
async function act(turn) {
  const first = turn.offer?.options?.[0];
  if (!first || turn.order) return;
  const verdict = first.decision.verdict;
  if (verdict === "BLOCK") return;
  if (turn.flags?.length) return; // an open question to the buyer comes first
  if (verdict === "AUTO" || (verdict === "APPROVAL" && mine().prefs.autoSend)) await place(turn, first.option_id);
}

async function place(turn, optionId) {
  turn.busy = true;
  update(turn);
  try {
    const key = `shop.${active().id}.${turn.offer.offer_id}.${optionId}`;
    turn.order = await api().order(turn.offer.offer_id, optionId, key);
    turn.problem = null;
  } catch (error) {
    turn.problem = { title: error.title, message: error.message, status: error.status };
  }
  turn.busy = false;
  update(turn);
  await refresh();
}

async function approveHere(turn) {
  const approval = app.data.approvals.find((a) => a.order_id === turn.order.order_id && a.status === "PENDING");
  if (!approval) return toast("This approval is no longer open.");
  const mineRoles = active().person.roles;
  const roles = rolesStillNeeded(approval).filter((r) => mineRoles.includes(r));
  turn.busy = true;
  update(turn);
  try {
    for (const role of roles) turn.order = await api().decide(approval.approval_id, role, "APPROVE", "Approved from the assistant.", signerName(role));
  } catch (error) {
    turn.problem = { title: error.title, message: error.message, status: error.status };
  }
  turn.busy = false;
  update(turn);
  await refresh();
}

on("ask", (form) => ask(form.elements.text.value));
on("example", (el) => {
  const example = active().examples[Number(el.dataset.i)];
  return ask(example.text, example.request);
});
on("draft", (el) => {
  app.ui.draft = el.value;
});
on("place", (el) => place(findTurn(el.dataset.turn), el.dataset.option));
on("approve-here", (el) => approveHere(findTurn(el.dataset.turn)));
on("retry", (el) => {
  const turn = findTurn(el.dataset.turn);
  mine().thread = mine().thread.filter((t) => t !== turn);
  const example = active().examples.find((e) => e.text === turn.text);
  return ask(turn.text, example?.request || null);
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

// ---- the answer card ---------------------------------------------------------------------------------------

function readAs(request) {
  const parts = request.lines.map((l) => {
    const what = l.product_ids?.length ? `product ${l.product_ids.join(", ")}` : (l.product_type || l.name_terms?.join(" ") || "products").replaceAll("_", " ");
    const claims = (l.required_claims || []).map((c) => c.replace(/^FREE_FROM_/, "").toLowerCase() + "-free").join(", ");
    return `${num(l.quantity)} ${unit(l.unit)} ${claims ? claims + " " : ""}${what}`;
  });
  return `${parts.join(" + ")}${request.needed_by ? `, by ${longDate(request.needed_by)}` : ""}`;
}

function exclusionsSummary(offer) {
  const counts = {};
  for (const e of offer.excluded || []) counts[e.reason] = (counts[e.reason] || 0) + 1;
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([r, n]) => `${n} ${REASONS[r] || r.toLowerCase().replaceAll("_", " ")}`)
    .join(" · ");
}

function whyBlock(turn, first, open) {
  const offer = turn.offer;
  const doubts = first.lines.flatMap((l) => l.claims.filter((c) => c.status !== "CONFIRMED").map((c) => ({ ...c, product: l.name })));
  const checks = first.constraint_checks || [];
  return html`<details class="why" ${open ? "open" : ""}>
    <summary>${icon("right")}Why this answer</summary>
    <div class="why-body">
      <div><h4>Rules checked</h4>${ruleList(first.decision.fired)}</div>
      <div><h4>What you asked for</h4><ul class="why-list">${checks.map(
        (c) => html`<li>${icon(c.result === "MET" ? "check" : c.result === "NOT_MET" ? "x" : "info", c.result === "MET" ? "yes" : c.result === "NOT_MET" ? "no" : "maybe")}<span>${c.sentence}</span></li>`
      )}</ul></div>
      ${doubts.length
        ? html`<div><h4>Not confirmed by Valio Aimo</h4><ul class="why-list">${doubts.map((c) => html`<li>${icon("info", "maybe")}<span><b>${c.claim.replace("_", " ")}</b> · ${c.sentence}</span></li>`)}</ul></div>`
        : html`<div><h4>Data</h4><p class="muted small">Price, stock, delivery date, allergens and origin are confirmed for every product.</p></div>`}
      <div><h4>Looked at ${offer.candidates_considered} products, left out ${offer.excluded?.length || 0}</h4>
        <p class="small muted">${exclusionsSummary(offer) || "None left out."}</p>
        ${(offer.notes || []).map((n) => html`<p class="small muted">${n}</p>`)}
      </div>
      ${first.comparison?.sentence ? html`<div><h4>Delivery and footprint</h4><p class="small muted">${first.comparison.sentence}</p></div>` : ""}
    </div>
  </details>`;
}

function verdictBox(turn, first) {
  const k = active();
  const order = turn.order;
  const busy = turn.busy ? "disabled" : "";
  if (order) {
    if (order.status === "ORDERED") {
      const by = order.placed_by === "AGENT" ? "Ordered by your agent" : "Ordered with approval";
      return html`<div class="verdict ok">${icon("checkCircle")}<div><b>${by}${deliveryOf(order.option) ? ` · delivery ${longDate(deliveryOf(order.option))}` : ""}</b><p>${order.status_sentence}</p><div class="actions"><a class="link" href="#/orders/${order.order_id}">Order and audit trail</a></div></div></div>`;
    }
    if (order.status === "PENDING_APPROVAL") {
      const approval = app.data.approvals.find((a) => a.order_id === order.order_id);
      const needed = approval ? rolesStillNeeded(approval) : order.decision.required_roles;
      const names = needed.map((r) => `${personFor(r)} (${(ROLES[r] || r).toLowerCase()})`).join(" and ");
      const canSign = needed.some((r) => k.person.roles.includes(r));
      return html`<div class="verdict wait">${icon("clock")}<div><b>Sent for approval to ${names}</b><p>${first.decision.sentence}</p>
        <div class="actions">${canSign ? html`<button class="btn small dark" data-act="approve-here" data-turn="${turn.id}" ${busy}>Approve as ${k.person.name}</button>` : ""}<a class="btn small line" href="#/approvals">Open approvals</a></div></div></div>`;
    }
    return html`<div class="verdict stop">${icon("stop")}<div><b>${order.status === "REJECTED" ? "Rejected" : "Expired"}</b><p>${order.status_sentence}</p></div></div>`;
  }
  const d = first.decision;
  if (turn.superseded) return "";
  if (d.verdict === "BLOCK") {
    return html`<div class="verdict stop">${icon("stop")}<div><b>This cannot be ordered, not even with approval</b><p>${d.sentence}</p></div></div>`;
  }
  if (turn.flags?.length) {
    return html`<div class="verdict info">${icon("info")}<div><b>Waiting for your answer before ordering</b><p>${d.verdict === "AUTO" ? "Your agent could order this alone, but the brand question below comes first." : d.sentence}</p></div></div>`;
  }
  if (d.verdict === "AUTO") {
    return html`<div class="verdict ok">${icon("checkCircle")}<div><b>Your agent may order this alone</b><p>${d.sentence}</p><div class="actions"><button class="btn small" data-act="place" data-turn="${turn.id}" data-option="${first.option_id}" ${busy}>Order now</button></div></div></div>`;
  }
  return html`<div class="verdict wait">${icon("clock")}<div><b>Needs ${d.required_roles.map((r) => personFor(r)).join(" and ")}</b><p>${d.sentence}</p><div class="actions"><button class="btn small" data-act="place" data-turn="${turn.id}" data-option="${first.option_id}" ${busy}>Send for approval</button></div></div></div>`;
}

function flagBox(turn, flag) {
  return html`<div class="flag">
    <div class="flag-head">${icon("alert")}Different brand than you usually buy</div>
    <p>The best match is from <b>${flag.vendors.map(titleCase).join(", ")}</b>. You normally take <b>${flag.brand}</b> for dairy. Should the agent stick to ${flag.brand}?</p>
    <div class="actions">
      <button class="btn small dark" data-act="flag-yes" data-turn="${turn.id}" data-rule="${flag.ruleId}" data-brand="${flag.brand}">Yes, ${flag.brand} only</button>
      <button class="btn small line" data-act="flag-no" data-turn="${turn.id}" data-rule="${flag.ruleId}">Other brands are fine</button>
    </div>
    <div class="basis">Why the agent asks: ${flag.basis.toLowerCase()} — it has not learned this from you yet. Your answer is remembered for next time.</div>
  </div>`;
}

function others(turn) {
  const rest = turn.offer.options.slice(1);
  if (!rest.length || !mine().prefs.alternatives) return "";
  const ordered = Boolean(turn.order) || Boolean(turn.superseded);
  return html`<div class="others"><h4>Other options</h4>${rest.map(
    (o) => html`<div class="other">
      <div class="what"><b>${o.title}</b> · ${money(o.totals.net)}<div class="small muted">${o.summary}</div></div>
      ${o.decision.verdict === "AUTO" ? html`<span class="tag ok">Agent may order</span>` : o.decision.verdict === "BLOCK" ? html`<span class="tag stop">Blocked</span>` : html`<span class="tag wait">Needs approval</span>`}
      ${ordered || o.decision.verdict === "BLOCK" ? "" : html`<button class="btn small line" data-act="place" data-turn="${turn.id}" data-option="${o.option_id}">Choose</button>`}
    </div>`
  )}${turn.order?.status === "PENDING_APPROVAL" ? html`<p class="small muted">The approver can still switch to one of these.</p>` : ""}</div>`;
}

function answer(turn) {
  const prefs = mine().prefs;
  if (turn.phase === "reading") return html`<div class="answer">${spinner("Reading your request…")}</div>`;
  if (turn.phase === "looking") return html`<div class="answer">${top(turn)}${spinner("Checking price and stock with Valio Aimo…")}</div>`;
  if (turn.phase === "failed") {
    return html`<div class="answer"><div class="answer-body">${problemBox(turn.problem)}
      <div class="verdict info">${icon("info")}<div><p>${turn.problem?.status === 429 ? "The demo allows a few readings a minute per visitor. Wait a moment, or use one of the examples: they skip the reading step." : "You can try again, or write the request differently."}</p><div class="actions"><button class="btn small line" data-act="retry" data-turn="${turn.id}">Try again</button></div></div></div>
    </div></div>`;
  }
  const offer = turn.offer;
  const first = offer.options?.[0];
  if (!first) {
    return html`<div class="answer">${top(turn)}<div class="answer-body">
      <div class="verdict stop">${icon("stop")}<div><b>Nothing can be offered for this request</b><p>Looked at ${offer.candidates_considered} products: ${exclusionsSummary(offer) || "none matched"}.</p>${(offer.notes || []).map((n) => html`<p>${n}</p>`)}</div></div>
    </div></div>`;
  }
  return html`<div class="answer">${top(turn)}<div class="answer-body">
    <p class="headline">${first.summary}</p>
    ${optionBlock(first, prefs.short)}
    ${turn.resolved ? html`<p class="small muted">${turn.resolved}</p>` : ""}
    ${(turn.flags || []).map((f) => flagBox(turn, f))}
    ${verdictBox(turn, first)}
    ${turn.problem ? problemBox(turn.problem) : ""}
    ${others(turn)}
    ${prefs.short && !prefs.explain ? "" : whyBlock(turn, first, prefs.explain)}
  </div></div>`;
}

function top(turn) {
  const offer = turn.offer;
  const source = SOURCES[turn.reading?.source] || "read";
  return html`<div class="answer-top">
    <span class="agent-dot">${icon("agent")}</span>
    <div class="read">
      ${offer ? html`<b>${readAs(offer.request)}</b>` : html`<b>Request read</b>`}
      <div class="small muted">${source}${offer ? html` · ${offer.source === "replay" ? "recorded Valio Aimo data" : "live Valio Aimo data"}` : ""}</div>
      ${turn.applied?.length ? html`<div class="applied">${turn.applied.map((a) => html`<span class="tag ${a.tone}">${a.text}</span>`)}</div>` : ""}
    </div>
  </div>`;
}

// ---- side panel --------------------------------------------------------------------------------------------

function side() {
  const k = active();
  const s = mine().settings;
  const spent = spendToday();
  const share = s.max_daily_net_eur ? (100 * spent) / s.max_daily_net_eur : 0;
  const waiting = pendingApprovals();
  const upcoming = app.data.orders
    .filter((o) => o.status === "ORDERED" || o.status === "PENDING_APPROVAL")
    .map((o) => ({ o, date: deliveryOf(o.option) }))
    .filter((x) => x.date)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 4);
  const knows = mine().learned.filter((r) => r.state !== "off").slice(0, 3);
  return html`<aside class="side">
    <div class="card">
      <div class="card-title"><h3>Today</h3><span class="tag">${shortDate(isoDay(dataToday()))}</span></div>
      <div class="small muted">Ordered or waiting today, against the daily limit</div>
      <div class="meter ${share > 80 ? "hot" : ""}"><i data-w="${share}"></i></div>
      <div class="kv"><span>${money(spent)} of ${money(s.max_daily_net_eur)}</span><b>${Math.round(share)}%</b></div>
      <div class="kv"><span>Agent orders alone up to</span><b>${s.auto_order_enabled ? money(s.max_order_net_eur) : "never"}</b></div>
      <div class="kv"><span>Allergens kept out</span><b>${s.excluded_allergens.length ? s.excluded_allergens.map((code) => `${allergenName(code)}${allergenRule(s, code) === "STRICT" ? " (strict)" : ""}`).join(", ") : "none"}</b></div>
      <div class="kv"><span>Waiting for approval</span><b>${waiting.length ? html`<a href="#/approvals">${waiting.length}</a>` : "0"}</b></div>
    </div>
    <div class="card">
      <div class="card-title"><h3>Coming deliveries</h3><a class="small" href="#/deliveries">Calendar</a></div>
      ${upcoming.length
        ? html`<ul class="side-list">${upcoming.map(
            ({ o, date }) => html`<li><span class="when">${shortDate(date).split(" ")[1]}<small>${shortDate(date).split(" ")[0]}</small></span><span><a href="#/orders/${o.order_id}">${o.option.lines[0].name}${o.option.lines.length > 1 ? ` +${o.option.lines.length - 1}` : ""}</a><br><span class="small muted">${money(o.option.totals.net)} · ${o.status === "ORDERED" ? "confirmed" : "waiting for approval"}</span></span></li>`
          )}</ul>`
        : html`<p class="small muted">Nothing ordered yet in this demo. Delivery days for ${k.name}: ${k.deliveryDays}.</p>`}
    </div>
    <div class="card">
      <div class="card-title"><h3>What your agent knows</h3><a class="small" href="#/settings">Edit</a></div>
      <ul class="side-list knows">${knows.map((r) => html`<li>${icon("memory")}<span><b>${r.title}</b><br><span class="small muted">${r.basis}</span></span></li>`)}</ul>
    </div>
  </aside>`;
}

// ---- view --------------------------------------------------------------------------------------------------

export function view() {
  const k = active();
  const thread = mine().thread;
  const hour = new Date().getHours();
  const hello = hour < 11 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return html`
    <div class="page-head">
      <div><div class="crumbs">${k.name} · customer ${k.customerNo} · ${k.address}</div><h1>${hello}, ${k.person.name.split(" ")[0]}</h1></div>
      ${thread.length ? html`<div class="right"><button class="link quiet" data-act="clear">Clear conversation</button></div>` : ""}
    </div>
    ${app.data.problem && !app.data.ready ? problemBox(app.data.problem) : ""}
    <div class="grid">
      <section>
        <div class="ask">
          <h2>What do you need, and by when?</h2>
          <p>Write it the way you would to a colleague. The agent checks price and stock, and orders within the limits you set.</p>
          <form data-act="ask">
            <label class="sr" for="ask-text">Request</label>
            <textarea id="ask-text" name="text" rows="2" data-send data-input="draft" placeholder="e.g. 40 litres of lactose-free milk by Monday">${app.ui.draft || ""}</textarea>
            <button class="btn" type="submit">${icon("send")}Ask</button>
          </form>
          <div class="examples"><span>Try:</span>${k.examples.map((e, i) => html`<button class="chip" data-act="example" data-i="${i}">${e.text}</button>`)}</div>
        </div>
        <div class="thread">
          ${thread.length
            ? thread
                .slice()
                .reverse()
                .map((t) => html`<div class="turn"><div class="said"><p>${t.text}<time>${clock(t.at)}</time></p></div>${answer(t)}</div>`)
            : html`<div class="card empty"><h3>No requests yet</h3><p>Ask for something, or start from one of the examples above.</p></div>`}
        </div>
      </section>
      ${side()}
    </div>`;
}

export function enter() {
  refresh();
}
