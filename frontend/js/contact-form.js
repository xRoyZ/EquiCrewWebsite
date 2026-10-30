// Contact form behaviour on /kontakt/ (ES module, loaded after /js/config.js).
// - An untouched form stays neutral. A field shows its error once the user typed into it
//   and left it; a 'Senden' attempt shows the errors of every field.
// - Invalid input: aria-invalid + aria-describedby on the field, a polite announcement,
//   focus on the first invalid field, nothing is sent.
// - Valid input: the button switches to its sending state and the form posts JSON to
//   `${apiBase}/api/contact`. 200 replaces the form by the thank-you sheet; any other
//   status or a network error shows the failure alert, keeps the values and enables the
//   button again.
// Visitor data is never logged.
import { FIELDS, validateField, validateForm } from "./form-validation.mjs";

const REQUEST_TIMEOUT_MS = 20000;
const SEND_LABEL = "Senden";
const SENDING_LABEL = "Wird gesendet …";

function apiBase() {
  const config = window.EQUICREW_CONFIG;
  const base = config && typeof config.apiBase === "string" ? config.apiBase : "";
  return base.replace(/\/+$/, "");
}

function init() {
  const form = document.querySelector("[data-contact-form]");
  if (!form) return;

  const thanks = document.querySelector("[data-contact-thanks]");
  const alertBox = form.querySelector("[data-form-alert]");
  const status = form.querySelector("[data-form-status]");
  const submit = form.querySelector('button[type="submit"]');
  const submitLabel = submit ? submit.querySelector("span") || submit : null;
  const inputs = FIELDS.map((name) => form.elements.namedItem(name)).filter(Boolean);
  const honeypot = form.elements.namedItem("website");
  let sending = false;

  const announce = (text) => {
    if (!status) return;
    // Clear first so the same sentence is announced again on a repeated attempt.
    status.textContent = "";
    window.setTimeout(() => {
      status.textContent = text;
    }, 50);
  };

  const showError = (input, message) => {
    const box = document.getElementById(`${input.id}-error`);
    const text = box ? box.querySelector("span") : null;
    if (message) {
      input.setAttribute("aria-invalid", "true");
      if (text) text.textContent = message;
      if (box) box.hidden = false;
    } else {
      input.removeAttribute("aria-invalid");
      if (text) text.textContent = "";
      if (box) box.hidden = true;
    }
  };

  for (const input of inputs) {
    input.addEventListener("input", () => {
      input.dataset.dirty = "1";
      // An error already shown follows the typing, so it disappears once fixed.
      if (input.getAttribute("aria-invalid") === "true") {
        showError(input, validateField(input.name, input.value));
      }
    });
    input.addEventListener("blur", () => {
      if (input.dataset.dirty && !sending) {
        showError(input, validateField(input.name, input.value));
      }
    });
  }

  const values = () => {
    const data = {};
    for (const input of inputs) data[input.name] = input.value;
    return data;
  };

  const setSending = (on) => {
    sending = on;
    form.setAttribute("aria-busy", on ? "true" : "false");
    for (const input of inputs) input.disabled = on;
    if (!submit) return;
    submit.disabled = on;
    submit.classList.toggle("is-sending", on);
    if (on) submit.setAttribute("aria-disabled", "true");
    else submit.removeAttribute("aria-disabled");
    if (submitLabel) submitLabel.textContent = on ? SENDING_LABEL : SEND_LABEL;
  };

  const showSent = () => {
    form.hidden = true;
    if (thanks) {
      thanks.hidden = false;
      thanks.focus();
    }
  };

  const showFailed = () => {
    setSending(false);
    if (alertBox) alertBox.hidden = false;
    if (submit) submit.focus();
  };

  const post = async (payload) => {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = controller ? window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS) : 0;
    try {
      const response = await fetch(`${apiBase()}/api/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller ? controller.signal : undefined,
      });
      return response.status === 200;
    } catch {
      // Network error, CORS refusal or timeout: the failure alert tells the visitor.
      return false;
    } finally {
      if (timer) window.clearTimeout(timer);
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sending) return;

    const data = values();
    const errors = validateForm(data);
    let firstInvalid = null;
    for (const input of inputs) {
      const message = errors[input.name] || null;
      showError(input, message);
      if (message && !firstInvalid) firstInvalid = input;
    }
    if (firstInvalid) {
      const count = Object.keys(errors).length;
      announce(
        count === 1
          ? "Bitte prüfe das markierte Feld."
          : `Bitte prüfe die ${count} markierten Felder.`,
      );
      firstInvalid.focus();
      return;
    }

    if (alertBox) alertBox.hidden = true;
    const payload = {
      vorname: data.vorname.trim(),
      nachname: data.nachname.trim(),
      email: data.email.trim(),
      nachricht: data.nachricht,
      website: honeypot ? honeypot.value : "",
    };
    setSending(true);
    const sent = await post(payload);
    if (sent) showSent();
    else showFailed();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
