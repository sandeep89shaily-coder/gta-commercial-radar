/* No analytics, cookies, third-party SDKs, or email submissions. */
(function () {
  "use strict";
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());

  var form = document.getElementById("sample-form");
  if (!form) return;
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var emailField = document.getElementById("lead-email");
    var sectorField = document.getElementById("lead-sector");
    var marketField = document.getElementById("lead-market");
    var feedback = document.getElementById("request-feedback");

    if (!emailField || !sectorField || !marketField || !feedback) return;
    if (!emailField.value.trim() || !emailField.checkValidity()) {
      emailField.setCustomValidity("Enter a valid email address to request the sample.");
      emailField.reportValidity();
      feedback.textContent = "Please enter a valid work email.";
      emailField.setCustomValidity("");
      return;
    }

    // The static website has no server, so there is no hidden or misleading
    // 'success' message. The visitor must explicitly send the email from
    // their own mail client to make a request.
    var subject = "GTA Radar sample research report request";
    var body = [
      "Hello GTA Radar,",
      "",
      "I would like to request a sample of your source-linked commercial intelligence report.",
      "",
      "Reply-to email: " + emailField.value.trim(),
      "My industry: " + sectorField.value,
      "Preferred market: " + marketField.value,
      "",
      "Please let me know which sample material is currently available.",
    ].join("\n");
    var mailto = "mailto:gtaradar18@gmail.com?subject=" +
      encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
    feedback.textContent = "Your email application should open with a draft. Please press Send there to complete your request; nothing has been submitted automatically.";
    window.location.href = mailto;
  });
})();
