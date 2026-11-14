// State and helpers shared by every view. The page frame (main.js) sets the renderer.
import { gateway } from "./api.js";
import { day, isoDay } from "./dom.js";
import { memory, mine } from "./store.js";

// `authority` is the gateway's own answer about the rules in force for this kitchen's book, never this
// browser's copy of the settings. `refused` is the last refusal of the settings call, kept until a call succeeds.
// `reorder`: the gateway's "you usually order this" for this customer, read each time the customer is opened or
// switched to, so a dismissal lasts until then (null: none, or the route did not answer).
export const freshData = () => ({ authority: null, refused: null, pushing: false, orders: [], approvals: [], ready: false, problem: null, reorder: null, reorderDismissed: false });

export const app = {
  route: { name: "assistant", id: null },
  data: freshData(),
  ui: { menu: false, toast: null, redraft: {} },
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
const isThisKitchens = (authority) => Boolean(authority?.profile) && authority.profile.display_name === mine().settings.display_name;

// Make this kitchen's settings the rules of its book, trying once more when refused. The rules then shown are the
// gateway's answer. Written into the data of the kitchen that asked, so a switch meanwhile cannot mix two kitchens.
export async function pushKitchen() {
  const data = app.data;
  const settings = mine().settings;
  data.pushing = true;
  let last = null;
  for (let attempt = 1; attempt <= PUSH_ATTEMPTS; attempt++) {
    try {
      data.authority = await api().setKitchen(settings);
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
export async function ensureRules() {
  return app.data.authority || pushKitchen();
}

// Before a request is read or an order confirmed: read the rules back from the gateway, and set them up again when
// its book no longer holds this kitchen's settings (dropped after idling, or the gateway restarted).
export async function verifyRules() {
  const data = app.data;
  if (data.authority && !data.pushing) {
    try {
      const authority = await api().authority();
      if (isThisKitchens(authority)) {
        data.authority = authority;
        return authority;
      }
    } catch (error) {
      if (!rulesLost(error)) return data.authority; // the check itself failed: the gateway's last answer stands
    }
  }
  return pushKitchen();
}

// A call that needs this kitchen's rules: set them up first; when the book lost them meanwhile, set them up again
// and make the call once more. Nothing is ever asked or ordered under rules the gateway did not confirm.
export async function withRules(call) {
  await ensureRules();
  try {
    return await call();
  } catch (error) {
    if (!rulesLost(error)) throw error;
    app.data.authority = null;
    await pushKitchen();
    return call();
  }
}

// Read the rules back from the gateway; when they are not this kitchen's, send the settings again.
async function checkRules(data) {
  if (data.pushing) return; // a push is on its way: its answer is the rules in force
  try {
    const authority = await api().authority();
    if (isThisKitchens(authority)) {
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
    await pushKitchen();
  } catch {
    // kept in app.data.refused and shown on every view
  }
}

export async function refresh() {
  const data = app.data;
  try {
    await checkRules(data);
    const [list, queue] = await Promise.all([api().orders(), api().approvals()]);
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

export function toast(text) {
  app.ui.toast = text;
  render();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    app.ui.toast = null;
    render();
  }, 3200);
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
