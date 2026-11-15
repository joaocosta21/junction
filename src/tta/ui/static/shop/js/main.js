// The page frame: header with the customer switcher, hash routing, events, and the render function.
import { health } from "./api.js";
import { app, freshData, handlers, keepFolds, on, pushKitchen, refresh, render, restoreFolds, setRenderer, startingCustomer, toast } from "./core.js";
import { contact, loadCustomer } from "./customer.js";
import { html, initials } from "./dom.js";
import { icon } from "./icons.js";
import { KITCHENS, kitchenById } from "./kitchens.js";
import { active, memory, save } from "./store.js";
import { ended, plain } from "./words.js";
import { loadReorder } from "./views/reorder.js";
import * as approvals from "./views/approvals.js";
import * as assistant from "./views/assistant.js";
import * as backoffice from "./views/backoffice.js";
import * as deliveries from "./views/deliveries.js";
import * as orders from "./views/orders.js";
import * as settings from "./views/settings.js";
import * as standing from "./views/standing.js";
import { clockStrip } from "./views/clock.js";

const VIEWS = { assistant, approvals, orders, deliveries, settings, standing, backoffice };
const NAV = [
  ["assistant", "#/", "Request"],
  ["standing", "#/standing", "Standing orders"],
  ["deliveries", "#/deliveries", "Deliveries"],
  ["approvals", "#/approvals", "Waiting for someone else"], // shown with its count, hidden when nothing waits
  ["orders", "#/orders", "Orders"],
  ["settings", "#/settings", "Settings"],
];
// Valio Aimo's own screen is no entry of the customer's menu: it is reached from the strip above it, which says
// whose it is.
const BACK_OFFICE = ["#/backoffice", "Valio Aimo's back office (demo)"];

// ---- loading and switching customer ----------------------------------------------------------------------

async function load() {
  const data = app.data;
  data.ready = false;
  render();
  const customer = loadCustomer().catch(() => null); // a refusal is kept and said where people or history show
  try {
    await pushKitchen();
  } catch {
    // kept in app.data.refused until a push succeeds, and shown on every view (rulesBanner)
  }
  loadReorder(); // "you usually order this", each time the customer is opened or switched to
  data.ready = true;
  await customer;
  await refresh();
}

async function switchKitchen(id) {
  if (id === memory.active) {
    app.ui.menu = false;
    return render();
  }
  memory.active = id;
  save();
  app.ui.menu = false;
  app.data = freshData();
  settings.forget();
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  window.scrollTo(0, 0); // another customer's page begins at its top
  await load();
  const k = kitchenById(id);
  const me = contact(id);
  toast(me ? `Now shopping as ${me.name}, ${k.name}` : `Now shopping for ${k.name}`);
}

on("menu", () => {
  app.ui.menu = !app.ui.menu;
  render();
});
on("switch", (el) => switchKitchen(el.dataset.id));
on("customer-again", () => loadCustomer().catch(() => null));
on("clock-fold", () => {
  app.ui.clockOpen = !app.ui.clockOpen;
  render();
});

// Send this customer's settings again after a refusal; the answer, or the refusal, is what the page then shows.
on("push-again", async () => {
  const pending = pushKitchen();
  render();
  try {
    await pending;
    toast("Settings accepted: the gateway applies them now.");
  } catch {
    render();
  }
  await refresh();
});

// ---- events: one listener per kind, routed by data-act / data-change / data-input --------------------------

function dispatch(event, el) {
  const fn = handlers[el.dataset.act];
  if (!fn) return;
  event.preventDefault();
  // Each action ends with one redraw, whatever its handler drew on the way: a toast redraws nothing (core.js), so
  // a view that says its outcome in a toast is shown as it now is.
  Promise.resolve(fn(el, event))
    .catch((error) => {
      console.error(error);
      toast(error.message || "Something went wrong.");
    })
    .finally(render);
}

document.addEventListener("click", (event) => {
  const el = event.target.closest("[data-act]");
  if (el && el.tagName !== "FORM") return dispatch(event, el);
  if (app.ui.menu && !event.target.closest(".who")) {
    app.ui.menu = false;
    render();
  }
});
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-act]");
  if (form) dispatch(event, form);
});
document.addEventListener("change", (event) => {
  const el = event.target.closest("[data-change]");
  if (el && handlers[el.dataset.change]) handlers[el.dataset.change](el, event);
});
document.addEventListener("input", (event) => {
  const el = event.target.closest("[data-input]");
  if (el && handlers[el.dataset.input]) handlers[el.dataset.input](el, event);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && app.ui.menu) {
    app.ui.menu = false;
    render();
  }
  // Enter sends the request; Shift+Enter makes a new line.
  if (event.key === "Enter" && !event.shiftKey && event.target.matches("textarea[data-send]")) {
    event.preventDefault();
    event.target.form?.requestSubmit();
  }
});

// ---- routing ---------------------------------------------------------------------------------------------

function route() {
  const [, name = "", id = null] = location.hash.replace(/^#/, "").split("/");
  app.route = { name: VIEWS[name] ? name : "assistant", id: id ? decodeURIComponent(id) : null };
}
window.addEventListener("hashchange", () => {
  route();
  app.ui.menu = false;
  window.scrollTo(0, 0); // before the redraw: a result waiting to be shown is scrolled to by it (revealPending)
  render();
  VIEWS[app.route.name].enter?.();
});

// ---- frame -----------------------------------------------------------------------------------------------

function modeLabel() {
  const h = app.health;
  if (!h) return "Gateway";
  return h.mode === "replay" ? "Recorded Valio Aimo data" : "Live · Valio Aimo mock API";
}

// Who is shown in the header: the customer file's person once the gateway has said who it is, else the customer.
function header() {
  const k = active();
  const me = contact();
  const waiting = approvals.waitingCount();
  const wholesale = app.route.name === "deliveries"; // the strip's first tab leads there: selected while it is shown
  const office = app.route.name === "backoffice";
  const link = ([name, href, label], mobile) =>
    name !== "approvals"
      ? html`<a href="${href}" class="${app.route.name === name ? "on" : ""}">${label}</a>`
      : !waiting
        ? "" // nothing waits for anybody: no entry to look into
        : html`<a href="${href}" class="${app.route.name === name ? "on" : ""}">${approvals.waitingLabel()}${mobile ? ` (${waiting})` : html`<span class="badge">${waiting}</span>`}</a>`;
  return html`
    <div class="strip">
      <a class="tab ${wholesale ? "on" : ""}" href="#/deliveries" title="Delivery wholesale">${icon("truck")}<span>Delivery wholesale</span></a>
      <a class="tab ${wholesale || office ? "" : "on"}" href="#/">${icon("agent")}<span>Buying agent</span></a>
      <a class="tab office ${office ? "on" : ""}" href="${BACK_OFFICE[0]}" title="${BACK_OFFICE[1]}">${icon("store")}<span>${BACK_OFFICE[1]}</span></a>
      <span class="mode">${modeLabel()}</span>
    </div>
    ${clockStrip(app.health, app.healthAsked, app.ui.clockOpen)}
    <header class="header">
      <div class="header-in">
        <a class="brand" href="#/"><b>Tukku</b><span>Trusted Trade</span></a>
        <nav class="nav" aria-label="Main">${NAV.map((n) => link(n, false))}</nav>
        <div class="tools">
          <div class="who">
            <button class="who-btn" data-act="menu" aria-haspopup="menu" aria-expanded="${String(app.ui.menu)}">
              <span class="avatar ${k.id}">${initials(me?.name || k.name)}</span>
              <span class="who-text"><b>${me?.name || k.name}</b><span>${me ? k.name : k.kind}</span></span>
              ${icon("chevron")}
            </button>
            <div class="menu ${app.ui.menu ? "open" : ""}" role="menu">
              <div class="menu-title">Switch customer</div>
              ${KITCHENS.map(
                (one) => html`<button role="menuitem" data-act="switch" data-id="${one.id}" class="${one.id === k.id ? "on" : ""}">
                  <span class="avatar ${one.id}">${initials(contact(one.id)?.name || one.name)}</span>
                  <span><b>${one.name}</b><span>${[contact(one.id)?.name, one.kind].filter(Boolean).join(" · ")}</span></span>
                  ${one.id === k.id ? html`<span class="tag ok">${icon("check")}In use</span>` : ""}
                </button>`
              )}
              <div class="menu-foot">${me ? `Demo, no login: you are acting as ${me.name}, ${k.name}.` : `Demo, no login: you are acting for ${k.name}.`} Each customer has its own order book and limits.</div>
            </div>
          </div>
        </div>
      </div>
      <nav class="mobile-nav" aria-label="Main">${NAV.map((n) => link(n, true))}</nav>
    </header>`;
}

// The settings of this customer were refused or never confirmed by the gateway: said on every view, with a way
// to send them again. Until the gateway accepts them, the page neither asks nor orders (core.js, withRules).
function rulesBanner() {
  const refused = app.data.refused;
  if (!refused) return "";
  return html`<div class="verdict stop banner" role="alert">${icon("alert")}<div>
    <b>This customer's settings are not in force</b>
    <p>${ended(plain(refused.message)) || "The gateway did not accept them."} Nothing is asked or ordered until the gateway accepts them.</p>
    <div class="actions"><button class="btn small dark" data-act="push-again" ${app.data.pushing ? "disabled" : ""}>${app.data.pushing ? "Sending…" : "Send them again"}</button><a class="link" href="#/settings">Settings</a></div>
  </div></div>`;
}

function footer() {
  return html`<div class="foot">Demo shop on the Trusted Trade gateway. Customers, people and past orders are made up; prices, stock and every rule come from the gateway. Orders are recorded in this browser's demo order book and commit nobody.
    <span class="foot-links">For developers, the same typed interface: <a href="/docs">REST API pages (OpenAPI)</a> · MCP server at <code>/mcp</code> · <a href="/">the gateway's first pages</a> (request, approvals, kitchen, standing orders, assumptions).</span></div>`;
}

// The result a request just sent is waiting to show (core.js, `reveal`): once it is drawn, its first line goes to
// the top of the window, under the header that stays on screen. Not a smooth scroll: a redraw on the way (the
// answer arriving) would stop it half-way. The request box is left, so the keyboard does not pull the page back.
const REVEAL_GAP = 12;
function revealPending() {
  const id = app.ui.reveal;
  const result = id ? document.getElementById(`result-${id}`) : null;
  if (!result) return; // not drawn here (another view is shown): kept until it is
  app.ui.reveal = null;
  const header = document.querySelector("header.header");
  const top = result.getBoundingClientRect().top + window.scrollY - (header?.offsetHeight || 0) - REVEAL_GAP;
  window.scrollTo(0, Math.max(0, Math.round(top)));
  app.ui.revealed = { id, y: window.scrollY };
  if (document.activeElement?.id === "ask-text") document.activeElement.blur();
}

// A redraw replaces the page. On the same view of the same customer it keeps what a person did to it: the folds
// they opened or closed, where they scrolled to, the field they type in. A toast is no part of it (core.js).
let drawn = null;
setRenderer(() => {
  const root = document.getElementById("app");
  const view = VIEWS[app.route.name];
  const page = [memory.active, app.route.name, app.route.id || ""].join("|");
  const folds = page === drawn ? keepFolds(root) : null;
  const y = window.scrollY;
  const typing = document.activeElement?.matches?.("textarea, input[type=text], input[type=number]");
  const focused = typing ? document.activeElement.id || null : null;
  const caret = focused ? [document.activeElement.selectionStart, document.activeElement.selectionEnd] : null;
  root.innerHTML = String(html`
    ${header()}
    <main class="page">${rulesBanner()}${view.view()}</main>
    ${footer()}
  `);
  drawn = page;
  // Widths a style attribute would carry: the page's Content-Security-Policy allows no inline style.
  for (const bar of root.querySelectorAll("[data-w]")) bar.style.width = `${Math.min(100, Number(bar.dataset.w))}%`;
  view.after?.(root);
  if (folds) restoreFolds(root, folds);
  // A render while someone types (an answer arriving, say) keeps the field they were in, without moving the page.
  if (focused) {
    const again = document.getElementById(focused);
    if (again) {
      again.focus({ preventScroll: true });
      try {
        if (caret && caret[0] !== null) again.setSelectionRange(caret[0], caret[1]);
      } catch {
        // number fields have no caret to restore
      }
    }
  }
  if (folds && window.scrollY !== y) window.scrollTo(0, y);
  revealPending();
});

// ---- start -----------------------------------------------------------------------------------------------

route();
// A newcomer starts at the hotel (core.js, `startingCustomer`); a returning visitor where they were.
const first = startingCustomer(memory.active);
if (first !== memory.active) {
  memory.active = first;
  save();
}
health().then((h) => {
  app.health = h;
  app.healthAsked = true;
  render();
});
load().then(() => VIEWS[app.route.name].enter?.());
