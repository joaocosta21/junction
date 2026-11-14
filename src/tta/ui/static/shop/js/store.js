// What the shop remembers in this browser: the kitchen in use, each kitchen's settings, answer preferences,
// what its agent has learned, and the conversation. Orders and approvals themselves live in the gateway.
import { KITCHENS, kitchenById } from "./kitchens.js";

const KEY = "tt-shop-v2"; // v2: nothing is ordered or sent without a click by default
const MAX_TURNS = 8;

function fresh() {
  const kitchens = {};
  for (const k of KITCHENS) {
    kitchens[k.id] = {
      settings: structuredClone(k.settings),
      prefs: structuredClone(k.prefs),
      learned: structuredClone(k.learned),
      thread: [],
    };
  }
  return { active: KITCHENS[0].id, kitchens };
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!saved || !saved.kitchens) return fresh();
    const base = fresh();
    for (const id of Object.keys(base.kitchens)) {
      if (saved.kitchens[id]) base.kitchens[id] = { ...base.kitchens[id], ...saved.kitchens[id] };
    }
    if (saved.active && base.kitchens[saved.active]) base.active = saved.active;
    return base;
  } catch {
    return fresh();
  }
}

export const memory = load();

export function save() {
  try {
    for (const k of Object.values(memory.kitchens)) k.thread = k.thread.slice(-MAX_TURNS);
    localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // Private windows and full storage: the shop still works, it just forgets on reload.
  }
}

export const active = () => kitchenById(memory.active);
export const mine = (id = memory.active) => memory.kitchens[id];

export function resetKitchen(id) {
  const k = kitchenById(id);
  memory.kitchens[id] = {
    settings: structuredClone(k.settings),
    prefs: structuredClone(k.prefs),
    learned: structuredClone(k.learned),
    thread: [],
  };
  save();
}
