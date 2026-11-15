// The side panel of the request page: the rules in force as the gateway states them (its answer to this
// customer's settings call, never this browser's copy), the coming deliveries and what the agent knows.
import { api, app, dataToday, deliveryOf, money, pendingApprovals, render, spendToday } from "../core.js";
import { customerOf } from "../customer.js";
import { html, isoDay, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { allergenName, allergenRule } from "../kitchens.js";
import { active, memory, mine } from "../store.js";
import { plain } from "../words.js";
import { netTotal } from "./parts.js";
import { recipeMode } from "./settings.js";

function allergensText(profile) {
  const codes = profile.excluded_allergens || [];
  if (!codes.length) return "none";
  return codes.map((code) => `${allergenName(code)}${allergenRule(profile, code) === "STRICT" ? " (strict)" : ""}`).join(", ");
}

// Two settings as a person says them, as the gateway applies them to this customer now (the rule ids stay in each
// order's log and on the developer pages).
const RECIPE_WORDS = { ALWAYS: "always", LEARN: "learned from your orders", WHEN_ASKED: "only when you say so" };
const recipeText = (profile) => RECIPE_WORDS[recipeMode(profile)];

// What the gateway has learned for this customer (api.js `learned`, GET /shop/api/learned), computed there on every call and stored
// nowhere. Read again when the mode or an order's state changes: a decision on a substitute teaches the agent.
const learned = {}; // key -> the route's answer, or null while it is on its way or when it failed
const learnedKey = (profile) => [memory.active, recipeMode(profile), ...app.data.orders.map((o) => `${o.order_id}:${o.status}`)].join("|");

function learnedLine(profile) {
  if (recipeMode(profile) !== "LEARN") return "";
  const key = learnedKey(profile);
  if (!(key in learned)) {
    learned[key] = null;
    api()
      .learned()
      .then((view) => {
        learned[key] = view;
        if (view) render();
      })
      .catch(() => {}); // the card stays without the line; the offers still say what was applied
  }
  return learned[key]?.summary ? html`<p class="small muted">${plain(learned[key].summary)}</p>` : "";
}

function premiumText(profile) {
  const ratio = profile.max_preference_premium_ratio;
  if (ratio === null || ratio === undefined) return "no limit set";
  const share = Math.round(Number(ratio) * 100);
  return share === 0 ? "nothing more than the cheapest" : `up to ${share}% more`;
}

// Every value on the card is changed in Settings: the link opens it at the limits.
const SETTINGS_AT_LIMITS = "#/settings/s-limits";

function rulesCard() {
  const authority = app.data.authority;
  const p = authority?.profile;
  const waiting = pendingApprovals();
  // Shown only when an order waits: nobody is sent to look into an empty list.
  const waitingRow = waiting.length ? html`<div class="kv"><span>Waiting for a decision</span><b><a href="#/approvals">${waiting.length}</a></b></div>` : "";
  if (!p) {
    return html`<div class="card">
      <div class="card-title"><h3>Rules in force</h3><a class="small" href="${SETTINGS_AT_LIMITS}">Change in Settings</a></div>
      <p class="small">${app.data.pushing ? "Sending this customer's settings to the gateway…" : "Not confirmed by the gateway. Nothing is asked or ordered until it confirms them."}</p>
      ${app.data.pushing ? "" : html`<div class="actions"><button class="btn small line" data-act="push-again">Send the settings again</button></div>`}
      ${waitingRow}
    </div>`;
  }
  const spent = spendToday();
  const daily = Number(p.max_daily_net_eur) || 0;
  const share = daily ? (100 * spent) / daily : 0;
  return html`<div class="card">
    <div class="card-title"><h3>Today</h3><span class="tag">${shortDate(isoDay(dataToday()))}</span><a class="small" href="${SETTINGS_AT_LIMITS}">Change in Settings</a></div>
    <div class="small muted">Ordered or waiting today, against the limit per day</div>
    <div class="meter ${share > 80 ? "hot" : ""}"><i data-w="${share}"></i></div>
    <div class="kv"><span>${money(spent)} of ${money(p.max_daily_net_eur)}</span><b>${Math.round(share)}%</b></div>
    <div class="kv"><span>Limit per day</span><b>${money(p.max_daily_net_eur)}</b></div>
    <div class="kv"><span>Limit per order</span><b>${money(p.max_order_net_eur)}</b></div>
    <div class="kv"><span>Agent orders alone</span><b>${p.auto_order_enabled ? "when all is confirmed" : "never: you confirm"}</b></div>
    <div class="kv"><span>Allergens kept out</span><b>${allergensText(p)}</b></div>
    <div class="kv"><span>Substitutes must keep the recipe</span><b>${recipeText(p)}</b></div>
    ${learnedLine(p)}
    <div class="kv"><span>A preference may cost</span><b>${premiumText(p)}</b></div>
    ${waitingRow}
    <p class="small muted">As the gateway applies them to this customer's orders now.${authority.note ? html` ${plain(authority.note)}` : ""}</p>
  </div>`;
}

export function side() {
  const k = active();
  const upcoming = app.data.orders
    .filter((o) => o.status === "ORDERED" || o.status === "PENDING_APPROVAL")
    .map((o) => ({ o, date: deliveryOf(o.option) }))
    .filter((x) => x.date)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 4);
  const knows = mine().learned.filter((r) => r.state !== "off").slice(0, 3);
  return html`<aside class="side">
    ${rulesCard()}
    <div class="card">
      <div class="card-title"><h3>Coming deliveries</h3><a class="small" href="#/deliveries">Calendar</a></div>
      ${upcoming.length
        ? html`<ul class="side-list">${upcoming.map(
            ({ o, date }) => html`<li><span class="when">${shortDate(date).split(" ")[1]}<small>${shortDate(date).split(" ")[0]}</small></span><span><a href="#/orders/${o.order_id}">${o.option.lines[0].name}${o.option.lines.length > 1 ? ` +${o.option.lines.length - 1}` : ""}</a><br><span class="small muted">${netTotal(o.option.totals)} · ${o.status === "ORDERED" ? "confirmed" : "waiting for a decision"}</span></span></li>`
          )}</ul>`
        : html`<p class="small muted">Nothing ordered yet in this demo.${customerOf()?.delivery_days ? ` Delivery days for ${k.name}: ${customerOf().delivery_days}.` : ""}</p>`}
    </div>
    <div class="card">
      <div class="card-title"><h3>What your agent knows</h3><a class="small" href="#/settings">Edit</a></div>
      ${knows.length ? html`<ul class="side-list knows">${knows.map((r) => html`<li>${icon("memory")}<span><b>${r.title}</b><br><span class="small muted">${r.basis}</span></span></li>`)}</ul>` : html`<p class="small muted">Nothing assumed yet. What your past orders suggest is shown under each offer.</p>`}
    </div>
  </aside>`;
}
