// Vite configuration for the disposable P0-A operator dashboard.
//
// Two things are decided here and both are security-relevant, so they are stated
// where they are read rather than in the README alone.
//
// **The API address is never compiled in.** In development every API path is
// proxied to a loopback origin, so the browser only ever talks to the origin Vite
// itself is serving and no absolute address reaches the bundle. `COSMA_API_ORIGIN`
// can move the proxy target, and `loopbackOnly` refuses anything that is not a
// loopback host — SEC-002 constrains the API to `127.0.0.1` or `::1`, and a
// dashboard that could be pointed at a remote host would be a way around that
// constraint rather than a client of it.
//
// **No React plugin.** Vite transforms `.tsx` with esbuild on its own, reading
// `"jsx": "react-jsx"` from `tsconfig.json`. `@vitejs/plugin-react` would add Fast
// Refresh, which is a convenience for a UI under design; this is instrumentation
// with two screens, and a full reload costs nothing. DP-006 D6 puts the floor at
// Vite, React, TypeScript, and `fetch`, and this keeps it there.

import { defineConfig } from "vite";

const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

/** Every API path the dashboard reads. Anything else is served by Vite. */
const API_PATHS = ["/jobs", "/health", "/metrics", "/events"];

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);

function loopbackOnly(origin: string): string {
  let parsed: URL;
  try {
    parsed = new URL(origin);
  } catch {
    throw new Error(`COSMA_API_ORIGIN is not a URL: ${origin}`);
  }
  if (parsed.protocol !== "http:") {
    throw new Error(`COSMA_API_ORIGIN must be http:, not ${parsed.protocol} (${origin})`);
  }
  if (!LOOPBACK_HOSTS.has(parsed.hostname) && !LOOPBACK_HOSTS.has(`[${parsed.hostname}]`)) {
    throw new Error(
      `COSMA_API_ORIGIN must name a loopback host, not ${parsed.hostname} — ` +
        "SEC-002 binds the operator API to 127.0.0.1 or ::1 and this dashboard " +
        "must not become a way to reach anything else",
    );
  }
  return parsed.origin;
}

const target = loopbackOnly(process.env.COSMA_API_ORIGIN ?? DEFAULT_API_ORIGIN);

export default defineConfig({
  server: {
    host: "127.0.0.1",
    proxy: Object.fromEntries(API_PATHS.map((path) => [path, { target, changeOrigin: false }])),
  },
  build: {
    // Fixed asset names, no content hash. Not a caching preference: the P0-A
    // boundary guard walks the whole experiment tree and checks every file's *path*
    // for reserved segments, and it does not skip build output. A content hash is
    // random text, and random text can split into a reserved segment — which would
    // fail `tests/environment` for a reason that has nothing to do with this code,
    // on one build in many. Fixed names remove the possibility rather than rely on
    // luck, and cost nothing: nothing caches this bundle.
    // The guard is not modified to accommodate this; the output is.
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
      },
    },
  },
});
