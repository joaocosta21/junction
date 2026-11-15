// "You usually order this": when a customer is opened or switched to, the gateway says what it ordered week after
// week (GET /shop/api/reorder). This module reads and keeps that answer; the request view draws it (assistant.js),
// below the request box. "Order the same again" posts the gateway's request unchanged: the answer is an offer on a
// normal result card, prepared, and a person confirms it as always. "Not now" hides it until the customer is opened
// again. No answer, or no lines: nothing is shown.
import { app, render } from "../core.js";
import { gateway } from "../api.js";
import { memory } from "../store.js";

const lineOf = (line) => line && typeof line === "object" && line.product_id;

// Read for the customer being opened. Written into that customer's data, so a switch meanwhile cannot mix two.
export async function loadReorder() {
  const data = app.data;
  try {
    const answer = await gateway(memory.active).reorder();
    const lines = Array.isArray(answer?.lines) ? answer.lines.filter(lineOf) : [];
    data.reorder = lines.length && answer.request ? { ...answer, lines } : null;
  } catch {
    data.reorder = null; // no route yet, or no answer: the page offers nothing it cannot back
  }
  render();
}

export const reorderShown = () => (app.data.reorder && !app.data.reorderDismissed ? app.data.reorder : null);

export function hideReorder() {
  app.data.reorderDismissed = true;
  render();
}
