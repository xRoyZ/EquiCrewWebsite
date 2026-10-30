// Checks of the web service's development server (dev_server.mjs), run in-process on an
// ephemeral port: page documents, directory mapping, path traversal and /js/config.js.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { request } from "node:http";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ROOT, configScript, makeServer, readPort, resolvePath } from "../dev_server.mjs";

let server;
let base;
const savedApiBase = process.env.API_BASE_URL;

before(async () => {
  server = makeServer();
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  if (savedApiBase === undefined) delete process.env.API_BASE_URL;
  else process.env.API_BASE_URL = savedApiBase;
  server.closeAllConnections();
  await new Promise((done) => server.close(done));
});

// A raw request, so a path such as /../ reaches the server unnormalised.
function get(path) {
  return new Promise((done, fail) => {
    const req = request(`${base}${path}`, { method: "GET", path, agent: false }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => done({ status: res.statusCode, headers: res.headers, body }));
    });
    req.on("error", fail);
    req.end();
  });
}

test("configScript writes the API origin without a trailing slash", () => {
  assert.equal(
    configScript("http://127.0.0.1:8000/"),
    'window.EQUICREW_CONFIG = {"apiBase":"http://127.0.0.1:8000"};\n',
  );
});

test("readPort uses 8000 by default and refuses an invalid PORT", () => {
  assert.equal(readPort(""), 8000);
  assert.equal(readPort("8080"), 8080);
  assert.throws(() => readPort("abc"), /PORT/);
  assert.throws(() => readPort("70000"), /PORT/);
});

test("resolvePath keeps every path inside the site directory", () => {
  assert.equal(resolvePath("/kontakt/"), join(ROOT, "kontakt"));
  assert.equal(resolvePath("/../SPEC.md"), null);
  assert.equal(resolvePath("/%2e%2e/%2e%2e/etc/passwd"), null);
  assert.equal(resolvePath("/%E0%A4%A"), null);
});

test("the start page and a directory URL answer with their index.html", async () => {
  const start = await get("/");
  assert.equal(start.status, 200);
  assert.match(start.headers["content-type"], /^text\/html/);
  assert.equal(start.body, readFileSync(join(ROOT, "index.html"), "utf8"));

  const kontakt = await get("/kontakt/");
  assert.equal(kontakt.status, 200);
  assert.equal(kontakt.body, readFileSync(join(ROOT, "kontakt", "index.html"), "utf8"));
});

test("a directory URL without its slash is redirected, unknown paths are 404", async () => {
  const redirect = await get("/impressum");
  assert.equal(redirect.status, 301);
  assert.equal(redirect.headers.location, "/impressum/");
  assert.equal((await get("/gibt-es-nicht/")).status, 404);
});

test("path traversal does not leave the site directory", async () => {
  assert.equal((await get("/../README.md")).status, 404);
  assert.equal((await get("/%2e%2e/README.md")).status, 404);
});

test("/js/config.js carries API_BASE_URL, or the static file when it is unset", async () => {
  process.env.API_BASE_URL = "http://127.0.0.1:8123";
  const dynamic = await get("/js/config.js");
  assert.equal(dynamic.status, 200);
  assert.equal(dynamic.body, configScript("http://127.0.0.1:8123"));
  assert.equal(dynamic.headers["cache-control"], "no-store");

  delete process.env.API_BASE_URL;
  const fallback = await get("/js/config.js");
  assert.equal(fallback.status, 200);
  assert.equal(fallback.body, readFileSync(join(ROOT, "js", "config.js"), "utf8"));
});
