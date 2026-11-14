// Settings: the few things a kitchen sets, filled in from the kind of kitchen so there is little to do.
// The buyer-profile part is sent to the gateway and enforced there; answer style and learned notes stay here.
import { app, api, on, pushKitchen, refresh, render, toast } from "../core.js";
import { html, money } from "../dom.js";
import { icon } from "../icons.js";
import { ALLERGENS, ALLERGEN_RULES, NEW_ALLERGEN_RULE, ROLES, allergenName, allergenRule } from "../kitchens.js";
import { restore, confirm, dismiss } from "../learning.js";
import { active, mine, resetKitchen, save } from "../store.js";
import { ended, plain } from "../words.js";
import { personFor } from "./parts.js";

let draft = null;
let message = null;
let saving = false;

export function forget() {
  draft = null;
  message = null;
}

function ensureDraft() {
  if (!draft) draft = { settings: structuredClone(mine().settings), prefs: structuredClone(mine().prefs) };
  return draft;
}

const dirty = () => draft && JSON.stringify(draft.settings) !== JSON.stringify(mine().settings);

on("set", (el) => {
  const d = ensureDraft();
  const key = el.dataset.key;
  let value = el.type === "checkbox" ? el.checked : el.value;
  if (el.dataset.type === "number") value = Number(value);
  if (el.dataset.type === "percent") value = Math.round(Number(value)) / 100;
  d.settings[key] = value;
  message = null;
  render();
});

on("allergen", (el) => {
  const d = ensureDraft();
  const code = el.dataset.code;
  const rules = { ...(d.settings.allergen_strictness_by_code || {}) };
  const set = new Set(d.settings.excluded_allergens);
  if (el.checked) {
    set.add(code);
    rules[code] = rules[code] || NEW_ALLERGEN_RULE;
  } else {
    set.delete(code);
    delete rules[code];
  }
  d.settings.excluded_allergens = ALLERGENS.map(([c]) => c).filter((c) => set.has(c));
  d.settings.allergen_strictness_by_code = rules;
  d.settings.allergen_strictness = d.settings.excluded_allergens.length ? d.settings.allergen_strictness || "DECLARED_ONLY" : null;
  message = null;
  render();
});

on("allergen-rule", (el) => {
  const d = ensureDraft();
  d.settings.allergen_strictness_by_code = { ...(d.settings.allergen_strictness_by_code || {}), [el.dataset.code]: el.dataset.rule };
  message = null;
  render();
});

on("pref", (el) => {
  mine().prefs[el.dataset.key] = el.checked;
  save();
  render();
});

on("learn", (el) => {
  const fn = { confirm, off: dismiss, back: restore }[el.dataset.do];
  fn(mine(), el.dataset.id);
  save();
  render();
});

on("save", async () => {
  const d = ensureDraft();
  saving = true;
  render();
  try {
    app.data.authority = await api().setKitchen(d.settings);
    app.data.refused = null;
    mine().settings = structuredClone(d.settings);
    save();
    message = { ok: true, text: "Saved. The gateway now applies these limits to every order of this customer." };
  } catch (error) {
    // A refused form changes nothing in the gateway (tta.api.sandbox, Kitchen.set_up).
    message = { ok: false, text: `Not saved: ${ended(plain(error.message))} The rules in force did not change.` };
  }
  saving = false;
  render();
});

on("undo", () => {
  draft = null;
  message = null;
  render();
});

on("reset", async () => {
  try {
    await api().reset();
  } catch {
    // an empty book is what we wanted anyway
  }
  resetKitchen(active().id);
  draft = null;
  message = { ok: true, text: "This customer's demo was reset: settings, results and orders." };
  try {
    await pushKitchen();
  } catch (error) {
    message = { ok: false, text: `Reset, but the gateway refused the settings: ${ended(plain(error.message))}` };
  }
  await refresh();
  toast("Demo reset for this customer.");
});

// ---- pieces -------------------------------------------------------------------------------------------------

function toggle(key, checked, change = "set", label = key) {
  return html`<span class="switch"><input type="checkbox" id="f-${key}" data-change="${change}" data-key="${key}" ${checked ? "checked" : ""} aria-label="${label}"><i></i></span>`;
}

function moneyField(key, value) {
  return html`<span class="money"><span>€</span><input type="number" id="f-${key}" min="0" max="100000" step="10" data-change="set" data-key="${key}" data-type="number" value="${value}"></span>`;
}

function radioCards(key, value, choices) {
  return html`<div class="radio-cards">${choices.map(
    ([v, title, text]) => html`<label class="radio-card ${value === v ? "on" : ""}"><input type="radio" name="${key}" value="${v}" data-change="set" data-key="${key}" ${value === v ? "checked" : ""}><span><b>${title}</b><span>${text}</span></span></label>`
  )}</div>`;
}

function allergenRules(s) {
  return html`<h3 class="sub-title">How strict, for each allergen</h3>
    <ul class="allergen-rules">${s.excluded_allergens.map((code) => {
      const current = allergenRule(s, code);
      return html`<li><span><b>${allergenName(code)}</b> <code>${code}</code></span>
        <span class="seg" role="radiogroup" aria-label="Rule for ${allergenName(code)}">${Object.entries(ALLERGEN_RULES).map(
          ([value, r]) => html`<button type="button" role="radio" aria-checked="${current === value}" class="${current === value ? "on" : ""}" data-act="allergen-rule" data-code="${code}" data-rule="${value}">${r.name}</button>`
        )}</span></li>`;
    })}</ul>
    <p class="small muted"><b>Declared only:</b> a product that says nothing about the allergen is offered, marked unverified. <b>Strict:</b> it goes to ${personFor("dietitian")} first. Either way, a product that contains it is never offered.</p>`;
}

const rule = (id) => html`<span class="rule-id rule">${id}</span>`;

function learnedList() {
  const items = mine().learned;
  if (!items.length) return html`<p class="small muted">Nothing yet. The agent adds notes here as you answer its questions.</p>`;
  return html`<ul class="learned">${items.map((r) => {
    const tone = r.state === "confirmed" ? "ok" : r.state === "off" ? "" : "wait";
    const label = r.state === "confirmed" ? "In use" : r.state === "off" ? "Off" : "Assumed — will ask";
    return html`<li><div><b>${r.title}</b> <span class="tag ${tone}">${label}</span><div class="small">${r.detail}</div><div class="basis">${r.basis}</div></div>
      <div class="acts">${r.state === "assumed" ? html`<button class="link" data-act="learn" data-do="confirm" data-id="${r.id}">Confirm</button><button class="link quiet" data-act="learn" data-do="off" data-id="${r.id}">Turn off</button>` : r.state === "confirmed" ? html`<button class="link quiet" data-act="learn" data-do="off" data-id="${r.id}">Turn off</button>` : html`<button class="link" data-act="learn" data-do="back" data-id="${r.id}">Use again</button>`}</div></li>`;
  })}</ul>`;
}

function fixedRules() {
  const rules = (app.data.authority?.rules || []).filter((r) => r.fixed);
  return html`<ul class="locked">${rules.map((r) => html`<li>${icon("lock")}<span class="rule-id">${r.rule_id}</span><span>${r.sentence}</span></li>`)}
    <li>${icon("lock")}<span class="rule-id">F-06</span><span>An agent can never approve an order, its own included.</span></li></ul>`;
}

// What the gateway applies now, from its own answer: never this browser's copy of the settings.
function inForce() {
  const p = app.data.authority?.profile;
  if (!p) return html`<span class="msg bad">Not confirmed by the gateway: nothing is asked or ordered until it accepts these settings.</span>`;
  return html`<span class="msg muted">In force in the gateway: per order ${money(p.max_order_net_eur)} · per day ${money(p.max_daily_net_eur)} · ordering alone ${p.auto_order_enabled ? "on" : "off"}</span>`;
}

// ---- view ---------------------------------------------------------------------------------------------------

export function view() {
  const k = active();
  const d = ensureDraft();
  const s = d.settings;
  const p = mine().prefs;
  return html`
    <div class="page-head"><div><div class="crumbs">${k.name} · customer ${k.customerNo}</div><h1>Settings</h1><div class="sub">Filled in for a ${k.kind.toLowerCase()}. Change only what is different for you.</div></div></div>
    <div class="settings">
      <nav class="toc" aria-label="Sections">
        <a href="#/settings" data-act="jump" data-to="s-allergens">Allergens</a>
        <a href="#/settings" data-act="jump" data-to="s-autonomy">What the agent may do</a>
        <a href="#/settings" data-act="jump" data-to="s-answers">How it answers</a>
        <a href="#/settings" data-act="jump" data-to="s-learned">What it has learned</a>
        <a href="#/settings" data-act="jump" data-to="s-fixed">Always applies</a>
        <a href="#/settings" data-act="jump" data-to="s-kitchen">Customer details</a>
      </nav>
      <div class="stack">
        <section class="card" id="s-allergens">
          <div class="card-title"><h2>Allergens</h2>${rule("P-04")}</div>
          <p class="small muted">Products that declare one of these are never offered. A nutritional claim such as "lactose free" is not an allergen statement; the agent reads the declaration and the ingredient list.</p>
          <div class="allergens">${ALLERGENS.map(
            ([code, name]) => html`<label class="allergen ${s.excluded_allergens.includes(code) ? "on" : ""}"><input type="checkbox" data-change="allergen" data-code="${code}" ${s.excluded_allergens.includes(code) ? "checked" : ""}>${name}<code>${code}</code></label>`
          )}</div>
          ${s.excluded_allergens.length ? allergenRules(s) : ""}
        </section>

        <section class="card" id="s-autonomy">
          <div class="card-title"><h2>What the agent may do alone</h2></div>
          <div class="field"><div><label for="f-auto_order_enabled">Let the agent place orders alone ${rule("F-10")}</label><div class="help">Off: nothing is ordered until ${personFor("purchasing_manager")} confirms it. On: the agent orders alone only when every statement is confirmed and no rule asks for a person.</div></div>${toggle("auto_order_enabled", s.auto_order_enabled, "set", "Let the agent place orders alone")}</div>
          <div class="field"><div><label for="f-max_order_net_eur">Alone up to, per order ${rule("P-01")}</label><div class="help">Above this, ${personFor("purchasing_manager")} approves. Before tax.</div></div>${moneyField("max_order_net_eur", s.max_order_net_eur)}</div>
          <div class="field"><div><label for="f-max_daily_net_eur">Alone up to, per day ${rule("P-02")}</label><div class="help">Everything ordered or waiting today counts. Above it, ${personFor("finance")} (finance) approves.</div></div>${moneyField("max_daily_net_eur", s.max_daily_net_eur)}</div>
          <div class="field"><div><label for="f-min_fill_ratio">Partial deliveries ${rule("P-03")}</label><div class="help">Smallest share of the quantity the agent accepts alone.</div></div>
            <select id="f-min_fill_ratio" data-change="set" data-key="min_fill_ratio" data-type="percent">${[100, 90, 75, 50].map((v) => html`<option value="${v}" ${Math.round(s.min_fill_ratio * 100) === v ? "selected" : ""}>${v === 100 ? "Only the full quantity" : `At least ${v}%`}</option>`)}</select></div>
          <div class="field"><div><label for="f-require_confirmed">Confirmed data only</label><div class="help">Leave out anything whose stock, delivery date or allergens Valio Aimo does not confirm.</div></div>${toggle("require_confirmed", s.require_confirmed, "set", "Confirmed data only")}</div>
          <div class="field"><div><span class="label">Substitutes ${rule("P-05")}</span><div class="help">When what you asked for cannot be had.</div>
            ${radioCards("substitution_without_approval", s.substitution_without_approval, [
              ["NONE", "Always ask me", "The agent proposes, a person decides."],
              ["LISTED_BY_SUPPLIER", "Only ones Valio Aimo lists", "The agent may take a substitute the wholesaler lists for the product."],
              ["SAME_CATEGORY", "Same kind of product", "Any product of the same category that passes the allergen check."],
            ])}</div><span></span></div>
          <div class="field"><div><label for="f-variable_weight">Sold by weight ${rule("P-06")}</label><div class="help">Meat and cheese by the kilo: the invoice can be lower than the offer, never higher.</div></div>
            <select id="f-variable_weight" data-change="set" data-key="variable_weight"><option value="APPROVAL" ${s.variable_weight === "APPROVAL" ? "selected" : ""}>Ask a person</option><option value="AUTO_WITH_CEILING" ${s.variable_weight === "AUTO_WITH_CEILING" ? "selected" : ""}>Agent may order</option></select></div>
          <div class="field"><div><label for="f-deposits">Deposits ${rule("P-07")}</label><div class="help">Bottles and crates with a deposit that has no published price.</div></div>
            <select id="f-deposits" data-change="set" data-key="deposits"><option value="APPROVAL" ${s.deposits === "APPROVAL" ? "selected" : ""}>Ask finance</option><option value="NOTE" ${s.deposits === "NOTE" ? "selected" : ""}>Agent may order, noted</option></select></div>
        </section>

        <section class="card" id="s-answers">
          <div class="card-title"><h2>How the agent answers</h2><span class="tag">kept in this browser</span></div>
          <div class="field"><div><label for="f-short">Short answers</label><div class="help">One line per product, no stock details.</div></div>${toggle("short", p.short, "pref", "Short answers")}</div>
          <div class="field"><div><label for="f-alternatives">Show other options</label><div class="help">Off: only the agent's first choice.</div></div>${toggle("alternatives", p.alternatives, "pref", "Show other options")}</div>
          <div class="field"><div><label for="f-explain">Always explain</label><div class="help">Open the rules, checks and left-out products under every answer.</div></div>${toggle("explain", p.explain, "pref", "Always explain")}</div>
        </section>

        <section class="card" id="s-learned">
          <div class="card-title"><h2>What the agent has learned</h2><span class="tag">kept in this browser</span></div>
          <p class="small muted">The agent starts from what is usual for a ${k.kind.toLowerCase()}. An assumption is never used quietly: it asks you first, and only what you confirm narrows its search.</p>
          ${learnedList()}
        </section>

        <section class="card" id="s-fixed">
          <div class="card-title"><h2>Always, whatever you set</h2>${icon("lock")}</div>
          <p class="small muted">Fixed rules of the gateway. No customer setting can switch them off.</p>
          ${fixedRules()}
        </section>

        <section class="card" id="s-kitchen">
          <div class="card-title"><h2>Customer details</h2><span class="tag">demo data</span></div>
          <div class="kv"><span>Customer</span><b>${k.name} · ${k.customerNo}</b></div>
          <div class="kv"><span>Delivery address</span><b>${k.address}</b></div>
          <div class="kv"><span>Delivery days</span><b>${k.deliveryDays}</b></div>
          <div class="kv"><span>Signed in as</span><b>${k.person.name} · ${k.person.title}</b></div>
          ${Object.entries(ROLES).map(([role, label]) => html`<div class="kv"><span>${label}</span><b>${personFor(role)}</b></div>`)}
          <div class="row"><button class="link quiet" data-act="reset">${icon("refresh")} Reset this customer's demo</button></div>
        </section>

        <div class="save-bar">
          ${message ? html`<span class="msg ${message.ok ? "ok" : "bad"}">${message.text}</span>` : dirty() ? html`<span class="msg">Unsaved changes to limits or allergens.</span>` : inForce()}
          ${dirty() ? html`<button class="btn line small" data-act="undo">Undo</button>` : ""}
          <button class="btn" data-act="save" ${dirty() && !saving ? "" : "disabled"}>${saving ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>`;
}

on("jump", (el) => document.getElementById(el.dataset.to)?.scrollIntoView({ behavior: "smooth", block: "start" }));

export function enter() {
  draft = null;
  message = null;
  render();
}
