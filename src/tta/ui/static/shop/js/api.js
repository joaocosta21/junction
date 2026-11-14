// The shop's calls to the gateway. Each kitchen of the shop has an order book of its own (X-Shop-Kitchen).

const BASE = "/shop/api";

export class Refusal extends Error {
  constructor(status, problem) {
    super(problem?.detail || `The gateway answered ${status}.`);
    this.status = status;
    this.problem = problem || {};
    this.title = problem?.title || "The request was refused";
  }
}

async function call(kitchen, method, path, body) {
  const headers = { "X-Shop-Request": "1", "X-Shop-Kitchen": kitchen };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Refusal(0, { title: "No connection", detail: "The gateway could not be reached. Check that it is running." });
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) throw new Refusal(response.status, data);
  return data;
}

export function gateway(kitchen) {
  const q = encodeURIComponent;
  return {
    authority: () => call(kitchen, "GET", "/kitchen"),
    setKitchen: (settings) => call(kitchen, "PUT", "/kitchen", settings),
    read: (text) => call(kitchen, "POST", "/read", { text }),
    offer: (request) => call(kitchen, "POST", "/offers", request),
    order: (offerId, optionId, key) => call(kitchen, "POST", "/orders", { offer_id: offerId, option_id: optionId, key }),
    orders: () => call(kitchen, "GET", "/orders"),
    getOrder: (id) => call(kitchen, "GET", `/orders/${q(id)}`),
    approvals: () => call(kitchen, "GET", "/approvals"),
    decide: (approvalId, role, decision, note, name, optionId) =>
      call(kitchen, "POST", `/approvals/${q(approvalId)}/decision`, {
        role,
        name: name || null,
        decision: { decision, note: note || null, option_id: optionId || null },
      }),
    audit: (orderId, reader) => call(kitchen, "GET", `/audit?order_id=${q(orderId)}&reader=${q(reader)}`),
    reset: () => call(kitchen, "POST", "/start-again"),
  };
}

export async function health() {
  try {
    const r = await fetch("/healthz", { credentials: "same-origin" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}
