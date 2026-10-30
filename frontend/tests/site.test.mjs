// Checks of the UI kit (frontend/css/components.css + css/kit/*) and of js/site.js (node --test).
// The CSS checks are static; the menu and year checks run site.js against a minimal fake DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (file) => readFileSync(join(ROOT, file), "utf8");

const KIT = ["frame", "sections", "form", "contact", "legal"].map((n) => `css/kit/${n}.css`);

// The body of every `@media (prefers-reduced-motion: reduce) { … }` block in a stylesheet.
function reducedMotionBlocks(css) {
  const blocks = [];
  const re = /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{/g;
  let match;
  while ((match = re.exec(css))) {
    let depth = 1;
    let i = re.lastIndex;
    for (; i < css.length && depth > 0; i += 1) {
      if (css[i] === "{") depth += 1;
      else if (css[i] === "}") depth -= 1;
    }
    blocks.push(css.slice(re.lastIndex, i - 1));
  }
  return blocks;
}

test("components.css imports the kit files in order, and each exists", () => {
  const css = read("css/components.css");
  const imports = [...css.matchAll(/@import\s+url\(\s*"([^"]+)"\s*\)/g)].map((m) => m[1]);
  assert.deepEqual(
    imports,
    KIT.map((f) => f.replace("css/", "")),
  );
  for (const file of KIT) assert.ok(existsSync(join(ROOT, file)), `${file} is missing`);
});

test("the kit CSS disables transitions and animations under prefers-reduced-motion", () => {
  const blocks = KIT.flatMap((file) => reducedMotionBlocks(read(file)));
  assert.ok(blocks.length > 0, "no prefers-reduced-motion block in the kit");
  const all = blocks.join("\n");
  assert.match(all, /transition(-duration)?\s*:\s*(none|0\.01ms)/, "transitions are not disabled");
  assert.match(all, /animation(-duration)?\s*:\s*(none|0\.01ms)/, "animations are not disabled");
  // the menu does not slide, the reveal does not fade in
  assert.match(all, /\.site-nav[\s\S]*transform\s*:\s*none/);
  assert.match(all, /is-reveal-pending[\s\S]*opacity\s*:\s*1/);
});

test("the kit defines the shared component classes of the screens", () => {
  const css = KIT.map(read).join("\n") + read("css/base.css");
  const classes = [
    "skip", "site-header", "header-row", "wordmark", "menu-btn", "icon", "icon-open", "icon-close",
    "site-nav", "nav-link", "site-footer", "footer-inner", "footer-col", "footer-name",
    "footer-links", "footer-small", "page", "h-1", "num", "btn", "btn-secondary", "btn-primary",
    "link", "label", "muted", "lead", "h-2", "h-3", "page-head", "main-end", "section", "band",
    "cta", "cta-action", "sheet", "cell", "grid", "g-1-5", "g-6-12", "g-1-7", "g-8-12", "g-1-9",
    "form", "form-row", "field", "field-error", "hp", "form-alert", "form-foot", "form-note",
    "contact-grid", "contact-card", "thanks", "legal", "placeholder",
  ];
  for (const name of classes) {
    assert.match(css, new RegExp(`\\.${name}(?![\\w-])`), `.${name} is not defined`);
  }
  assert.match(css, /\.nav-link\[aria-current="page"\]/);
  assert.match(css, /\.btn-primary:disabled/);
  assert.match(css, /\.btn-primary\.is-sending/);
  assert.match(css, /\.field \[aria-invalid="true"\]/);
});

test("the kit CSS loads nothing from another host", () => {
  for (const file of ["css/components.css", ...KIT]) {
    assert.doesNotMatch(read(file), /url\(\s*["']?(https?:)?\/\//i, file);
  }
});

test("site.js references nav-toggle, aria-expanded and data-reveal", () => {
  const js = read("js/site.js");
  assert.match(js, /nav-toggle/);
  assert.match(js, /aria-expanded/);
  assert.match(js, /data-reveal/);
  assert.match(js, /prefers-reduced-motion/);
});

// ---- behaviour against a minimal fake DOM ------------------------------------------------

function makeElement(attrs = {}) {
  const classes = new Set();
  const listeners = {};
  const el = {
    attrs: { ...attrs },
    textContent: "",
    children: [],
    parent: null,
    focused: false,
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
      toggle: (c, force) => {
        const on = force === undefined ? !classes.has(c) : force;
        if (on) classes.add(c);
        else classes.delete(c);
        return on;
      },
    },
    getAttribute: (n) => (n in el.attrs ? el.attrs[n] : null),
    setAttribute: (n, v) => {
      el.attrs[n] = String(v);
    },
    addEventListener: (type, fn) => {
      (listeners[type] ||= []).push(fn);
    },
    dispatch: (type, event) => {
      for (const fn of listeners[type] || []) fn(event);
    },
    focus: () => {
      el.focused = true;
    },
    contains: (other) => {
      for (let node = other; node; node = node.parent) if (node === el) return true;
      return false;
    },
    closest: (selector) => {
      for (let node = el; node; node = node.parent) if (node.tag === selector) return node;
      return null;
    },
    append: (child) => {
      child.parent = el;
      el.children.push(child);
    },
  };
  return el;
}

function loadSite() {
  const doc = makeElement();
  const toggle = makeElement({ "aria-expanded": "false", "aria-controls": "site-nav" });
  const nav = makeElement({ id: "site-nav" });
  const link = makeElement({ href: "/kontakt/" });
  link.tag = "a";
  nav.append(link);
  const outside = makeElement();
  const years = [makeElement(), makeElement()];

  // events bubble from the target up its parents to the document
  const fire = (target, type, extra = {}) => {
    const event = { type, target, ...extra };
    for (let node = target; node; node = node.parent) node.dispatch(type, event);
    doc.dispatch(type, event);
  };

  Object.assign(doc, {
    querySelector: (sel) => (sel === "button.nav-toggle" ? toggle : null),
    querySelectorAll: (sel) => (sel === "[data-year]" ? years : []),
    getElementById: (id) => (id === "site-nav" ? nav : null),
    documentElement: { clientHeight: 800 },
  });
  const window = {
    innerHeight: 800,
    matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  };
  vm.runInNewContext(read("js/site.js"), { window, document: doc });
  return { doc, toggle, nav, link, outside, years, fire };
}

test("the menu button opens and closes the navigation and keeps aria-expanded in step", () => {
  const { toggle, nav, fire } = loadSite();
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  fire(toggle, "click");
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.ok(nav.classList.contains("is-open"));
  fire(toggle, "click");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.ok(!nav.classList.contains("is-open"));
});

test("Escape closes the open menu and returns focus to the button", () => {
  const { toggle, nav, doc, fire } = loadSite();
  fire(toggle, "click");
  doc.dispatch("keydown", { key: "Escape" });
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.ok(!nav.classList.contains("is-open"));
  assert.ok(toggle.focused);
});

test("a click on a navigation link or outside the menu closes it", () => {
  const { toggle, link, outside, fire } = loadSite();
  fire(toggle, "click");
  fire(link, "click");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  fire(toggle, "click");
  fire(outside, "click");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
});

test("every [data-year] shows the current year", () => {
  const { years } = loadSite();
  const now = String(new Date().getFullYear());
  for (const el of years) assert.equal(el.textContent, now);
});
