// State and helpers shared by every view. The page frame (main.js) sets the renderer.
import { gateway } from "./api.js";
import { day, isoDay } from "./dom.js";
import { kitchenById } from "./kitchens.js";
import { memory, mine } from "./store.js";

// `authority` is the gateway's own answer about the rules in force for this kitchen's book, never this
// browser's copy of the settings. `refused` is the last refusal of the settings call, kept until a call succeeds.
// `reorder`: the gateway's "you usually order this" for this customer, read each time the customer is opened or
// switched to, so a dismissal lasts until then (null: none, or the route did not answer).
export const freshData = () => ({ authority: null, refused: null, pushing: false, orders: [], approvals: [], ready: false, problem: null, reorder: null, reorderDismissed: false });

export const app = {
  route: { name: "assistant", id: null },
  data: freshData(),
  ui: { menu: false, redraft: {}, reveal: null, revealed: null, toBox: false },
  health: null, // the gateway's GET /healthz answer, null when it did not answer
  healthAsked: false,
};

let renderer = () => {};
export const setRenderer = (fn) => {
  renderer = fn;
};
export const render = () => renderer();

export const handlers = {};
export function on(name, fn) {
  handlers[name] = fn;
}

export const api = () => gateway(memory.active);

// A request belongs to the customer that was active when it was sent. `sender()` is taken once, as the request is
// sent, and every later step of that request asks it instead of the page: its gateway (that customer's order book),
// its settings and what its agent learned, and the rules the gateway confirmed for it. A switch of customer while
// the request is on its way then changes nothing of it: its answer is made under its own customer's rules and kept
// in that customer's results, which only that customer's page draws.
export function sender() {
  const id = memory.active;
  return {
    id,
    kitchen: kitchenById(id),
    data: app.data, // the page data of the customer as it was opened: the rules in force are read into it
    api: () => gateway(id),
    mine: () => mine(id), // read each time: a save or a reset makes new lists
    shown: () => memory.active === id, // the page shows this customer now
  };
}

// The page's own figures, written as the gateway writes them in its sentences ("€1,083.39"): one format on a page,
// from this one function.
const EUR = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR" });
export const money = (n) => (n === null || n === undefined ? "–" : EUR.format(Number(n)));

// A newcomer starts at the hotel, whose first example is the brief's own sentence. Decided once per browser, under a
// key of its own; after that the customer last used is kept. A window without storage starts there every time.
export const FIRST_CUSTOMER = "hotel";
const WELCOMED = "tt-shop-welcomed";
export function startingCustomer(saved) {
  try {
    if (localStorage.getItem(WELCOMED)) return saved;
    localStorage.setItem(WELCOMED, "1");
  } catch {
    // no storage in this window: every load is a newcomer's
  }
  return FIRST_CUSTOMER;
}

// ---- the rules in force -------------------------------------------------------------------------------------

const PUSH_ATTEMPTS = 2;
const PUSH_RETRY_MS = 600;
const OFFER_CHANGED = /offer-(expired|stale)$/;
const wait = (ms) => new Promise((done) => setTimeout(done, ms));

// The gateway's 409 for a book whose settings never arrived (tta.ui.shop_api): GET /kitchen, a reading, an offer
// and an order all answer it rather than apply another customer's rules.
const NOT_RECEIVED = "settings-not-received";

// A 409 that is not about the offer: the book lost this kitchen's settings, or never had them (a restart, an idle
// book dropped). The answer to either is to send the settings again.
export const rulesLost = (error) => {
  if (error?.status !== 409) return false;
  const type = String(error.problem?.type || "");
  return type === NOT_RECEIVED || !OFFER_CHANGED.test(type);
};

// The book's answer is this kitchen's settings, not a book that started again from the defaults ("My kitchen").
const isThisKitchens = (authority, who) => Boolean(authority?.profile) && authority.profile.display_name === who.mine().settings.display_name;

// Make this kitchen's settings the rules of its book, trying once more when refused. The rules then shown are the
// gateway's answer. Sent to the book of the kitchen that asked and written into its data (`who`, the customer in use
// when none is given), so a switch meanwhile cannot mix two kitchens.
export async function pushKitchen(who = sender()) {
  const data = who.data;
  const settings = who.mine().settings;
  data.pushing = true;
  let last = null;
  for (let attempt = 1; attempt <= PUSH_ATTEMPTS; attempt++) {
    try {
      data.authority = await who.api().setKitchen(settings);
      data.refused = null;
      data.pushing = false;
      return data.authority;
    } catch (error) {
      last = error;
      if (attempt < PUSH_ATTEMPTS) await wait(PUSH_RETRY_MS);
    }
  }
  data.authority = null;
  data.refused = last;
  data.pushing = false;
  throw last;
}

// The rules in force, set up first when the gateway has not confirmed them.
export async function ensureRules(who = sender()) {
  return who.data.authority || pushKitchen(who);
}

// Before a request is read or an order confirmed: read the rules back from the gateway, and set them up again when
// its book no longer holds this kitchen's settings (dropped after idling, or the gateway restarted). `who`: the
// customer the request was sent for.
export async function verifyRules(who = sender()) {
  const data = who.data;
  if (data.authority && !data.pushing) {
    try {
      const authority = await who.api().authority();
      if (isThisKitchens(authority, who)) {
        data.authority = authority;
        return authority;
      }
    } catch (error) {
      if (!rulesLost(error)) return data.authority; // the check itself failed: the gateway's last answer stands
    }
  }
  return pushKitchen(who);
}

// A call that needs this kitchen's rules: set them up first; when the book lost them meanwhile, set them up again
// and make the call once more. Nothing is ever asked or ordered under rules the gateway did not confirm. `who`: the
// customer the request was sent for; the call is made on that customer's gateway (`who.api()`).
export async function withRules(call, who = sender()) {
  await ensureRules(who);
  try {
    return await call();
  } catch (error) {
    if (!rulesLost(error)) throw error;
    who.data.authority = null;
    await pushKitchen(who);
    return call();
  }
}

// Read the rules back from the gateway; when they are not this kitchen's, send the settings again.
async function checkRules(who) {
  const data = who.data;
  if (data.pushing) return; // a push is on its way: its answer is the rules in force
  try {
    const authority = await who.api().authority();
    if (isThisKitchens(authority, who)) {
      data.authority = authority;
      return;
    }
  } catch (error) {
    if (!rulesLost(error)) return; // the gateway did not answer: keep its last answer, refresh() shows the problem
  }
  if (data !== app.data) return;
  data.authority = null;
  if (data.refused) return; // just refused twice: the banner offers to send again, and so does the next request
  try {
    await pushKitchen(who);
  } catch {
    // kept in app.data.refused and shown on every view
  }
}

// The orders and approvals of the customer the page shows, read from that customer's book whatever is switched to
// while the calls are on their way.
export async function refresh() {
  const who = sender();
  const data = who.data;
  try {
    await checkRules(who);
    const [list, queue] = await Promise.all([who.api().orders(), who.api().approvals()]);
    data.orders = list;
    data.approvals = queue;
    data.problem = null;
  } catch (error) {
    data.problem = error;
  }
  render();
}

// The day the data is about: the gateway's data clock as /healthz states it (the recording's instant, a demo clock
// we chose, or Valio Aimo's server time), else the latest the gateway stated on an order or offer, else today.
export function dataToday() {
  const now = app.health?.clock?.now;
  if (now) return day(now);
  const stamps = app.data.orders.map((o) => o.created_at);
  for (const t of mine().thread) if (t.offer?.time_now) stamps.push(t.offer.time_now);
  const latest = stamps.sort().at(-1);
  return latest ? day(latest) : day(isoDay(new Date()));
}

export function nextDeliveryDay() {
  const next = new Date(dataToday());
  do next.setDate(next.getDate() + 1);
  while (next.getDay() === 0);
  return next;
}

export const pendingApprovals = () => app.data.approvals.filter((a) => a.status === "PENDING");

// A toast comes and goes without redrawing the page: it lives in an element of its own beside the page (#toasts in
// the shell), so nothing a person opened or scrolled to is touched when it is shown or when it expires.
const TOAST_MS = 3200;
function toastHost() {
  if (typeof document === "undefined") return null;
  const host = document.getElementById("toasts");
  if (host) return host;
  const made = document.createElement("div");
  made.id = "toasts";
  document.body.append(made);
  return made;
}

export function toast(text, ms = TOAST_MS) {
  clearTimeout(toast.timer);
  const host = toastHost();
  if (!host) return;
  host.replaceChildren();
  if (!text) return;
  const note = document.createElement("div");
  note.className = "toast";
  note.setAttribute("role", "status");
  note.textContent = text;
  host.append(note);
  toast.timer = setTimeout(() => note.remove(), ms);
}

// ---- what a redraw keeps ------------------------------------------------------------------------------------
// A redraw replaces the page, and a fold a person opened or closed must stay as they left it. A fold is known by
// where it is (the nearest element with an id: a result card, a suggestion), its words, and its place among the
// folds with the same words there. A fold whose summary carries `data-act` is drawn from the page's own state (the
// clock strip) and is left to it.
function folds(root) {
  const seen = new Map();
  const found = [];
  for (const el of root.querySelectorAll("details")) {
    const summary = el.querySelector(":scope > summary");
    if (!summary || summary.dataset.act) continue;
    const place = `${el.parentElement?.closest("[id]")?.id || ""}|${summary.textContent.trim()}`;
    const nth = seen.get(place) || 0;
    seen.set(place, nth + 1);
    found.push([`${place}|${nth}`, el]);
  }
  return found;
}
export const keepFolds = (root) => new Map(folds(root).map(([key, el]) => [key, el.open]));
export function restoreFolds(root, kept) {
  for (const [key, el] of folds(root)) {
    if (kept.has(key) && el.open !== kept.get(key)) el.open = kept.get(key);
  }
}

// The result the next redraw brings to the top of the window: a request that was just sent (main.js scrolls once the
// result is drawn). `again`: its answer has arrived; the page goes back to it only if the person has not scrolled
// away since, so that somebody reading further down is not pulled back.
export function reveal(id, { again = false } = {}) {
  if (again) {
    const shown = app.ui.revealed;
    if (!shown || shown.id !== id || typeof window === "undefined" || Math.abs(window.scrollY - shown.y) > 2) return;
  }
  app.ui.reveal = id;
}

// "New request" on the newest result, and the key "/" (main.js): the next redraw brings the request box back under
// the header and puts the cursor in it, so the next sentence is one keystroke away. An answer still on its way then
// leaves the page where the person is typing (`revealed` is forgotten, so `reveal(…, { again })` does nothing).
export function toRequestBox() {
  app.ui.toBox = true;
  app.ui.reveal = null;
  app.ui.revealed = null;
}

// Spend that counts against today's limit: orders of the data clock's day that are ordered or waiting.
export function spendToday() {
  const today = isoDay(dataToday());
  return app.data.orders
    .filter((o) => ["ORDERED", "PENDING_APPROVAL"].includes(o.status) && String(o.created_at).slice(0, 10) === today)
    .reduce((sum, o) => sum + Number(o.option?.totals?.net || 0), 0);
}

// The latest delivery date of an option's lines: the day the whole order can be there.
export function deliveryOf(option) {
  const dates = (option?.lines || []).map((l) => l.availability?.available_date).filter(Boolean).sort();
  return dates.at(-1) || null;
}
