// The typed interface behind the page, shown: the request as the gateway got it, and where any purchasing agent
// sends the same. The page is one client of that interface; it decides nothing the interface does not.
import { html } from "../dom.js";
import { icon } from "../icons.js";

const DOCS = "/docs";
const MCP = "/mcp";
// The 13 tools of the MCP server (`tta.api.mcp_surface.TOOL_NAMES`; no shop route lists them). None of them
// approves: that is for a person.
const MCP_TOOLS = [
  "get_authority", "search_products", "get_product", "find_substitutes", "get_offer", "place_order", "get_order",
  "get_audit", "get_customer", "plan_menu", "set_up_standing_order", "renew_standing_order", "list_standing_orders",
];
const HOW = {
  example: "This example is sent as written, with no reading step.",
  suggestion: "The suggestion's own request, sent unchanged: it names the suggestion it accepts, so the gateway records the acceptance.",
};

export function openInterface() {
  return html`<p class="open">The same typed interface is open to any purchasing agent:
    <a href="${DOCS}" target="_blank" rel="noopener">REST API with its OpenAPI description</a>, and an MCP server at
    <code>${MCP}</code> with ${MCP_TOOLS.length} tools. None of them approves.</p>`;
}

// What the page sent: the reading of the text, with what the buyer confirmed here (a brand) added to it.
export function typedRequest(turn) {
  const request = turn.sent || turn.offer?.request;
  if (!request) return "";
  const how = HOW[turn.reading?.source] || "What the agent read from your text.";
  return html`<details class="why typed">
    <summary>${icon("right")}Typed request sent to the gateway</summary>
    <div class="why-body">
      <p class="small muted">${how} Any purchasing agent can send the same request: <code>POST /v1/offers</code> in the
        <a href="${DOCS}" target="_blank" rel="noopener">REST API</a>, or the tool <code>get_offer</code> of the MCP server at
        <code>${MCP}</code>. Ordering is <code>place_order</code>. Approving is for a person: no tool does it.</p>
      <pre class="json">${JSON.stringify(request, null, 2)}</pre>
      <p class="small muted">MCP tools: ${MCP_TOOLS.map((t, i) => html`${i ? ", " : ""}<code>${t}</code>`)}.</p>
    </div>
  </details>`;
}
