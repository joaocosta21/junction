// A request that got no offer, said to a person: what was not clear, the reader's question when it asks one, and a
// place to answer it. Nothing for developers is shown here: no key names, no route names, no recordings.
import { app } from "../core.js";
import { html } from "../dom.js";
import { icon } from "../icons.js";
import { ended, plain, sentences } from "../words.js";
import { problemBox } from "./parts.js";

// Sentences meant for a developer or an operator, never for the buyer.
const FOR_DEVELOPERS = /GEMINI|Gemini|API key|\b(?:POST|GET|PUT)\b|\/v1\/|\/shop\/api|recorded demonstration|X-Shop/;
// The openings of the reader's refusals, older and current ("… did not read this request, and nothing was guessed:").
const NOT_READ = /^The fixed rules (?:could not read it either|cannot read this text|did not read this request, and nothing was guessed):\s*/;
const RATE_LIMITED = 429;
const QUESTION_STATUS = 422; // the reader refuses with what is missing: that sentence is its question

// The error kept with a result: what a view needs, and the reader's questions when the gateway passes them on
// (`question`, or `questions` as sentences or objects with `text`, `question` or `sentence`), with what it could
// not read (`not_read`, the fixed rules' 422 since 14 Nov).
export function problemOf(error, step) {
  const p = error?.problem || {};
  const asked = [p.question, ...(Array.isArray(p.questions) ? p.questions : [])];
  const questions = asked
    .map((q) => (typeof q === "string" ? q : q?.text || q?.question || q?.sentence || ""))
    .map((q) => String(q).trim())
    .filter(Boolean);
  return {
    step,
    status: error?.status ?? null,
    type: p.type || null,
    title: error?.title || p.title || null,
    message: error?.message || p.detail || "",
    questions,
    notRead: typeof p.not_read === "string" ? p.not_read.trim() : "",
    // The recipe planner's refusal of a dish sentence (`menu`), or its list of dishes beside the reader's question
    // when the sentence named a dish the recipe table does not have (`dishNote`; assistant.js, planInstead).
    menu: error?.menu === true,
    dishNote: typeof error?.dishNote === "string" ? error.dishNote.trim() : "",
  };
}

// The sentences of a refusal a buyer can use, in plain words.
export function forPeople(message) {
  return sentences(message)
    .map((s) => s.replace(NOT_READ, "What was not clear: "))
    .filter((s) => !FOR_DEVELOPERS.test(s))
    .map((s) => ended(plain(s)));
}

function tryAgain(turn) {
  return html`<button class="btn small line" data-act="retry" data-turn="${turn.id}">Try again</button>`;
}

function readerBox(turn) {
  const p = turn.problem;
  const questions = (p.questions || []).map((q) => plain(q));
  // What was not clear: the reader's own member when it sends one, and then the refusal's sentence is not shown,
  // for it only says the same twice. Otherwise its sentences, less those that only repeat a question listed.
  const unclear = p.notRead ? [ended(`What was not clear: ${plain(p.notRead)}`)] : null;
  const said = unclear || forPeople(p.message).filter((s) => !questions.some((q) => q.includes(s) || s.includes(q)));
  const asks = questions.length ? questions : said;
  const isQuestion = questions.length > 0 || p.status === QUESTION_STATUS;
  const draft = app.ui.redraft?.[turn.id] ?? turn.text;
  return html`<div class="verdict info">${icon("info")}<div>
    <b>${isQuestion ? "The agent needs an answer before it can look this up" : "The request could not be read into a typed request"}</b>
    ${asks.length ? html`<ul class="asks">${asks.map((a) => html`<li>${a}</li>`)}</ul>` : html`<p>The agent could not tell what is needed, how much, or by when.</p>`}
    ${questions.length && said.length ? html`<p class="small">${said.join(" ")}</p>` : ""}
    ${p.dishNote ? html`<p class="small">If you meant a dish: ${forPeople(p.dishNote).join(" ")}</p>` : ""}
    ${p.menu ? "" : html`<p>Say what is needed, how much (a number and a unit) and by when, for example “40 litres of lactose-free milk by Monday”.</p>`}
    <form class="reask" data-act="reask" data-turn="${turn.id}">
      <label class="sr" for="reask-${turn.id}">Your answer, or the request written again</label>
      <textarea id="reask-${turn.id}" name="text" rows="2" data-send data-input="redraft" data-turn="${turn.id}">${draft}</textarea>
      <button class="btn small" type="submit">Read again</button>
    </form>
    <p class="small muted">Or use one of the examples above: they are sent as typed requests and skip the reading.</p>
  </div></div>`;
}

function rulesBox(turn) {
  const said = forPeople(turn.problem.message);
  return html`<div class="verdict stop">${icon("stop")}<div>
    <b>Nothing was asked: this customer's settings are not in force</b>
    <p>${said.length ? said.join(" ") : "The gateway did not accept them."} Nothing is asked or ordered until the gateway accepts them.</p>
    <div class="actions"><button class="btn small dark" data-act="push-again">Send the settings again</button>${tryAgain(turn)}</div>
  </div></div>`;
}

export function failedAnswer(turn) {
  const p = turn.problem || {};
  // A rate limit or the gateway's daily budget: its own sentence says which, and how long to wait.
  if (p.status === RATE_LIMITED) {
    const said = forPeople(p.message);
    return html`<div class="verdict info">${icon("info")}<div><b>Too many requests for now</b>
      <p>${said.length ? said.join(" ") : "The gateway asks to wait before the next request."}</p>
      <div class="actions">${tryAgain(turn)}</div></div></div>`;
  }
  if (p.step === "rules") return rulesBox(turn);
  if (p.step === "reading") return readerBox(turn);
  const said = forPeople(p.message);
  return html`${problemBox({ title: p.title || "The request was refused", message: said.join(" ") })}
    <div class="verdict info">${icon("info")}<div><p>You can try again, or write the request differently.</p><div class="actions">${tryAgain(turn)}</div></div></div>`;
}
