// The four demo customers of the shop. Names, addresses, customer numbers and past orders are made up for
// the demonstration. The `settings` block is what the gateway enforces for each kitchen (its buyer profile);
// everything else here lives only in this browser.

export const ROLES = {
  purchasing_manager: "Purchasing manager",
  finance: "Finance",
  dietitian: "Dietitian",
};

export const ALLERGENS = [
  ["AM", "Milk"],
  ["AW", "Cereals with gluten"],
  ["AE", "Eggs"],
  ["AN", "Tree nuts"],
  ["AP", "Peanuts"],
  ["AS", "Sesame"],
  ["AY", "Soya"],
  ["AF", "Fish"],
  ["AC", "Crustaceans"],
  ["UM", "Molluscs"],
  ["BC", "Celery"],
  ["BM", "Mustard"],
  ["NL", "Lupin"],
  ["AU", "Sulphites"],
];
export const allergenName = (code) => (ALLERGENS.find(([c]) => c === code) || [code, code])[1];

// The two allergen rules of the gateway (P-04), in the words the shop uses.
export const ALLERGEN_RULES = {
  DECLARED_ONLY: { name: "Declared only", short: "declared only" },
  STRICT: { name: "Strict", short: "strict" },
};
export const NEW_ALLERGEN_RULE = "STRICT"; // an allergen just added starts on the safer rule

// The rule one excluded allergen is checked under: its own, else the kitchen's general one.
export function allergenRule(settings, code) {
  return settings.allergen_strictness_by_code?.[code] || settings.allergen_strictness || NEW_ALLERGEN_RULE;
}

// The allergen settings as the gateway takes them: every excluded allergen with its own rule, nothing else.
export function withAllergenRules(settings) {
  const excluded = settings.excluded_allergens || [];
  const byCode = Object.fromEntries(excluded.map((code) => [code, allergenRule(settings, code)]));
  return {
    ...settings,
    allergen_strictness: excluded.length ? settings.allergen_strictness || "DECLARED_ONLY" : null,
    allergen_strictness_by_code: byCode,
  };
}

const BASE_SETTINGS = {
  auto_order_enabled: true,
  variable_weight: "APPROVAL",
  deposits: "APPROVAL",
  standing_order_drift_ratio: 0.25,
};

const milk1000 = {
  needed_by: "2026-11-16",
  lines: [{ text: "1,000 litres of lactose-free milk by Monday", product_type: "milk", required_claims: ["FREE_FROM_LACTOSE"], quantity: 1000, unit: "L" }],
};

export const KITCHENS = [
  {
    id: "school",
    name: "Kilo School",
    kind: "School kitchen",
    detail: "Espoo · lunch for 420 pupils",
    customerNo: "554 812",
    address: "Kilonkartanontie 6, 02610 Espoo",
    person: { name: "Päivi Korhonen", title: "Kitchen manager", roles: ["purchasing_manager"] },
    people: { purchasing_manager: "Päivi Korhonen", finance: "Tuomas Aho", dietitian: "Riikka Mäkelä" },
    deliveryDays: "Mon–Fri",
    settings: {
      ...BASE_SETTINGS,
      display_name: "Kilo School",
      max_order_net_eur: 250,
      max_daily_net_eur: 800,
      min_fill_ratio: 1,
      excluded_allergens: ["AN", "AP", "AS"],
      allergen_strictness: "DECLARED_ONLY",
      allergen_strictness_by_code: { AN: "DECLARED_ONLY", AP: "DECLARED_ONLY", AS: "DECLARED_ONLY" },
      substitution_without_approval: "LISTED_BY_SUPPLIER",
      require_confirmed: false,
    },
    prefs: { short: false, alternatives: true, explain: true, autoSend: true },
    examples: [
      { text: "40 litres of lactose-free milk by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "40 litres of lactose-free milk by Monday", product_type: "milk", required_claims: ["FREE_FROM_LACTOSE"], quantity: 40, unit: "L" }] } },
      { text: "20 kg of natural yoghurt by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "20 kg of natural yoghurt by Monday", product_type: "yoghurt", name_terms: ["natural"], quantity: 20, unit: "KG" }] } },
    ],
    learned: [
      { id: "school-nuts", kind: "note", title: "The whole school is nut-free", detail: "Tree nuts, peanuts and sesame are kept out of every order. Special diets of single pupils are handled by the dietitian, not here.", basis: "Set by the kitchen manager", state: "confirmed", count: 0 },
      { id: "school-monday", kind: "pattern", title: "Dairy arrives on Mondays", detail: "Milk and yoghurt have been delivered on each of the last four Mondays.", basis: "From your past orders", state: "assumed", count: 0 },
    ],
    history: [
      { date: "2026-11-09", lines: [["Valio lactose free milk drink 1 l", 40, "pcs", 42.0], ["Valio natural yoghurt 1 kg lactose free", 20, "pcs", 33.8]] },
      { date: "2026-11-02", lines: [["Valio lactose free milk drink 1 l", 38, "pcs", 39.9], ["Valio natural yoghurt 1 kg lactose free", 18, "pcs", 30.42]] },
      { date: "2026-10-26", lines: [["Valio lactose free milk drink 1 l", 40, "pcs", 42.0], ["Pirkka grated cheese 1 kg", 6, "pcs", 47.1]] },
      { date: "2026-10-19", lines: [["Valio lactose free milk drink 1 l", 42, "pcs", 44.1]] },
    ],
  },
  {
    id: "ward",
    name: "City Hospital, Ward 4",
    kind: "Hospital allergy ward",
    detail: "Espoo · 36 beds",
    customerNo: "554 097",
    address: "Turuntie 150, 02740 Espoo",
    person: { name: "Jussi Nieminen", title: "Ward purchasing", roles: ["purchasing_manager"] },
    people: { purchasing_manager: "Jussi Nieminen", finance: "Anna Virta", dietitian: "Sari Lehto" },
    deliveryDays: "Mon–Sat",
    settings: {
      ...BASE_SETTINGS,
      display_name: "City Hospital, Ward 4",
      max_order_net_eur: 500,
      max_daily_net_eur: 1500,
      min_fill_ratio: 1,
      excluded_allergens: ["AM", "AW"],
      allergen_strictness: "STRICT",
      allergen_strictness_by_code: { AM: "STRICT", AW: "STRICT" },
      substitution_without_approval: "NONE",
      require_confirmed: true,
    },
    prefs: { short: false, alternatives: false, explain: true, autoSend: true },
    examples: [
      {
        text: "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
        request: { needed_by: "2026-11-16", require_confirmed: true, lines: [{ text: "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only", product_type: "plant_drink", quantity: 200, unit: "L", exclude_allergens: ["AM", "AW"], allergen_strictness: "STRICT" }] },
      },
      { text: "50 litres of soya drink by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "50 litres of soya drink by Monday", product_type: "plant_drink", name_terms: ["soya"], quantity: 50, unit: "L" }] } },
    ],
    learned: [
      { id: "ward-alpro", kind: "pattern", title: "Soya drink is usually Alpro", detail: "Four of the last five plant-drink orders were Alpro No Sugars soya drink.", basis: "From your past orders", state: "assumed", count: 0 },
    ],
    history: [
      { date: "2026-11-09", lines: [["Alpro No Sugars Soya drink 1L", 180, "pcs", 361.8]] },
      { date: "2026-11-02", lines: [["Alpro No Sugars Soya drink 1L", 200, "pcs", 402.0]] },
      { date: "2026-10-27", lines: [["Oddlygood oat drink 1 l gluten free", 120, "pcs", 226.8]] },
      { date: "2026-10-26", lines: [["Alpro No Sugars Soya drink 1L", 190, "pcs", 381.9]] },
    ],
  },
  {
    id: "hotel",
    name: "Harbourside Hotel",
    kind: "Hotel kitchen",
    detail: "Helsinki · breakfast and à la carte",
    customerNo: "610 245",
    address: "Satamakatu 4, 00160 Helsinki",
    person: { name: "Hanna Laine", title: "Purchasing manager", roles: ["purchasing_manager"] },
    people: { purchasing_manager: "Hanna Laine", finance: "Mikko Saari", dietitian: "Leena Koski" },
    deliveryDays: "Mon–Sat",
    settings: {
      ...BASE_SETTINGS,
      display_name: "Harbourside Hotel",
      max_order_net_eur: 750,
      max_daily_net_eur: 3000,
      min_fill_ratio: 0.9,
      excluded_allergens: [],
      allergen_strictness: null,
      substitution_without_approval: "SAME_CATEGORY",
      require_confirmed: false,
    },
    prefs: { short: false, alternatives: true, explain: false, autoSend: true },
    examples: [
      { text: "1,000 litres of lactose-free milk by Monday", request: milk1000 },
      { text: "30 litres of cream by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "30 litres of cream by Monday", product_type: "cream", quantity: 30, unit: "L" }] } },
    ],
    learned: [
      { id: "hotel-price", kind: "note", title: "Price comes first", detail: "Mixing brands in one order is fine for this kitchen.", basis: "Assumed for hotel kitchens", state: "assumed", count: 0 },
    ],
    history: [
      { date: "2026-11-13", lines: [["Arla Semi skimmed milkdrink 1 L lactose free", 300, "pcs", 744.0]] },
      { date: "2026-11-11", lines: [["Arla Pro Cooking cream 10% 1 L", 30, "pcs", 99.3], ["Valio butter 500 g", 20, "pcs", 98.0]] },
      { date: "2026-11-06", lines: [["Arla Semi skimmed milkdrink 1 L lactose free", 280, "pcs", 694.4]] },
    ],
  },
  {
    id: "bakery",
    name: "Kallio Bakery",
    kind: "Bakery and café",
    detail: "Helsinki · 2 shops",
    customerNo: "611 530",
    address: "Fleminginkatu 12, 00530 Helsinki",
    person: { name: "Marko Heikkinen", title: "Owner", roles: ["purchasing_manager", "finance"] },
    people: { purchasing_manager: "Marko Heikkinen", finance: "Marko Heikkinen", dietitian: "No dietitian named" },
    deliveryDays: "Mon–Sat",
    settings: {
      ...BASE_SETTINGS,
      display_name: "Kallio Bakery",
      max_order_net_eur: 50,
      max_daily_net_eur: 400,
      min_fill_ratio: 1,
      excluded_allergens: [],
      allergen_strictness: null,
      substitution_without_approval: "SAME_CATEGORY",
      require_confirmed: false,
    },
    prefs: { short: true, alternatives: true, explain: false, autoSend: true },
    examples: [
      { text: "10 litres of whipping cream by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "10 litres of whipping cream by Monday", product_type: "cream", name_terms: ["whipping"], quantity: 10, unit: "L" }] } },
      { text: "10 litres of milk by Monday", request: { needed_by: "2026-11-16", lines: [{ text: "10 litres of milk by Monday", product_type: "milk", quantity: 10, unit: "L" }] } },
    ],
    learned: [
      { id: "bakery-brand", kind: "brand", brand: "Valio", scope: ["milk", "cream", "butter", "quark", "yoghurt", "sour_milk"], title: "Keep Valio for dairy", detail: "Bakeries usually keep one dairy brand: another brand's fat and protein content changes how doughs and creams behave. Until you confirm it, the agent only flags other brands and does not filter them out.", basis: "Assumed for bakeries", state: "assumed", count: 0 },
    ],
    history: [
      { date: "2026-11-13", lines: [["Valio whipping cream 1 l lactose free", 12, "pcs", 41.4], ["Valio milk 1 l", 20, "pcs", 18.6]] },
      { date: "2026-11-11", lines: [["Valio whipping cream 1 l lactose free", 10, "pcs", 34.5]] },
      { date: "2026-11-06", lines: [["Valio whipping cream 1 l lactose free", 12, "pcs", 41.4], ["Valio butter 500 g", 10, "pcs", 49.0]] },
    ],
  },
];

export const kitchenById = (id) => KITCHENS.find((k) => k.id === id) || KITCHENS[0];
