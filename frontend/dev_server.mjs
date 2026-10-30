// Development server for the EquiCrew website — the web service's start command per
// RUN.json (`node dev_server.mjs`, run from frontend/). Node standard library only.
//
// Serves the files of this directory on the port from the environment variable PORT
// (default 8000). Directory URLs such as /kontakt/ answer with their index.html.
// The path /js/config.js is answered dynamically with the API origin from the
// environment variable API_BASE_URL; when it is unset, the static file is served,
// whose apiBase "" means "same origin".
//
// Usage:  PORT=8080 API_BASE_URL=http://127.0.0.1:8000 node dev_server.mjs

import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)));
const CONFIG_PATH = "/js/config.js";
const DEFAULT_PORT = 8000;

// Content types of the files this site serves, independent of the host's mime database.
const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".woff2": "font/woff2",
  ".webp": "image/webp",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".json": "application/json",
};

/** Body of /js/config.js for the given API origin. */
export function configScript(apiBase) {
  const config = { apiBase: String(apiBase).replace(/\/+$/, "") };
  return `window.EQUICREW_CONFIG = ${JSON.stringify(config)};\n`;
}

/** The API origin from API_BASE_URL, or null when it is unset or empty. */
function apiBaseFromEnv() {
  const value = (process.env.API_BASE_URL ?? "").trim();
  return value || null;
}

/**
 * Map a URL path to a file path inside root, or null when it would leave root
 * (path traversal) or cannot be decoded.
 */
export function resolvePath(urlPath, root = ROOT) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch {
    return null;
  }
  if (decoded.includes("\0")) return null;
  const target = resolve(join(root, decoded));
  if (target !== root && !target.startsWith(root + sep)) return null;
  return target;
}

function sendText(res, status, text, head) {
  const body = Buffer.from(text, "utf8");
  res.writeHead(status, {
    "Content-Type": "text/plain; charset=utf-8",
    "Content-Length": body.length,
  });
  res.end(head ? undefined : body);
}

async function handle(req, res) {
  res.setHeader("X-Content-Type-Options", "nosniff");
  const head = req.method === "HEAD";
  if (req.method !== "GET" && !head) {
    res.setHeader("Allow", "GET, HEAD");
    sendText(res, 405, "Method Not Allowed", head);
    return;
  }

  const url = new URL(req.url ?? "/", "http://localhost");
  const apiBase = apiBaseFromEnv();
  if (url.pathname === CONFIG_PATH && apiBase !== null) {
    const body = Buffer.from(configScript(apiBase), "utf8");
    res.writeHead(200, {
      "Content-Type": "text/javascript; charset=utf-8",
      "Content-Length": body.length,
      "Cache-Control": "no-store",
    });
    res.end(head ? undefined : body);
    return;
  }

  let filePath = resolvePath(url.pathname);
  if (filePath === null) {
    sendText(res, 404, "Not Found", head);
    return;
  }

  let info;
  try {
    info = await stat(filePath);
    if (info.isDirectory()) {
      if (!url.pathname.endsWith("/")) {
        // Same as a static host: a directory URL without its slash is redirected.
        res.writeHead(301, { Location: `${url.pathname}/${url.search}`, "Content-Length": 0 });
        res.end();
        return;
      }
      filePath = join(filePath, "index.html");
      info = await stat(filePath);
    }
  } catch {
    sendText(res, 404, "Not Found", head);
    return;
  }
  if (!info.isFile()) {
    sendText(res, 404, "Not Found", head);
    return;
  }

  res.writeHead(200, {
    "Content-Type": CONTENT_TYPES[extname(filePath).toLowerCase()] ?? "application/octet-stream",
    "Content-Length": info.size,
  });
  if (head) {
    res.end();
    return;
  }
  const stream = createReadStream(filePath);
  stream.on("error", () => res.destroy());
  stream.pipe(res);
}

/** Create (but do not start) the HTTP server for this directory. */
export function makeServer() {
  return createServer((req, res) => {
    handle(req, res).catch(() => {
      if (!res.headersSent) sendText(res, 500, "Internal Server Error", false);
      else res.destroy();
    });
    // Request line and status only; the visitor's address is not written to the log.
    res.on("finish", () => {
      process.stderr.write(`[web] "${req.method} ${req.url}" ${res.statusCode}\n`);
    });
  });
}

/** PORT from the environment, naming the variable when it is not a valid port. */
export function readPort(raw = process.env.PORT) {
  const value = (raw ?? "").trim();
  if (!value) return DEFAULT_PORT;
  const port = Number(value);
  if (!Number.isInteger(port) || port <= 0 || port >= 65536) {
    throw new Error(`PORT must be a number between 1 and 65535, got ${JSON.stringify(value)}`);
  }
  return port;
}

function main() {
  let port;
  try {
    port = readPort();
  } catch (err) {
    process.stderr.write(`${err.message}\n`);
    process.exit(1);
  }
  const server = makeServer();
  server.on("error", (err) => {
    process.stderr.write(`Cannot listen on port ${port}: ${err.code ?? err.message}\n`);
    process.exit(1);
  });
  server.listen(port, "0.0.0.0", () => {
    const api = apiBaseFromEnv() ?? "same origin";
    process.stdout.write(`[web] serving ${ROOT} on http://localhost:${port}/ (API: ${api})\n`);
  });
  const stop = () => {
    server.close(() => process.exit(0));
    server.closeAllConnections();
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
