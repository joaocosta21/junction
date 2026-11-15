// The recipe plan of a result (task U5): a sentence that names a dish and its servings, read by the gateway's
// recipe planner (POST /shop/api/menus/plan) into dishes and servings, with the offer it made. Three lines first:
// what was asked, what the recipe needs and what is offered for it (one row per ingredient, for the option chosen),
// and what needs a person and why. The option cards under it are the request page's own (assistant.js). Every
// figure is the gateway's; the page only multiplies packs by their size to say what is left over.
// The card has one decision box, the request page's own (assistant.js), which holds the button and follows the
// order: the plan adds its reasons in a plain line while nothing is ordered, and nothing once an order exists.
// With an option, the request page draws that option's total and its decision box first and this card under them,
// so that "Confirm order" is in the window; the rows are what the person reads next.
import { money } from "../core.js";
import { html, num, unit } from "../dom.js";
import { icon } from "../icons.js";
import { plain } from "../words.js";
import { peopleFor, stockLine } from "./parts.js";

const READ_AS = /^Read as: /;
// The planner's note that some products were answered from a later recording (tta.offers.recorded.LATER_RECORDED).
const LATER = /^\d+ of the \d+ products of this offer have their price and stock from the later recording/;
const ILLUSTRATIVE = /illustrative/;
const PER_OPTION = /^Option \d+, /; // the planner's sentence per option: the option cards below say the same
const NOT_CONFIRMED = "QUANTITY_NOT_CONFIRMED";
// What the rows already say: the date and the share missed by a line the option leaves out, a quantity Valio Aimo
// does not confirm, a product type that stands in for the recipe's. Any other rule that fired is said as written.
const SAID_BY_UNCOVERED = ["F-07", "P-03"];
const SAID_BY_UNCONFIRMED = ["F-01"];
const SAID_BY_STAND_IN = ["F-09"];
const EXACT = 0.0005; // kg or L: below half a gram, a pack holds exactly the need

const words = (type) => String(type || "").replaceAll("_", " ");
const capital = (text) => (text ? text[0].toUpperCase() + text.slice(1) : "");
// Recipe amounts to the gram or millilitre (the planner asks for an amount below 1 kg or 1 L to the gram).
const GRAMS = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 });
const amount = (n, u) => `${GRAMS.format(Math.round(Number(n) * 1000) / 1000)} ${unit(u)}`;
const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);
// Who confirms, each person once and by name; what they are only for somebody else than the person signed in.
const who = (roles) => listed(peopleFor(roles));

// ---- the plan's notes ---------------------------------------------------------------------------------------

// "Read as: <dish>, 20 servings, by Monday 16 Nov.": the first note, when the planner read a sentence.
export const planReadAs = (plan) => (READ_AS.test(plan?.notes?.[0] || "") ? plan.notes[0] : "");

const laterNote = (plan) => (plan.notes || []).find((n) => LATER.test(n)) || "";

function otherNotes(plan) {
  const shown = (n, i) => (i === 0 && READ_AS.test(n)) || LATER.test(n) || ILLUSTRATIVE.test(n) || PER_OPTION.test(n);
  return (plan.notes || []).filter((n, i) => !shown(n, i));
}

// The products of a later recording, said once: how many as the fold's line, and under it only what that line
// does not say (which products, and why the two recordings are read together), never the same sentence again.
export function laterParts(note) {
  const first = note.split(" (")[0];
  const rest = note.slice(first.length).trim().replace(/^\(([^)]*)\)\.\s*/, "They are $1. ");
  return [first, rest];
}

function laterFold(plan) {
  const note = laterNote(plan);
  if (!note) return "";
  const [first, rest] = laterParts(note);
  return html`<details class="why fold"><summary>${icon("right")}${first}</summary>
    ${rest ? html`<div class="why-body"><p class="small muted">${plain(rest)}</p></div>` : ""}</details>`;
}

// ---- one ingredient: needed, offered, what is left over --------------------------------------------------

const linesOf = (option, index) => (option?.lines || []).filter((l) => l.request_line_index === index);
const lineOf = (plan, index) => (plan.lines || []).find((l) => l.request_line_index === index);

// The option that offers something for request line `index` when the chosen one does not: the first that does.
const elsewhere = (offer, chosen, index) => (offer?.options || []).find((o) => o !== chosen && linesOf(o, index).length);

// "1 × 2 kg", "3 × 0.5 kg": packs as Valio Aimo sells them, the size where the product file states it.
function packWords(line) {
  const size = line.pack_size?.value;
  return size ? `${num(line.quantity)} × ${amount(size, line.pack_size.unit)}` : `${num(line.quantity)} ${unit(line.sales_unit)}`;
}

// What the packs hold in the recipe's unit, or null when a size is not stated or is in another unit.
function bought(lines, needUnit) {
  let total = 0;
  for (const l of lines) {
    if (!l.pack_size?.value || l.pack_size.unit !== needUnit) return null;
    total += Number(l.quantity) * Number(l.pack_size.value);
  }
  return total;
}

// What the packs are: "the pack is 2 kg", "2 packs of 2 kg hold 4 kg", "the packs hold 6 kg" (two products).
function packsHeld(lines, held, needUnit) {
  if (lines.length > 1) return `the packs hold ${amount(held, needUnit)}`;
  const [line] = lines;
  if (Number(line.quantity) === 1) return `the pack is ${amount(held, needUnit)}`;
  return `${num(line.quantity)} packs of ${amount(line.pack_size.value, needUnit)} hold ${amount(held, needUnit)}`;
}

// "You need 0.4 kg; the pack is 2 kg; 1.6 kg is left over." A wholesale pack against a small need, in plain words.
export function leftover(need, needUnit, lines) {
  const held = bought(lines, needUnit);
  const needed = `You need ${amount(need, needUnit)}`;
  if (held === null) return `${needed}; the pack size is not stated, so what is left over cannot be said.`;
  const left = held - Number(need);
  if (left < EXACT) return `${needed}; ${packsHeld(lines, held, needUnit)}: nothing is left over.`;
  return `${needed}; ${packsHeld(lines, held, needUnit)}; ${amount(left, needUnit)} is left over.`;
}

function offered(lines, need, needUnit, where = "") {
  return html`${lines.map((l) => html`<div class="plan-product">
      <div class="pname">${where}${l.name} <span class="pid">(${l.product_id})</span></div>
      <div class="small">${packWords(l)} · <b>${money(l.net)}</b> before tax</div>
      ${stockLine(l.availability)}
    </div>`)}
    <p class="small plan-left">${leftover(need, needUnit, lines)}</p>`;
}

function offerCell(plan, offer, option, ingredient) {
  if (ingredient.status === "IN_STOCK") return html`<p class="small">Your stock covers it: nothing is ordered.</p>`;
  if (ingredient.status === "CANNOT_BE_SOURCED") {
    return html`<p class="small"><span class="tag stop">Cannot be supplied</span> ${plain(ingredient.sentence)}</p>`;
  }
  const index = ingredient.request_line_index;
  const line = lineOf(plan, index);
  const need = line ? line.to_order : ingredient.to_order;
  const mine = linesOf(option, index);
  if (mine.length) return offered(mine, need, ingredient.unit);
  const other = elsewhere(offer, option, index);
  if (!other) return html`<p class="small"><span class="tag stop">Not offered</span> No option holds a product for it.</p>`;
  return html`<p class="small"><span class="tag wait">Not in this option</span> Only option ${other.rank} offers it:</p>
    ${offered(linesOf(other, index), need, ingredient.unit)}`;
}

function standsIn(ingredient) {
  if (ingredient.status !== "STANDS_IN") return "";
  return html`<p class="small"><span class="tag info">Stands in</span> ${words(ingredient.product_type)} in place of ${words(ingredient.recipe_product_type)}${ingredient.alternative_reason ? `: ${plain(ingredient.alternative_reason)}` : ""}</p>`;
}

function row(plan, offer, option, dish, ingredient) {
  const shared = (lineOf(plan, ingredient.request_line_index)?.dishes || []).length > 1;
  return html`<li class="plan-row">
    <div class="plan-what"><b>${capital(words(ingredient.recipe_product_type))}</b>
      <span class="small muted">${plain(ingredient.role)}</span>
      ${plan.dishes.length > 1 ? html`<span class="tiny muted">${dish.name}</span>` : ""}</div>
    <div class="plan-need"><b>${amount(ingredient.needed, ingredient.unit)}</b>${Number(ingredient.in_stock) > 0 ? html`<span class="tiny muted">${amount(ingredient.in_stock, ingredient.unit)} in your stock</span>` : ""}${shared ? html`<span class="tiny muted">one line for every dish that uses it</span>` : ""}</div>
    <div class="plan-offer">${standsIn(ingredient)}${offerCell(plan, offer, option, ingredient)}</div>
  </li>`;
}

// "In 3 of the 4 packs of this option, more is left over than the recipe uses": what wholesale packs do to a
// small need, counted over the rows that have a product in the chosen option.
function packsNote(plan, option) {
  let offeredRows = 0;
  let over = 0;
  for (const line of plan.lines || []) {
    const lines = linesOf(option, line.request_line_index);
    const held = lines.length ? bought(lines, line.unit) : null;
    if (held === null) continue;
    offeredRows += 1;
    if (held - Number(line.to_order) > Number(line.to_order)) over += 1;
  }
  if (!over) return "";
  return html`<p class="small muted">In ${over} of the ${offeredRows} products of this option, more is left over than the recipe uses: Valio Aimo sells whole packs, and each row says what is left.</p>`;
}

// ---- line 3: what needs a person, and why ------------------------------------------------------------------

function reasons(plan, option) {
  const ingredients = plan.dishes.flatMap((d) => d.ingredients).filter((i) => i.request_line_index !== null && i.request_line_index !== undefined);
  const uncovered = [...new Set(ingredients.filter((i) => !linesOf(option, i.request_line_index).length).map((i) => words(i.recipe_product_type)))];
  const unconfirmed = [...new Set(ingredients.filter((i) => linesOf(option, i.request_line_index).some((l) => l.availability?.state === NOT_CONFIRMED)).map((i) => words(i.recipe_product_type)))];
  const standing = ingredients.filter((i) => i.status === "STANDS_IN").map((i) => `${words(i.product_type)} stands in for ${words(i.recipe_product_type)}`);
  const found = [
    [uncovered, `this option has nothing for ${listed(uncovered)}`, SAID_BY_UNCOVERED],
    [unconfirmed, `Valio Aimo does not confirm the quantity in stock of ${listed(unconfirmed)}`, SAID_BY_UNCONFIRMED],
    [standing, listed(standing), SAID_BY_STAND_IN],
  ].filter(([items]) => items.length);
  const explained = new Set(found.flatMap(([, , rules]) => rules));
  const others = (option.decision?.fired || []).filter((r) => !explained.has(r.rule_id)).map((r) => plain(r.sentence).replace(/\.$/, ""));
  return [...found.map(([, sentence]) => sentence), ...new Set(others)];
}

// Not a second decision box: the box with the button is the request page's, under the option, and it alone says
// what happened once the option is ordered (`ordered`). Until then the plan says, in its own words, why a person
// decides. An option the agent may order alone, or one that cannot be ordered, is said by that box only.
function needsPerson(plan, option, ordered) {
  const d = option?.decision || {};
  if (ordered || d.verdict !== "APPROVAL") return "";
  const roles = d.required_roles || [];
  const why = reasons(plan, option);
  const sentence = why.length ? `${capital(why.join("; "))}.` : plain(d.sentence);
  return html`<p class="small"><b>${roles.length ? `Needs ${who(roles)}` : "Needs a person"}:</b> ${sentence} The decision is asked above, with the total.</p>`;
}

// ---- the card -------------------------------------------------------------------------------------------------

function cannotBeSupplied(plan) {
  const list = plan.cannot_be_sourced || [];
  if (!list.length) return "";
  return html`<div class="verdict stop">${icon("stop")}<div><b>Cannot be supplied</b>
    <ul class="asks">${list.map((u) => html`<li><b>${capital(words(u.product_type))}, ${amount(u.quantity, u.unit)}</b>: ${plain(u.sentence)}</li>`)}</ul></div></div>`;
}

function leftOut(plan) {
  const out = plan.dishes.flatMap((d) => (d.left_out || []).map((item) => (plan.dishes.length > 1 ? `${d.name}: ${item}` : item)));
  return out.length ? html`<p class="small muted">Not ordered here: ${out.map(plain).join("; ")}.</p>` : "";
}

function howMade(plan) {
  const notes = otherNotes(plan);
  if (!notes.length) return "";
  return html`<details class="why fold"><summary>${icon("right")}How the plan was made</summary>
    <div class="why-body">${notes.map((n) => html`<p class="small muted">${plain(n)}</p>`)}</div></details>`;
}

// The plan's three lines and what belongs to them, for the option chosen (`option`, the first when none is).
export function planCard(turn, option) {
  const plan = turn.plan;
  const offer = turn.offer;
  const illustrative = (plan.notes || []).find((n) => ILLUSTRATIVE.test(n));
  const rows = plan.dishes.flatMap((dish) => dish.ingredients.map((ingredient) => row(plan, offer, option, dish, ingredient)));
  return html`<section class="plan" aria-label="Recipe plan">
    <div class="label-row"><span class="label">What the recipe needs</span><span class="small muted">${option ? `and what option ${option.rank} (${plain(option.title)}) offers for it` : "and nothing could be offered for it"}</span></div>
    <ul class="plan-rows">${rows}</ul>
    ${option ? packsNote(plan, option) : ""}
    ${option ? needsPerson(plan, option, Boolean(turn.order)) : ""}
    ${cannotBeSupplied(plan)}
    ${leftOut(plan)}
    ${illustrative ? html`<p class="tiny muted">${plain(illustrative)}</p>` : ""}
    ${laterFold(plan)}
    ${howMade(plan)}
  </section>`;
}
