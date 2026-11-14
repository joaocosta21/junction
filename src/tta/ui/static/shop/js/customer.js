// Who the shop's customer is, as the gateway answers it (GET /shop/api/customer): the person signed in, who holds
// each role, the usual products and the synthetic past orders, all from the customer file (src/tta/customers/data/).
// Nothing here is typed in: until the route answers, the page names nobody and shows no history.
import { gateway } from "./api.js";
import { app, render } from "./core.js";
import { memory, mine } from "./store.js";

const views = {}; // kitchen id -> the route's answer; a customer file does not change while the page is open
const problems = {}; // kitchen id -> the last refusal, until a call succeeds
const pending = {}; // kitchen id -> the call on its way

// The customer of this kitchen, read once. Rejects with the gateway's refusal, which is kept for the views to say.
export function loadCustomer(id = memory.active) {
  if (views[id]) return Promise.resolve(views[id]);
  pending[id] ||= gateway(id)
    .customer()
    .then((view) => {
      views[id] = view;
      delete problems[id];
      return view;
    })
    .catch((error) => {
      problems[id] = error;
      throw error;
    })
    .finally(() => {
      delete pending[id];
      render();
    });
  return pending[id];
}

export const customerView = (id = memory.active) => views[id] || null;
export const customerProblem = (id = memory.active) => problems[id] || null;
export const customerKnown = (id = memory.active) => Boolean(views[id]);
export const customerOf = (id = memory.active) => views[id]?.customer || null;
// The route's own sentence that the customer is made up: shown where the history is.
export const customerNote = (id = memory.active) => views[id]?.note || "";

// The person signed in on this page: the customer file's contact.
export const contact = (id = memory.active) => customerOf(id)?.contact || null;
// Who holds each role at this customer, by name. Empty until the route answers.
export const people = (id = memory.active) => customerOf(id)?.people || {};
// The roles the person signed in holds: those the customer file names them for (the bakery's owner holds all three).
export function myRoles(id = memory.active) {
  const c = customerOf(id);
  if (!c) return [];
  return Object.entries(c.people || {}).filter(([, name]) => name === c.contact?.name).map(([role]) => role);
}

// ---- products by name: the customer file names products by id only ---------------------------------------------

// The names the gateway has given this page for products: lines of offers and orders, suggestions, products left
// out. A product the page has not met yet is shown by its id and its product type.
function knownNames() {
  const names = new Map();
  const add = (item) => {
    if (item?.product_id && item.name) names.set(String(item.product_id), item.name);
  };
  for (const turn of mine().thread) {
    for (const option of turn.offer?.options || []) (option.lines || []).forEach(add);
    (turn.offer?.suggestions || []).forEach(add);
    (turn.offer?.excluded || []).forEach(add);
  }
  for (const order of app.data.orders) (order.option?.lines || []).forEach(add);
  return names;
}

const TYPE_WORD = (type) => String(type || "product").replaceAll("_", " ");
const UNIT_WORD = { L: "L", KG: "kg", UNIT: "pcs" };
export const unitWord = (code) => UNIT_WORD[code] || String(code || "").toLowerCase();

// The usual products, each with the words the page shows: its name when known, else its type and id.
export function usualProducts(id = memory.active) {
  const names = knownNames();
  return (customerOf(id)?.usual || []).map((u) => ({
    ...u,
    label: names.has(u.product_id) ? `${names.get(u.product_id)} (${u.product_id})` : `${TYPE_WORD(u.product_type)} ${u.product_id}`,
  }));
}

// One product in the page's words: its name when the gateway has given one, else its type and id.
export function productLabel(productId, id = memory.active) {
  const usual = usualProducts(id).find((u) => u.product_id === productId);
  if (usual) return usual.label;
  const name = knownNames().get(String(productId));
  return name ? `${name} (${productId})` : `product ${productId}`;
}

// The usual unit of a product of this customer ("L", "kg", "pcs"), or "" when it is not a usual product.
export const usualUnit = (productId, id = memory.active) => unitWord(usualProducts(id).find((u) => u.product_id === productId)?.unit);

// The past orders, newest first, each line in the usual product's unit and in the order the usual products are
// listed. Dated and synthetic as the file says.
export function historyRows(id = memory.active) {
  const usual = usualProducts(id);
  const rank = (productId) => {
    const i = usual.findIndex((u) => u.product_id === productId);
    return i < 0 ? usual.length : i;
  };
  return (customerOf(id)?.history || [])
    .slice()
    .reverse()
    .map((order) => ({
      date: order.delivered_on,
      lines: Object.entries(order.quantities || {})
        .sort(([a], [b]) => rank(a) - rank(b))
        .map(([productId, quantity]) => {
          const u = usual[rank(productId)];
          return { productId, quantity, label: u?.label || `product ${productId}`, unit: unitWord(u?.unit) };
        }),
    }));
}
