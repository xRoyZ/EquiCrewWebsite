// Structure checks for the six page documents of the website (node --test).
// They assert the shared frame — head metadata, header navigation, footer — and that no
// document references a third-party host. Nothing here asserts the content of <main>.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const PAGES = [
  { route: "/", file: "index.html", css: "start" },
  { route: "/ueber-uns/", file: "ueber-uns/index.html", css: "ueber-uns" },
  { route: "/equicube/", file: "equicube/index.html", css: "equicube" },
  { route: "/kontakt/", file: "kontakt/index.html", css: "kontakt" },
  { route: "/impressum/", file: "impressum/index.html", css: "impressum" },
  { route: "/datenschutz/", file: "datenschutz/index.html", css: "datenschutz" },
];

const NAV_TARGETS = ["/", "/ueber-uns/", "/equicube/", "/kontakt/", "/impressum/"];
const FOOTER_TARGETS = ["/kontakt/", "/impressum/", "/datenschutz/"];

const read = (file) => readFileSync(join(ROOT, file), "utf8");

function section(html, tag) {
  const match = html.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`, "i"));
  return match ? match[0] : "";
}

function hrefs(html) {
  return [...html.matchAll(/\bhref\s*=\s*"([^"]*)"/gi)].map((m) => m[1]);
}

// Resolve a reference the way a browser does on the page's served route
// (e.g. "../css/base.css" on /kontakt/ -> "/css/base.css").
function served(ref, route) {
  return new URL(ref, `http://site.test${route}`).pathname;
}

function scripts(html) {
  return [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/gi)].map((m) => m[1]);
}

function metaContent(html, attr, name) {
  const re = new RegExp(`<meta\\s+${attr}="${name}"\\s+content="([^"]*)"`, "i");
  const match = html.match(re);
  return match ? match[1].trim() : "";
}

function title(html) {
  const match = html.match(/<title>([^<]*)<\/title>/i);
  return match ? match[1].trim() : "";
}

test("every page document exists", () => {
  for (const page of PAGES) {
    assert.ok(existsSync(join(ROOT, page.file)), `${page.file} is missing`);
  }
});

test('every document is German (<html lang="de">)', () => {
  for (const page of PAGES) {
    assert.match(read(page.file), /<html\s+lang="de"\s*>/i, page.file);
  }
});

test("titles and meta descriptions are non-empty and unique", () => {
  const titles = PAGES.map((p) => title(read(p.file)));
  const descriptions = PAGES.map((p) => metaContent(read(p.file), "name", "description"));
  titles.forEach((t, i) => assert.ok(t.length > 0, `${PAGES[i].file} has no title`));
  descriptions.forEach((d, i) => assert.ok(d.length > 0, `${PAGES[i].file} has no description`));
  assert.equal(new Set(titles).size, PAGES.length, "titles are not unique");
  assert.equal(new Set(descriptions).size, PAGES.length, "descriptions are not unique");
});

test("every document carries canonical and Open Graph tags for its own route", () => {
  for (const page of PAGES) {
    const html = read(page.file);
    const canonical = html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/i);
    assert.ok(canonical, `${page.file} has no canonical link`);
    assert.ok(new URL(canonical[1]).pathname === page.route, `${page.file} canonical route`);
    assert.equal(metaContent(html, "property", "og:url"), canonical[1], page.file);
    assert.equal(metaContent(html, "property", "og:title"), title(html), page.file);
    assert.ok(metaContent(html, "property", "og:description").length > 0, page.file);
  }
});

test("every document links the shared fonts, styles and site script", () => {
  for (const page of PAGES) {
    const html = read(page.file);
    const links = hrefs(html).map((h) => served(h, page.route));
    for (const href of [
      "/fonts/red-hat-display/font.css",
      "/fonts/albert-sans/font.css",
      "/css/base.css",
      "/css/components.css",
      `/css/pages/${page.css}.css`,
    ]) {
      assert.ok(links.includes(href), `${page.file} does not link ${href}`);
      assert.ok(existsSync(join(ROOT, href)), `${href} does not exist`);
    }
    const src = scripts(html).map((s) => served(s, page.route));
    assert.ok(src.includes("/js/site.js"), `${page.file} does not load /js/site.js`);
    assert.match(html, /<script src="[^"]*js\/site\.js" defer><\/script>/, page.file);
  }
});

test("the Kontakt page loads /js/config.js before any other script", () => {
  const html = read("kontakt/index.html");
  const src = scripts(html).map((s) => served(s, "/kontakt/"));
  assert.equal(src[0], "/js/config.js");
  assert.ok(existsSync(join(ROOT, "js/config.js")));
});

test("the header links every navigation target and marks only the current page", () => {
  for (const page of PAGES) {
    const header = section(read(page.file), "header");
    assert.ok(header, `${page.file} has no <header>`);
    const links = hrefs(header);
    for (const target of NAV_TARGETS) {
      assert.ok(links.includes(target), `${page.file} header lacks ${target}`);
    }
    assert.match(header, /<button[^>]*class="[^"]*\bnav-toggle\b[^"]*"[^>]*aria-expanded="false"/);
    assert.match(header, /aria-controls="site-nav"/);
    assert.match(header, /<nav[^>]*id="site-nav"/);
    const current = [...header.matchAll(/<a[^>]*href="([^"]+)"[^>]*aria-current="page"/g)];
    if (NAV_TARGETS.includes(page.route)) {
      assert.equal(current.length, 1, `${page.file} must mark exactly one entry`);
      assert.equal(current[0][1], page.route, `${page.file} marks the wrong entry`);
    } else {
      assert.equal(current.length, 0, `${page.file} must mark no entry`);
    }
  }
});

const NAV_ENTRIES = [
  ["/", "Start"],
  ["/ueber-uns/", "Über uns"],
  ["/equicube/", "EquiCube"],
  ["/kontakt/", "Kontakt"],
  ["/impressum/", "Impressum"],
];

function siteNav(html) {
  const match = html.match(/<nav\b[^>]*\bid="site-nav"[^>]*>[\s\S]*?<\/nav>/i);
  return match ? match[0] : "";
}

function navLinks(nav) {
  return [...nav.matchAll(/<a\b([^>]*)>([^<]*)<\/a>/gi)].map((m) => ({
    attrs: m[1],
    href: (m[1].match(/\bhref="([^"]*)"/i) || [])[1],
    text: m[2].trim(),
    current: /\baria-current="page"/i.test(m[1]),
  }));
}

test("nav #site-nav lists Start, Über uns, EquiCube, Kontakt and Impressum in order on every page", () => {
  for (const page of PAGES) {
    const nav = siteNav(read(page.file));
    assert.ok(nav, `${page.file} has no nav#site-nav`);
    const links = navLinks(nav);
    assert.deepEqual(
      links.map((l) => [l.href, l.text]),
      NAV_ENTRIES,
      `${page.file} nav entries differ`,
    );
    for (const link of links) {
      assert.match(link.attrs, /\bclass="nav-link"/, `${page.file} ${link.href} lacks nav-link`);
    }
    const impressum = links.find((l) => l.href === "/impressum/");
    assert.ok(impressum, `${page.file} nav does not link /impressum/`);
  }
});

test("exactly the current page's nav entry carries aria-current, Datenschutz marks none", () => {
  for (const page of PAGES) {
    const current = navLinks(siteNav(read(page.file))).filter((l) => l.current);
    if (page.route === "/datenschutz/") {
      assert.equal(current.length, 0, `${page.file} must mark no nav entry`);
    } else {
      assert.equal(current.length, 1, `${page.file} must mark exactly one nav entry`);
      assert.equal(current[0].href, page.route, `${page.file} marks the wrong nav entry`);
    }
  }
});

test("the footer has the address, mailto, tel, legal links and the year", () => {
  for (const page of PAGES) {
    const footer = section(read(page.file), "footer");
    assert.ok(footer, `${page.file} has no <footer>`);
    const links = hrefs(footer);
    assert.ok(links.includes("mailto:office@equicrew.com"), `${page.file} footer mailto`);
    assert.ok(links.includes("tel:+436504593129"), `${page.file} footer tel`);
    for (const target of FOOTER_TARGETS) {
      assert.ok(links.includes(target), `${page.file} footer lacks ${target}`);
    }
    for (const text of ["EquiCrew FlexCo", "Marktplatz 14", "4310 Mauthausen", "Österreich", "+43 650 4593 129"]) {
      assert.ok(footer.includes(text), `${page.file} footer lacks "${text}"`);
    }
    assert.match(footer, /<span data-year>\d{4}<\/span>/, `${page.file} footer year`);
  }
});

test("internal links point at declared routes or own files", () => {
  const routes = new Set(PAGES.map((p) => p.route));
  for (const page of PAGES) {
    for (const href of hrefs(read(page.file))) {
      if (/^(mailto:|tel:|#|https?:)/.test(href)) continue;
      const path = served(href, page.route);
      // Both the served route and the file next to the document must exist.
      const onDisk = join(ROOT, dirname(page.file), href.split(/[?#]/)[0]);
      if (href.startsWith("/")) {
        assert.ok(routes.has(path), `${page.file}: ${href} is not a page route`);
      } else {
        assert.ok(existsSync(onDisk), `${page.file}: ${href} does not exist next to the document`);
      }
    }
  }
});

test("no document loads anything from an external http(s) host", () => {
  for (const page of PAGES) {
    const html = read(page.file);
    // The canonical link names the page's own public address; it is never requested.
    const withoutCanonical = html.replace(/<link\s+rel="canonical"[^>]*>/gi, "");
    const refs = [...withoutCanonical.matchAll(/\b(?:src|href|srcset|action)\s*=\s*"([^"]*)"/gi)].map((m) => m[1]);
    for (const ref of refs) {
      assert.doesNotMatch(ref, /^\s*(https?:)?\/\//i, `${page.file} references external ${ref}`);
    }
    assert.doesNotMatch(withoutCanonical, /@import|url\(\s*["']?(https?:)?\/\//i, page.file);
  }
});

test("the shared stylesheets and font files reference no external host", () => {
  const files = [
    "css/base.css",
    "css/components.css",
    "fonts/red-hat-display/font.css",
    "fonts/albert-sans/font.css",
  ];
  for (const file of files) {
    const css = read(file);
    assert.doesNotMatch(css, /url\(\s*["']?(https?:)?\/\//i, file);
    assert.doesNotMatch(css, /@import\s+(url\()?\s*["']?(https?:)?\/\//i, file);
    for (const m of css.matchAll(/url\(\s*"([^"]+)"\s*\)/g)) {
      assert.ok(existsSync(join(ROOT, dirname(file), m[1])), `${file}: ${m[1]} missing`);
    }
  }
});
