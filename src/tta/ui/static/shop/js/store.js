// What the shop remembers in this browser: the kitchen in use, each kitchen's settings as the buyer wants them
// (the rules in force are the gateway's answer, never this copy), answer preferences, what its agent has
// learned, and the latest results. Orders and approvals themselves live in the gateway.
import { KITCHENS, kitchenById } from "./kitchens.js";

// v3: one "Confirm order" button and no preference that sends by itself. A new key, so a browser that opened
// an earlier version does not keep its saved defaults (saved values win over new defaults at load).
const KEY = "tt-shop-v3";
const OLD_KEYS = ["tt-shop-v1", "tt-shop-v2"];
const MAX_TURNS = 8;

function forgetOldVersions() {
  try {
    for (const key of OLD_KEYS) localStorage.removeItem(key);
  } catch {
    // no storage in this window: nothing old to forget
  }
}

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
  forgetOldVersions();
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
