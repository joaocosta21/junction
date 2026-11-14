// Trusted Trade Agents: the little script of the pages. Every page works without it.
// No library, no inline handler, no request to another host (the Content-Security-Policy forbids them).
(function () {
  "use strict";

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

  document.querySelectorAll('form[method="post"]').forEach(sendOnce);
  document.querySelectorAll("select[data-autosubmit]").forEach(submitOnChange);
}());
