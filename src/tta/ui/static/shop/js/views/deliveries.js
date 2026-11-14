// Deliveries: a calendar like the shop's delivery calendar, with this kitchen's orders on their delivery days.
import { app, dataToday, deliveryOf, on, refresh, render } from "../core.js";
import { html, isoDay, longDate, money, monthName, shortDate } from "../dom.js";
import { icon } from "../icons.js";
import { SYNTHETIC } from "../kitchens.js";
import { active } from "../store.js";
import { netTotal, statusTag } from "./parts.js";

const state = { month: null, selected: null };

on("day", (el) => {
  state.selected = el.dataset.day;
  render();
});
on("month", (el) => {
  const m = state.month || new Date(dataToday().getFullYear(), dataToday().getMonth(), 1);
  state.month = new Date(m.getFullYear(), m.getMonth() + Number(el.dataset.step), 1);
  render();
});

function byDay() {
  const days = {};
  const add = (date, entry) => (days[date] ||= []).push(entry);
  for (const o of app.data.orders) {
    const date = deliveryOf(o.option);
    if (date && ["ORDERED", "PENDING_APPROVAL"].includes(o.status)) add(date, { live: o });
  }
  for (const h of active().history) add(h.date, { past: h });
  return days;
}

function calendar(days) {
  const today = isoDay(dataToday());
  const first = state.month || new Date(dataToday().getFullYear(), dataToday().getMonth(), 1);
  const start = new Date(first);
  start.setDate(1 - ((first.getDay() + 6) % 7)); // back to Monday
  const weeks = [];
  for (let w = 0; w < 6; w++) {
    const cells = [];
    for (let d = 0; d < 7; d++) {
      const date = new Date(start);
      date.setDate(start.getDate() + w * 7 + d);
      const key = isoDay(date);
      const inMonth = date.getMonth() === first.getMonth();
      const sunday = date.getDay() === 0;
      const entries = days[key] || [];
      const marks = entries.map((e) => (e.past ? "m-past" : e.live.status === "ORDERED" ? "m-ok" : "m-wait"));
      cells.push(html`<td><button class="${!inMonth || sunday ? "off" : ""} ${key === today ? "today" : ""} ${key === state.selected ? "sel" : ""}" ${!inMonth || sunday ? "disabled" : ""} data-act="day" data-day="${key}" aria-label="${longDate(key)}">${date.getDate()}${marks.length ? html`<span class="marks">${marks.slice(0, 3).map((m) => html`<i class="${m}"></i>`)}</span>` : ""}</button></td>`);
    }
    weeks.push(html`<tr>${cells}</tr>`);
  }
  return html`<div class="card">
    <div class="card-title"><button class="icon-btn" data-act="month" data-step="-1" aria-label="Previous month">${icon("left")}</button><h3>${monthName(first)}</h3><button class="icon-btn" data-act="month" data-step="1" aria-label="Next month">${icon("right")}</button></div>
    <table class="cal"><thead><tr>${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => html`<th>${d}</th>`)}</tr></thead><tbody>${weeks}</tbody></table>
    <div class="legend"><span><i class="m-ok"></i>Ordered</span><span><i class="m-wait"></i>Waiting for approval</span><span><i class="m-past"></i>Delivered (synthetic history, made up for the demonstration)</span><span>No deliveries on Sundays</span></div>
  </div>`;
}

function dayPanel(days) {
  const key = state.selected;
  if (!key) return html`<div class="card"><h3>Pick a day</h3><p class="small muted">Days with a dot have deliveries. All orders for one day arrive together, with one delivery fee.</p></div>`;
  const entries = days[key] || [];
  return html`<div class="card">
    <div class="card-title"><h3>${longDate(key)}</h3><span class="tag">${entries.length} order${entries.length === 1 ? "" : "s"}</span></div>
    ${entries.length
      ? html`<ul class="side-list">${entries.map((e) =>
          e.live
            ? html`<li><span><a href="#/orders/${e.live.order_id}"><b>${e.live.option.lines.map((l) => l.name).join(", ")}</b></a><br>${statusTag(e.live)} <span class="small muted">${netTotal(e.live.option.totals)}</span></span></li>`
            : html`<li><span><b>${e.past.lines.map((l) => l[0]).join(", ")}</b><br><span class="tag">Delivered</span> <span class="small muted">${money(e.past.lines.reduce((s, l) => s + l[3], 0))} · ${SYNTHETIC}</span></span></li>`
        )}</ul>`
      : html`<p class="small muted">No delivery on this day yet. Write a purchase request for something "by ${shortDate(key)}".</p>`}
  </div>`;
}

export function view() {
  const k = active();
  const days = byDay();
  return html`
    <div class="page-head"><div><div class="crumbs">${k.name} · ${k.address}</div><h1>Deliveries</h1><div class="sub">Delivery days: ${k.deliveryDays}. Stocked products arrive the next delivery day if ordered before the cut-off; products from a supplier's own warehouse take about two days.</div></div></div>
    <div class="lead">
      <div><b>24 h</b><span>Stocked products: order by the cut-off shown on each product</span></div>
      <div><b>48 h</b><span>Terminal products, delivered from the supplier's warehouse</span></div>
      <div><b>1 fee</b><span>Orders for the same day travel together</span></div>
    </div>
    <div class="grid">
      <section>${calendar(days)}</section>
      <aside class="side">${dayPanel(days)}</aside>
    </div>`;
}

export function enter() {
  state.month = null;
  state.selected = state.selected || null;
  refresh();
}
