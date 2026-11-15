// What a manufacturer's page says about a product whose data does not rule out an excluded allergen (task S2):
// shown beside the allergen question wherever it is asked. On the approvals page it is the approval's own
// (`approval.evidence`); on a result, where the person signed in decides before any approval exists, it is read
// once per option from GET /shop/api/evidence, which answers from the recordings only and asks nobody.
import { api, render } from "../core.js";
import { cutoff, html } from "../dom.js";
import { save } from "../store.js";
import { plain } from "../words.js";

// Only a plain web address becomes a link: never javascript:, data: or anything else a page could carry.
const WEB_LINK = /^https?:\/\//i;

function hostOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

const named = (items) => (Array.isArray(items) && items.length ? items.join(", ") : "nothing named");

// What one web page says (task S2). Its sentence says whose page it is: "The manufacturer's page …" for a host the
// gateway lists as the brand owner's, "A web page whose owner was not checked …" for any other. Every word comes
// from the web or the gateway and is escaped like any other text.
function evidenceEntry(found) {
  const url = typeof found.source_url === "string" && WEB_LINK.test(found.source_url) ? found.source_url : null;
  if (!found.found || !url) return html`<p class="small">${plain(found.sentence)}</p>`;
  return html`<div class="ev-entry">
    <p><b>Product ${found.product_id}</b>: ${plain(found.sentence)}</p>
    <ul class="findings">
      <li><span>Contains</span>${named(found.contains)}</li>
      <li><span>May contain</span>${named(found.may_contain)}</li>
      <li><span>Free from</span>${named(found.free_from)}</li>
    </ul>
    <p class="small muted">Source: <a href="${url}" title="${url}" target="_blank" rel="noopener noreferrer nofollow">${hostOf(url)}</a>${found.page_title ? html` · page title “${found.page_title}”` : ""}${found.retrieved_at ? html` · read ${cutoff(found.retrieved_at)}` : ""}</p>
  </div>`;
}

// Shown above the reasons, under its own heading, and never as Valio Aimo's data: it changes no status and no
// decision. The same fields and wording as the approvals page of the old pages (templates/_evidence.html).
export function evidenceBlock(holder) {
  const entries = (Array.isArray(holder?.evidence) ? holder.evidence : []).filter((e) => e && typeof e === "object");
  if (!entries.length) return "";
  return html`<section class="evidence">
    <h4>Found on the web, not Valio Aimo data</h4>
    ${entries.map(evidenceEntry)}
    <p class="small muted">Read from the web through Context.dev. Valio Aimo's data still states nothing about this allergen, so it stays unknown: this changes no status and no decision, and the person approving decides.</p>
  </section>`;
}

// The evidence for one option of a result, read once and kept on the turn (`turn.evidence[option_id]`): an empty
// list when the gateway has none or does not answer, so the question is asked either way.
// `gateway`: the book of the customer that asked (assistant.js gives the one the request was sent for), so a switch
// of customer meanwhile reads nothing from another book.
export async function loadEvidence(turn, option, gateway = api()) {
  const id = option?.option_id;
  if (!turn.offer?.offer_id || !id || turn.evidence?.[id]) return;
  let found = [];
  try {
    found = await gateway.evidence(turn.offer.offer_id, id);
  } catch {
    found = [];
  }
  turn.evidence = { ...(turn.evidence || {}), [id]: Array.isArray(found) ? found : [] };
  save();
  render();
}

export const evidenceFor = (turn, option) => evidenceBlock({ evidence: turn.evidence?.[option.option_id] });
