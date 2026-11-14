// Trusted Trade Agents: the little script of the pages. Every page works without it.
// No library, no inline handler, no request to another host (the Content-Security-Policy forbids them).
(function () {
  "use strict";

  var SHOWN_HASH_LENGTH = 16;

  // A form that changes state is sent once: a double click must not run a request or a decision twice.
  // The buttons are disabled after the browser has read the form, so the clicked button's value is still sent.
  function sendOnce(form) {
    form.addEventListener("submit", function () {
      window.setTimeout(function () {
        form.querySelectorAll("button").forEach(function (button) {
          button.disabled = true;
        });
      }, 0);
    });
  }

  // The "deciding as" selector switches as soon as another approver is chosen.
  function submitOnChange(select) {
    select.addEventListener("change", function () {
      if (select.form) {
        select.form.submit();
      }
    });
  }

  // The order page shows the head of the whole audit chain, read from the public health route.
  function showAuditHead(place) {
    fetch(place.getAttribute("data-audit-head"), { headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.ok ? response.json() : Promise.reject(new Error("no answer"));
      })
      .then(function (health) {
        var head = health.audit_head;
        if (!head || typeof head.events !== "number" || typeof head.last_hash !== "string") {
          return;
        }
        var line = document.createElement("p");
        line.className = "small";
        line.textContent = "Head of the whole audit chain now: " + head.events + " events, last hash "
          + head.last_hash.slice(0, SHOWN_HASH_LENGTH) + "… A copy kept by another party shows a trail cut short.";
        place.insertAdjacentElement("afterend", line);
      })
      .catch(function () {
        // The page already links to the health route; without an answer it stays as it is.
      });
  }

  document.querySelectorAll('form[method="post"]').forEach(sendOnce);
  document.querySelectorAll("select[data-autosubmit]").forEach(submitOnChange);
  document.querySelectorAll("[data-audit-head]").forEach(showAuditHead);
}());
