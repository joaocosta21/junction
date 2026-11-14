// Small HTML helpers. Every interpolated value is escaped unless it was built with html`` or raw().

class Safe {
  constructor(text) { this.text = text; }
  toString() { return this.text; }
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function part(value) {
  if (value === null || value === undefined || value === false) return "";
  if (value instanceof Safe) return value.text;
  if (Array.isArray(value)) return value.map(part).join("");
  return esc(value);
}

export function html(strings, ...values) {
  let out = "";
  strings.forEach((s, i) => {
    out += s;
    if (i < values.length) out += part(values[i]);
  });
  return new Safe(out);
}

export const raw = (text) => new Safe(text);

// ---- formatting -----------------------------------------------------------------------------------

const EUR = new Intl.NumberFormat("fi-FI", { style: "currency", currency: "EUR" });
const NUM = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const money = (n) => (n === null || n === undefined ? "–" : EUR.format(Number(n)));
export const num = (n) => NUM.format(Number(n));

// "2026-11-16" or an ISO time -> a Date at local midnight of that calendar day (the shop shows Helsinki days).
export function day(value) {
  const [y, m, d] = String(value).slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}
export const isoDay = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export const shortDate = (value) => {
  const d = day(value);
  return `${WEEKDAY[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
};
export const longDate = (value) => {
  const d = day(value);
  return `${WEEKDAY[d.getDay()]} ${d.getDate()} ${MONTH[d.getMonth()]}`;
};
export const monthName = (date) => `${["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][date.getMonth()]} ${date.getFullYear()}`;

// Clock time as the data states it ("2026-11-15T17:00:00+02:00" -> "Sun 15.11. 17:00").
export function cutoff(value) {
  if (!value) return "";
  const time = String(value).slice(11, 16);
  return `${shortDate(value)} ${time}`;
}

export function clock(value) {
  const d = new Date(value);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

// A moment of the real clock (an audit event's stamp) in this browser's time: "Sat 14.11. 18:03".
export const realTime = (value) => `${shortDate(isoDay(new Date(value)))} ${clock(value)}`;

// An instant as the gateway states it, in its own offset: "2026-11-12T14:15:00+02:00" -> "Thu 12 Nov 2026, 14:15
// (UTC+02:00)". Read from the text, so the browser's time zone never moves it.
const OFFSET = /([+-]\d{2}:\d{2}|Z)$/;
export function instant(value) {
  const text = String(value || "");
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text)) return text;
  const offset = text.match(OFFSET)?.[1];
  const zone = !offset ? "" : offset === "Z" ? " (UTC)" : ` (UTC${offset})`;
  return `${longDate(text)} ${text.slice(0, 4)}, ${text.slice(11, 16)}${zone}`;
}

const UNITS = { ST: "pcs", KPL: "pcs", KI: "crt", KG: "kg", L: "l", PAK: "pac", PS: "bag", RS: "box", PLO: "bot" };
export const unit = (code) => UNITS[code] || String(code || "").toLowerCase();

export function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

// A short word for a product's picture tile, from its product type or its name.
export function tile(line) {
  const n = (line.name || "").toLowerCase();
  for (const [word, label] of [["cream", "Cream"], ["milk", "Milk"], ["yog", "Yog"], ["butter", "Butter"], ["oat", "Oat"], ["soy", "Soya"], ["quark", "Quark"], ["cheese", "Chs"], ["almond", "Alm"], ["drink", "Drink"]]) {
    if (n.includes(word)) return label;
  }
  return (line.vendor_name || "Item").split(/\s+/)[0].slice(0, 5);
}

export function titleCase(text) {
  return String(text).toLowerCase().replace(/(^|[\s/-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase());
}
