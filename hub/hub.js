"use strict";
const $ = (selector) => document.querySelector(selector);
function updateClock() {
  const now = new Date();
  $("#clock").textContent = new Intl.DateTimeFormat("cs-CZ", {timeZone:"Europe/Prague", hour:"2-digit", minute:"2-digit"}).format(now);
  $("#date").textContent = new Intl.DateTimeFormat("cs-CZ", {timeZone:"Europe/Prague", weekday:"long", day:"numeric", month:"long", year:"numeric"}).format(now);
}
function showView() {
  const finance = location.hash === "#finance";
  $("#home-view").hidden = finance;
  $("#finance-view").hidden = !finance;
  document.querySelectorAll("[data-view]").forEach(link => {
    const active = link.dataset.view === (finance ? "finance" : "home");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  // Always return to the private empty state when switching views.
  $("#finance-demo").hidden = true;
  $(".finance-empty").hidden = false;
  document.title = finance ? "Wonders · Moje finance" : "Wonders · Domov";
}
$("#show-demo").addEventListener("click", () => {
  $("#finance-demo").hidden = false;
  $(".finance-empty").hidden = true;
  $("#hide-demo").focus();
});
$("#hide-demo").addEventListener("click", () => {
  showView();
  $("#show-demo").focus();
});
const explanations = {
  climate: ["AC INFINITY", "Hodnoty přímo z pěstírny.", "Tady zatím vidíš ukázkové hodnoty. Pro skutečné sledování už máš samostatný AC Infinity Monitor. Při propojení zachováme sledování teploty, vlhkosti a VPD bez ovládání zařízení."],
  bob: ["BOB + CODEX", "Přehled, kterému rozumíš.", "Z výpisu Komerční banky připravíme lokální souhrn. V Codexu pak můžeš říct: Bobe, vyhodnoť moje utrácení za říjen. Dostaneš vysvětlení výdajů, platby k prověření a návrhy podle svých cílů. Tento návrh analýzu ještě nespouští; částky v ukázce jsou vymyšlené."]
};
document.querySelectorAll("[data-dialog]").forEach(button => button.addEventListener("click", () => {
  const [label, title, body] = explanations[button.dataset.dialog];
  $("#dialog-label").textContent = label;
  $("#dialog-title").textContent = title;
  $("#dialog-body").textContent = body;
  $("#info-dialog").showModal();
}));
$("#close-dialog").addEventListener("click", () => $("#info-dialog").close());
$("#dialog-ok").addEventListener("click", () => $("#info-dialog").close());
window.addEventListener("hashchange", showView);
updateClock();
setInterval(updateClock, 1000);
showView();
