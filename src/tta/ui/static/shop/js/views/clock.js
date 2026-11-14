// The clock strip on every view (R8, P5-clock.md section 4, "Labels"): which instant prices, stock and closing
// times are judged against, that we chose it when a demo clock is set, and that the log keeps the real time.
// The gateway states its clock (`GET /healthz`, `clock`): the strip prints a short line of it and, unfolded,
// the gateway's own sentence. Nothing here decides a time.
import { html, instant } from "../dom.js";
import { icon } from "../icons.js";
import { plain } from "../words.js";

const SETTING = "TTA_DEMO_CLOCK"; // the gateway's setting, shown as a name in the full text only
const LOG = "The log keeps the real time.";

function short(clock) {
  const when = instant(clock.now);
  switch (clock.basis) {
    case "demo_setting":
      return `Demo clock: ${when}, chosen by us. ${LOG}`;
    case "recording":
      return `Clock: ${when}, the moment Valio Aimo's data was recorded. ${LOG}`;
    case "supplier":
      return `Clock: Valio Aimo's server time, ${when}.${clock.demo_clock_set ? " A demo clock is set and not applied to live data." : ""} ${LOG}`;
    default:
      return `Clock: ${when}. ${LOG}`;
  }
}

// The gateway's sentence, with the setting's name as code rather than a word to read.
function full(sentence) {
  const parts = String(sentence || "").split(SETTING);
  return parts.map((part, i) => html`${i ? html`<code>${SETTING}</code>` : ""}${plain(part)}`);
}

// `health` is the gateway's answer (null when it did not answer); `asked` says whether the page has asked yet;
// `open` keeps the full sentence unfolded across renders (the fold is the page's state, not the browser's).
export function clockStrip(health, asked, open = false) {
  const clock = health?.clock;
  if (!clock?.now) {
    if (!asked) return "";
    return html`<div class="clockbar"><div class="clockbar-in">${icon("clock")}<span>The gateway did not say which clock is in force, so this page cannot show it.</span></div></div>`;
  }
  return html`<details class="clockbar" ${open ? "open" : ""}>
    <summary class="clockbar-in" data-act="clock-fold" aria-expanded="${String(open)}">${icon("clock")}<span>${short(clock)}</span><span class="more">Why this time</span></summary>
    <div class="clockbar-in clockbar-full"><p>${full(clock.sentence)}</p></div>
  </details>`;
}
