// The page frame: header with the customer switcher, hash routing, events, and the render function.
import { health } from "./api.js";
import { app, handlers, nextDeliveryDay, on, pendingApprovals, pushKitchen, refresh, render, setRenderer, toast } from "./core.js";
import { html, initials, isoDay, shortDate } from "./dom.js";
import { icon } from "./icons.js";
import { KITCHENS, kitchenById } from "./kitchens.js";
import { active, memory, save } from "./store.js";
import * as approvals from "./views/approvals.js";
import * as assistant from "./views/assistant.js";
import * as deliveries from "./views/deliveries.js";
import * as orders from "./views/orders.js";
import * as settings from "./views/settings.js";

const VIEWS = { assistant, approvals, orders, deliveries, settings };
const NAV = [
  ["assistant", "#/", "Assistant"],
  ["deliveries", "#/deliveries", "Deliveries"],
  ["approvals", "#/approvals", "Approvals"],
  ["orders", "#/orders", "Orders"],
  ["settings", "#/settings", "Settings"],
];

// ---- loading and switching customer ----------------------------------------------------------------------

async function load() {
  app.data.ready = false;
  render();
  try {
    await pushKitchen();
    app.data.problem = null;
  } catch (error) {
    app.data.problem = error;
  }
  app.data.ready = true;
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
  app.data = { authority: null, orders: [], approvals: [], ready: false, problem: null };
  settings.forget();
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  await load();
  const k = kitchenById(id);
  toast(`Now shopping as ${k.person.name}, ${k.name}`);
}

on("menu", () => {
  app.ui.menu = !app.ui.menu;
  render();
});
on("switch", (el) => switchKitchen(el.dataset.id));

// ---- events: one listener per kind, routed by data-act / data-change / data-input --------------------------

function dispatch(event, el) {
  const fn = handlers[el.dataset.act];
  if (!fn) return;
  event.preventDefault();
  Promise.resolve(fn(el, event)).catch((error) => {
    console.error(error);
    toast(error.message || "Something went wrong.");
  });
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
  render();
  window.scrollTo(0, 0);
  VIEWS[app.route.name].enter?.();
});

// ---- frame -----------------------------------------------------------------------------------------------

function modeLabel() {
  const h = app.health;
  if (!h) return "Gateway";
  return h.mode === "replay" ? "Replay · recorded Valio Aimo data" : "Live · Valio Aimo mock API";
}

function header() {
  const k = active();
  const waiting = pendingApprovals().length;
  const next = nextDeliveryDay();
  const link = ([name, href, label], mobile) =>
    html`<a href="${href}" class="${app.route.name === name ? "on" : ""}">${label}${
      name === "approvals" && waiting ? (mobile ? ` (${waiting})` : html`<span class="badge">${waiting}</span>`) : ""
    }</a>`;
  return html`
    <div class="strip">
      <a class="tab" href="#/deliveries" title="Delivery wholesale">${icon("truck")}<span>Delivery wholesale</span></a>
      <a class="tab on" href="#/">${icon("agent")}<span>Buying agent</span></a>
      <span class="mode">${modeLabel()}</span>
    </div>
    <header class="header">
      <div class="header-in">
        <a class="brand" href="#/"><b>Tukku</b><span>Trusted Trade</span></a>
        <nav class="nav" aria-label="Main">${NAV.map((n) => link(n, false))}</nav>
        <div class="tools">
          <a class="date-chip" href="#/deliveries" title="Next delivery day">${icon("calendar")}<span>${shortDate(isoDay(next))}</span></a>
          <a class="icon-btn" href="#/approvals" title="Waiting for approval">${icon("bell")}${waiting ? html`<span class="badge">${waiting}</span>` : ""}</a>
          <div class="who">
            <button class="who-btn" data-act="menu" aria-haspopup="menu" aria-expanded="${String(app.ui.menu)}">
              <span class="avatar ${k.id}">${initials(k.person.name)}</span>
              <span class="who-text"><b>${k.person.name}</b><span>${k.name}</span></span>
              ${icon("chevron")}
            </button>
            <div class="menu ${app.ui.menu ? "open" : ""}" role="menu">
              <div class="menu-title">Switch customer</div>
              ${KITCHENS.map(
                (one) => html`<button role="menuitem" data-act="switch" data-id="${one.id}" class="${one.id === k.id ? "on" : ""}">
                  <span class="avatar ${one.id}">${initials(one.person.name)}</span>
                  <span><b>${one.person.name}</b><span>${one.name} · ${one.kind}</span></span>
                  ${one.id === k.id ? html`<span class="tag ok">${icon("check")}In use</span>` : ""}
                </button>`
              )}
              <div class="menu-foot">Demo customers, no login. Each one has its own order book, limits and approvers.</div>
            </div>
          </div>
        </div>
      </div>
      <nav class="mobile-nav" aria-label="Main">${NAV.map((n) => link(n, true))}</nav>
    </header>`;
}

function footer() {
  return html`<div class="foot">Demo shop on the Trusted Trade gateway. Customers, people and past orders are made up; prices, stock and every rule come from the gateway. Orders are recorded in this browser's demo order book and commit nobody.</div>`;
}

setRenderer(() => {
  const root = document.getElementById("app");
  const view = VIEWS[app.route.name];
  const typing = document.activeElement?.matches?.("textarea, input[type=text], input[type=number]");
  const focused = typing ? document.activeElement.id || null : null;
  const caret = focused ? [document.activeElement.selectionStart, document.activeElement.selectionEnd] : null;
  root.innerHTML = String(html`
    ${header()}
    <main class="page">${view.view()}</main>
    ${footer()}
    ${app.ui.toast ? html`<div class="toast" role="status">${app.ui.toast}</div>` : ""}
  `);
  // Widths a style attribute would carry: the page's Content-Security-Policy allows no inline style.
  for (const bar of root.querySelectorAll("[data-w]")) bar.style.width = `${Math.min(100, Number(bar.dataset.w))}%`;
  view.after?.(root);
  // A render while someone types (an answer arriving, say) keeps the field they were in.
  if (focused) {
    const again = document.getElementById(focused);
    if (again) {
      again.focus();
      try {
        if (caret && caret[0] !== null) again.setSelectionRange(caret[0], caret[1]);
      } catch {
        // number fields have no caret to restore
      }
    }
  }
});

// ---- start -----------------------------------------------------------------------------------------------

route();
health().then((h) => {
  app.health = h;
  render();
});
load().then(() => VIEWS[app.route.name].enter?.());
