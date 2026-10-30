// Client-side validation of the contact form (node --test).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  FIELDS,
  MAX_MESSAGE_LENGTH,
  MESSAGES,
  validateField,
  validateForm,
} from "../js/form-validation.mjs";

const VALID = {
  vorname: "Mara",
  nachname: "Beispiel",
  email: "mara@beispiel.at",
  nachricht: "Wir möchten gerne mehr über den EquiCube erfahren.",
};

test("every field is required, whitespace counts as empty", () => {
  for (const name of FIELDS) {
    for (const empty of ["", "   ", undefined, null]) {
      const message = validateField(name, empty);
      assert.equal(typeof message, "string", `${name} accepted ${JSON.stringify(empty)}`);
      assert.ok(message.length > 0);
    }
  }
  assert.equal(validateField("vorname", ""), MESSAGES.vorname);
  assert.equal(validateField("nachname", " "), MESSAGES.nachname);
  assert.equal(validateField("email", ""), MESSAGES.email);
  assert.equal(validateField("nachricht", "\n"), MESSAGES.nachricht);
});

test("filled name fields are valid", () => {
  assert.equal(validateField("vorname", "Mara"), null);
  assert.equal(validateField("nachname", "Beispiel"), null);
});

test("invalid e-mail addresses are rejected with the German message", () => {
  for (const email of ["mara", "mara@beispiel", "mara@@beispiel.at", "ma ra@beispiel.at", "@beispiel.at", "mara@.a"]) {
    assert.equal(validateField("email", email), MESSAGES.emailInvalid, email);
  }
  assert.match(MESSAGES.emailInvalid, /nicht gültig/);
});

test("valid e-mail addresses are accepted", () => {
  for (const email of ["mara@beispiel.at", "office@equicrew.com", " a.b+c@sub.example.org "]) {
    assert.equal(validateField("email", email), null, email);
  }
});

test("Nachricht accepts 5000 characters and rejects 5001", () => {
  assert.equal(MAX_MESSAGE_LENGTH, 5000);
  assert.equal(validateField("nachricht", "a".repeat(5000)), null);
  assert.equal(validateField("nachricht", "a".repeat(5001)), MESSAGES.nachrichtLong);
  assert.match(MESSAGES.nachrichtLong, /5000/);
});

test("validateForm returns no errors for a valid form", () => {
  assert.deepEqual(validateForm(VALID), {});
});

test("validateForm aggregates the message of every invalid field", () => {
  const errors = validateForm({ vorname: "Mara", nachname: "", email: "mara@beispiel", nachricht: "  " });
  assert.deepEqual(errors, {
    nachname: MESSAGES.nachname,
    email: MESSAGES.emailInvalid,
    nachricht: MESSAGES.nachricht,
  });
  assert.deepEqual(Object.keys(validateForm({})).sort(), [...FIELDS].sort());
  assert.deepEqual(Object.keys(validateForm(null)).sort(), [...FIELDS].sort());
});

test("validateForm ignores the honeypot and unknown fields", () => {
  assert.deepEqual(validateForm({ ...VALID, website: "spam", extra: "" }), {});
});
