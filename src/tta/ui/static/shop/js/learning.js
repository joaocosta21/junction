// What the agent assumes about a kitchen, and how it learns from the answers it gets.
//
// An assumption never decides on its own. While it is only assumed (from the kind of kitchen or from past
// orders), the agent flags what does not fit it and waits for the buyer before ordering. Once the buyer has
// confirmed it, it narrows the request the gateway gets (for a brand: only products whose name carries the
// brand). Turned off, it is no longer used. All of this is kept in this browser only.

import { ALLERGEN_RULES, allergenName, allergenRule } from "./kitchens.js";

const lower = (s) => String(s || "").toLowerCase();

export function brandRules(learned) {
  return learned.filter((r) => r.kind === "brand" && r.state !== "off");
}

function inScope(rule, line) {
  return !rule.scope || rule.scope.includes(line.product_type);
}

const carriesBrand = (rule, line) => lower(`${line.vendor_name} ${line.name}`).includes(lower(rule.brand));

// The request as the gateway will get it, and the chips that say what the kitchen's own data added to it.
export function prepare(request, kitchen, mine) {
  const out = structuredClone(request);
  const applied = [];
  const s = mine.settings;
  if (s.excluded_allergens?.length) {
    for (const rule of ["STRICT", "DECLARED_ONLY"]) {
      const codes = s.excluded_allergens.filter((code) => allergenRule(s, code) === rule);
      if (codes.length) applied.push({ tone: "info", text: `${ALLERGEN_RULES[rule].name}: no ${codes.map(allergenName).join(", ").toLowerCase()}` });
    }
  }
  if (s.require_confirmed) applied.push({ tone: "info", text: "Confirmed data only" });
  for (const rule of brandRules(mine.learned)) {
    if (rule.state !== "confirmed") continue;
    let used = false;
    for (const line of out.lines) {
      if (line.product_ids?.length || !inScope(rule, line)) continue;
      const terms = new Set([...(line.name_terms || []), lower(rule.brand)]);
      line.name_terms = [...terms];
      used = true;
    }
    if (used) applied.push({ tone: "lime", text: `${rule.brand} only — you confirmed this` });
  }
  return { request: out, applied };
}

// Lines of the offer's first option that do not fit an assumption the buyer has not confirmed yet.
export function review(offer, mine) {
  const first = offer.options?.[0];
  if (!first) return [];
  const flags = [];
  for (const rule of brandRules(mine.learned)) {
    if (rule.state !== "assumed") continue;
    const request = offer.request.lines;
    const off = first.lines.filter((l) => inScope(rule, request[l.request_line_index] || {}) && !carriesBrand(rule, l));
    if (!off.length) continue;
    const vendors = [...new Set(off.map((l) => l.vendor_name))];
    flags.push({ kind: "brand", ruleId: rule.id, brand: rule.brand, vendors, basis: rule.basis });
  }
  return flags;
}

export function confirm(mine, ruleId) {
  const rule = mine.learned.find((r) => r.id === ruleId);
  if (rule) {
    rule.state = "confirmed";
    rule.count = (rule.count || 0) + 1;
    rule.basis = `Confirmed by you${rule.count > 1 ? ` ${rule.count} times` : ""}`;
  }
}

export function dismiss(mine, ruleId) {
  const rule = mine.learned.find((r) => r.id === ruleId);
  if (rule) {
    rule.state = "off";
    rule.basis = "Turned off by you";
  }
}

export function restore(mine, ruleId) {
  const rule = mine.learned.find((r) => r.id === ruleId);
  if (rule) {
    rule.state = "assumed";
    rule.basis = "Back to an assumption";
  }
}
