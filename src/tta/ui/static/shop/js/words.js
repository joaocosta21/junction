// The gateway's sentences in the words a buyer reads: no codes, no field names, no profile ids.
// The gateway is being reworded at its source; this keeps the page readable meanwhile, and touches only
// tokens a person would not say. Numbers, amounts, dates and rule ids with their words stay as they are.
import { ALLERGENS } from "./kitchens.js";
import { active } from "./store.js";

const CODES = new Map(ALLERGENS);
const CODE = `(?:${ALLERGENS.map(([code]) => code).join("|")})`;
// An allergen code only where a sentence names allergens ("excludes AN, AP and AS"): a bare two-letter word
// could be part of a company name.
const ALLERGEN_LIST = new RegExp(
  `\\b(excludes?|contains?|declares?|free from|without|no)(:?\\s+)(${CODE}(?:(?:,\\s*|\\s+and\\s+|\\s+or\\s+)${CODE})*)\\b`,
  "g"
);
const ONE_CODE = new RegExp(`\\b${CODE}\\b`, "g");
// The code the gateway puts after an allergen's name ("tree nuts (AN)"): a person reads the name alone.
const CODE_AFTER_NAME = new RegExp(`\\s\\(${CODE}\\)`, "g");
const SPELLED = (token) => token.toLowerCase().replaceAll("_", " ");

const REWRITES = [
  [CODE_AFTER_NAME, () => ""],
  [ALLERGEN_LIST, (_, verb, gap, list) => `${verb}${gap}${list.replace(ONE_CODE, (code) => CODES.get(code).toLowerCase())}`],
  [/\bFREE_FROM_([A-Z_]+)\b/g, (_, what) => `${SPELLED(what)} free`],
  [/\bDECLARED_ONLY\b/g, () => "declared only"],
  [/\bSTRICT\b/g, () => "strict"],
  [/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g, (token) => SPELLED(token)],
  [/\b(?:option )?opt_(\d+)\b/g, (_, n) => `option ${n}`],
  [/\b[a-z]+(?:_[a-z]+)+\b/g, (token) => SPELLED(token)],
  [/\bin replay\b/gi, () => "with recorded data"],
  [/\breplay\b/gi, () => "recorded data"],
  [/\bfill ratio\b/gi, () => "share of the quantity covered"],
  [/\bverdict\b/gi, () => "decision"],
];

// "profile my-kitchen" names the book's profile, not the customer. Profile ids always hold a hyphen.
const PROFILE_ID = /\b(?:the )?profile [a-z][a-z0-9]*-[a-z0-9-]+\b/g;

export function plain(text, name = active().name) {
  if (text === null || text === undefined) return "";
  let out = String(text).replace(PROFILE_ID, name);
  for (const [pattern, change] of REWRITES) out = out.replace(pattern, change);
  return out;
}

// Sentences, split where a full stop, ! or ? is followed by a space and a capital: "€2.48" stays whole.
export function sentences(text) {
  return String(text || "")
    .split(/(?<=[.!?])\s+(?=[A-Z"“])/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// A refused settings form as a person reads it. The gateway names the form and the field before its sentence
// ("Your kitchen: excluded_allergens: The allergen exclusions of Kilo School are set by its dietitian and cannot
// be removed here: …"): the page shows the sentence, where the person is. Any other field keeps its name.
const FORM_NAME = /^Your kitchen:\s*/;
const ALLERGEN_FIELD = /(^|;\s*)(?:excluded_allergens|allergen_strictness(?:_by_code)?):\s*/g;
export const refusalWords = (text) => String(text || "").replace(FORM_NAME, "").replace(ALLERGEN_FIELD, "$1");

// One sentence, closed with a full stop when it has no end mark, so that two of them never run together.
export function ended(text) {
  const t = String(text || "").trim();
  return !t || /[.!?…]$/.test(t) ? t : `${t}.`;
}
