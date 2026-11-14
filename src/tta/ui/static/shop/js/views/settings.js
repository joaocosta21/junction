// Settings: the few things a kitchen sets, filled in from the kind of kitchen so there is little to do.
// The buyer-profile part is sent to the gateway and enforced there; answer style and learned notes stay here.
import { app, api, on, pushKitchen, refresh, render, toast } from "../core.js";
import { contact, customerKnown, customerNote, customerOf, myRoles, unitWord, usualProducts } from "../customer.js";
import { html, money } from "../dom.js";
import { icon } from "../icons.js";
import { ALLERGENS, ALLERGEN_RULES, NEW_ALLERGEN_RULE, ROLES, allergenName, allergenRule } from "../kitchens.js";
import { restore, confirm, dismiss } from "../learning.js";
import { active, mine, resetKitchen, save } from "../store.js";
import { ended, plain } from "../words.js";
import { customerPending, personFor } from "./parts.js";

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
  if (el.dataset.type === "percent-or-none") value = value === "" ? null : Math.round(Number(value)) / 100;
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
      return html`<li><span><b>${allergenName(code)}</b></span>
        <span class="seg" role="radiogroup" aria-label="Rule for ${allergenName(code)}">${Object.entries(ALLERGEN_RULES).map(
          ([value, r]) => html`<button type="button" role="radio" aria-checked="${current === value}" class="${current === value ? "on" : ""}" data-act="allergen-rule" data-code="${code}" data-rule="${value}">${r.name}</button>`
        )}</span></li>`;
    })}</ul>
    <p class="small muted"><b>Declared only:</b> a product that says nothing about the allergen is offered, marked unverified. <b>Strict:</b> it goes to ${personFor("dietitian")} first. Either way, a product that contains it is never offered.</p>`;
}

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

// What no setting changes, said once in plain words: the rules themselves, with their ids, are for developers and
// auditors (GET /v1/authority, on the API pages), and each order's log names the rules that applied to it.
const NEVER_ALONE = [
  "order a product that declares an allergen you exclude",
  "approve an order",
  "order when Valio Aimo's stock, price or delivery date is not confirmed",
  "choose a substitute that is not a like-for-like replacement",
];

function neverAlone() {
  return html`<details class="why never"><summary>${icon("right")}What the agent never does on its own, whatever you set</summary>
    <div class="why-body"><p class="small">${NEVER_ALONE.join(" · ")}. A person decides those.</p>
      <p class="small"><a href="/docs" target="_blank" rel="noopener">The full rules, for developers and auditors</a></p></div>
  </details>`;
}

// What a preference (a greener or more reliable choice) may cost above the cheapest option before a person chooses.
const PREMIUMS = [0, 5, 10, 25];

function premiumSelect(ratio) {
  const current = ratio === null || ratio === undefined ? null : Math.round(Number(ratio) * 100);
  const word = (v) => (v === 0 ? "no extra" : `${v}%`);
  // A value the four choices do not hold (no limit at all, in some profiles) is shown as it is, never as another.
  const extra = current === null ? html`<option value="" selected>no limit</option>` : PREMIUMS.includes(current) ? "" : html`<option value="${current}" selected>${current}%</option>`;
  return html`<select id="f-max_preference_premium_ratio" data-change="set" data-key="max_preference_premium_ratio" data-type="percent-or-none">${extra}${PREMIUMS.map((v) => html`<option value="${v}" ${current === v ? "selected" : ""}>${word(v)}</option>`)}</select>`;
}

// What the gateway applies now, from its own answer: never this browser's copy of the settings.
function inForce() {
  const p = app.data.authority?.profile;
  if (!p) return html`<span class="msg bad">Not confirmed by the gateway: nothing is asked or ordered until it accepts these settings.</span>`;
  return html`<span class="msg muted">In force in the gateway: limit per order ${money(p.max_order_net_eur)} · limit per day ${money(p.max_daily_net_eur)} · ordering alone ${p.auto_order_enabled ? "on" : "off"}</span>`;
}

// Who the customer is, from the customer file through the gateway: nothing of it is typed into the page.
const USE = { INGREDIENT: "cooked or baked with", SERVED: "served as it is" };

function customerDetails() {
  if (!customerKnown()) return customerPending();
  const c = customerOf();
  const me = contact();
  const usual = usualProducts();
  return html`
    <div class="kv"><span>Customer</span><b>${[c.name, c.customer_number].filter(Boolean).join(" · ")}</b></div>
    ${c.address ? html`<div class="kv"><span>Delivery address</span><b>${c.address}</b></div>` : ""}
    ${c.delivery_days ? html`<div class="kv"><span>Delivery days</span><b>${c.delivery_days}</b></div>` : ""}
    <div class="kv"><span>Signed in as</span><b>${me.name} · ${me.title}</b></div>
    ${Object.entries(ROLES).map(([role, label]) => html`<div class="kv"><span>${label}</span><b>${personFor(role)}${myRoles().includes(role) ? " (you)" : ""}</b></div>`)}
    ${usual.length ? html`<h3 class="sub-title">Usual products</h3><ul class="side-list">${usual.map((u) => html`<li><span><b>${u.label}</b><br><span class="small muted">ordered in ${unitWord(u.unit)} · ${USE[u.use] || plain(u.use)}</span></span></li>`)}</ul>` : ""}
    <p class="small muted">${plain(customerNote())}</p>`;
}

// ---- view ---------------------------------------------------------------------------------------------------

export function view() {
  const k = active();
  const d = ensureDraft();
  const s = d.settings;
  const p = mine().prefs;
  return html`
    <div class="page-head"><div><div class="crumbs">${[k.name, customerOf()?.customer_number ? `customer ${customerOf().customer_number}` : ""].filter(Boolean).join(" · ")}</div><h1>Settings</h1><div class="sub">Filled in for a ${k.kind.toLowerCase()}. Change only what is different for you.</div></div></div>
    <div class="settings">
      <nav class="toc" aria-label="Sections">
        <a href="#/settings" data-act="jump" data-to="s-allergens">Allergens</a>
        <a href="#/settings" data-act="jump" data-to="s-autonomy">What the agent may do</a>
        <a href="#/settings" data-act="jump" data-to="s-answers">How it answers</a>
        <a href="#/settings" data-act="jump" data-to="s-learned">What it has learned</a>
        <a href="#/settings" data-act="jump" data-to="s-kitchen">Customer details</a>
      </nav>
      <div class="stack">
        <section class="card" id="s-allergens">
          <div class="card-title"><h2>Allergens</h2></div>
          <p class="small muted">Products that declare one of these are never offered. A nutritional claim such as "lactose free" is not an allergen statement; the agent reads the declaration and the ingredient list.</p>
          <div class="allergens">${ALLERGENS.map(
            ([code, name]) => html`<label class="allergen ${s.excluded_allergens.includes(code) ? "on" : ""}"><input type="checkbox" data-change="allergen" data-code="${code}" ${s.excluded_allergens.includes(code) ? "checked" : ""}>${name}</label>`
          )}</div>
          ${s.excluded_allergens.length ? allergenRules(s) : ""}
        </section>

        <section class="card" id="s-autonomy">
          <div class="card-title"><h2>What the agent may do alone</h2></div>
          <div class="field"><div><label for="f-auto_order_enabled">Let the agent place orders alone</label><div class="help">Off: nothing is ordered until ${personFor("purchasing_manager")} confirms it. On: the agent orders alone only when every statement is confirmed and no rule asks for a person.</div></div>${toggle("auto_order_enabled", s.auto_order_enabled, "set", "Let the agent place orders alone")}</div>
          <div class="field" id="s-limits"><div><label for="f-max_order_net_eur">Limit per order</label><div class="help">Above this, ${personFor("purchasing_manager")} approves. Before tax.</div></div>${moneyField("max_order_net_eur", s.max_order_net_eur)}</div>
          <div class="field"><div><label for="f-max_daily_net_eur">Limit per day</label><div class="help">Everything ordered or waiting today counts. Above it, ${personFor("finance")} (finance) approves.</div></div>${moneyField("max_daily_net_eur", s.max_daily_net_eur)}</div>
          <div class="field"><div><label for="f-min_fill_ratio">Partial deliveries</label><div class="help">Smallest share of the quantity the agent accepts alone.</div></div>
            <select id="f-min_fill_ratio" data-change="set" data-key="min_fill_ratio" data-type="percent">${[100, 90, 75, 50].map((v) => html`<option value="${v}" ${Math.round(s.min_fill_ratio * 100) === v ? "selected" : ""}>${v === 100 ? "Only the full quantity" : `At least ${v}%`}</option>`)}</select></div>
          <div class="field"><div><label for="f-require_confirmed">Confirmed data only</label><div class="help">Leave out anything whose stock, delivery date or allergens Valio Aimo does not confirm.</div></div>${toggle("require_confirmed", s.require_confirmed, "set", "Confirmed data only")}</div>
          <div class="field"><div><span class="label">Substitutes</span><div class="help">When what you asked for cannot be had.</div>
            ${radioCards("substitution_without_approval", s.substitution_without_approval, [
              ["NONE", "Always ask me", "The agent proposes, a person decides."],
              ["LISTED_BY_SUPPLIER", "Only ones Valio Aimo lists", "The agent may take a substitute the wholesaler lists for the product."],
              ["SAME_CATEGORY", "Same kind of product", "Any product of the same category that passes the allergen check."],
            ])}</div><span></span></div>
          <div class="field" id="s-recipe"><div><label for="f-formula_matters">Substitutes must keep the recipe</label><div class="help">On: when the product you asked for is not available, a substitute with different ingredients or nutrition is never chosen for you; you decide. Off: only when your request says so (for example “for baking”).</div></div>${toggle("formula_matters", s.formula_matters, "set", "Substitutes must keep the recipe")}</div>
          <div class="field" id="s-premium"><div><label for="f-max_preference_premium_ratio">A greener or more reliable choice may cost up to</label><div class="help">More than the cheapest. Above this, the cheapest option is shown first and you choose.</div></div>${premiumSelect(s.max_preference_premium_ratio)}</div>
          <div class="field"><div><label for="f-variable_weight">Sold by weight</label><div class="help">Meat and cheese by the kilo: the total is an estimate, because Valio Aimo invoices the weight delivered.</div></div>
            <select id="f-variable_weight" data-change="set" data-key="variable_weight"><option value="APPROVAL" ${s.variable_weight === "APPROVAL" ? "selected" : ""}>Ask a person</option><option value="AUTO_WITH_CEILING" ${s.variable_weight === "AUTO_WITH_CEILING" ? "selected" : ""}>Agent may order</option></select></div>
          <div class="field"><div><label for="f-deposits">Deposits</label><div class="help">Bottles and crates with a deposit that has no published price.</div></div>
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

        <section class="card" id="s-kitchen">
          <div class="card-title"><h2>Customer details</h2><span class="tag">demo data</span></div>
          ${customerDetails()}
          <div class="row"><button class="link quiet" data-act="reset">${icon("refresh")} Reset this customer's demo</button></div>
        </section>

        ${neverAlone()}

        <div class="save-bar">
          ${message ? html`<span class="msg ${message.ok ? "ok" : "bad"}">${message.text}</span>` : dirty() ? html`<span class="msg">Unsaved changes to limits or allergens.</span>` : inForce()}
          ${dirty() ? html`<button class="btn line small" data-act="undo">Undo</button>` : ""}
          <button class="btn" data-act="save" ${dirty() && !saving ? "" : "disabled"}>${saving ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>`;
}

on("jump", (el) => document.getElementById(el.dataset.to)?.scrollIntoView({ behavior: "smooth", block: "start" }));

// "#/settings/s-limits" opens Settings at that field (the side card's "Change in Settings").
let jumpTo = null;
export function after() {
  if (!jumpTo) return;
  document.getElementById(jumpTo)?.scrollIntoView({ block: "start" });
  jumpTo = null;
}

export function enter() {
  draft = null;
  message = null;
  jumpTo = app.route.id;
  render();
}
