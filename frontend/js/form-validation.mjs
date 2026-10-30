// Client-side validation of the contact form (pure functions, no DOM).
// The messages are the German texts of the approved screens
// (design/mockups/kontakt-fehler.html, design/mockups/script.js).

export const FIELDS = ["vorname", "nachname", "email", "nachricht"];

export const MAX_MESSAGE_LENGTH = 5000;

export const MESSAGES = {
  vorname: "Bitte gib deinen Vornamen an.",
  nachname: "Bitte gib deinen Nachnamen an.",
  email: "Bitte gib deine Email-Adresse an.",
  emailInvalid: "Diese Email-Adresse sieht nicht gültig aus.",
  nachricht: "Bitte schreib uns eine Nachricht.",
  nachrichtLong: `Die Nachricht darf höchstens ${MAX_MESSAGE_LENGTH} Zeichen lang sein.`,
};

// local@domain.tld — no whitespace, exactly one "@", a dot in the domain, a TLD of 2+ chars.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/**
 * Validates one field of the contact form.
 * @param {string} name one of FIELDS
 * @param {unknown} value the field's current value
 * @returns {string|null} the German error message, or null when the value is valid
 */
export function validateField(name, value) {
  const raw = typeof value === "string" ? value : value == null ? "" : String(value);
  const trimmed = raw.trim();
  switch (name) {
    case "vorname":
    case "nachname":
      return trimmed ? null : MESSAGES[name];
    case "email":
      if (!trimmed) return MESSAGES.email;
      return EMAIL.test(trimmed) ? null : MESSAGES.emailInvalid;
    case "nachricht":
      if (!trimmed) return MESSAGES.nachricht;
      return raw.length > MAX_MESSAGE_LENGTH ? MESSAGES.nachrichtLong : null;
    default:
      return null;
  }
}

/**
 * Validates every field of the contact form.
 * @param {Record<string, unknown>} values field name -> value
 * @returns {Record<string, string>} field name -> message, only for the invalid fields
 *   (an empty object means the form is valid)
 */
export function validateForm(values) {
  const source = values && typeof values === "object" ? values : {};
  const errors = {};
  for (const name of FIELDS) {
    const message = validateField(name, source[name]);
    if (message) errors[name] = message;
  }
  return errors;
}
