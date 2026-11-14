// State and helpers shared by every view. The page frame (main.js) sets the renderer.
import { gateway } from "./api.js";
import { day, isoDay } from "./dom.js";
import { memory, mine } from "./store.js";

export const app = {
  route: { name: "assistant", id: null },
  data: { authority: null, orders: [], approvals: [], ready: false, problem: null },
  ui: { menu: false, toast: null },
  health: null,
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

export async function pushKitchen() {
  app.data.authority = await api().setKitchen(mine().settings);
  return app.data.authority;
}

export async function refresh() {
  try {
    const [list, queue] = await Promise.all([api().orders(), api().approvals()]);
    app.data.orders = list;
    app.data.approvals = queue;
    app.data.problem = null;
  } catch (error) {
    app.data.problem = error;
  }
  render();
}

// The day the data is about: the gateway's data clock (pinned to the recording in replay), else today.
export function dataToday() {
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
