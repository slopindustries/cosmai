import { afterEach, describe, expect, it, vi } from "vitest";

import { apiBase, credentialRefName } from "../client";

/**
 * M-X3 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`): `credentialRefName` (this
 * file) and `apps/domain/api.py`'s `credential_ref_for` must derive the same ref for
 * the same `(source_id, purpose)` pair — the whole point of showing the operator this
 * name is that it is the key they populate on the write path, which runs the Python
 * version. The two used to diverge on consecutive separators and leading/trailing
 * ones; this vector table is asserted identically here and in
 * `apps/tests/test_credential_ref_derivation_agrees.py` (same vectors, same order).
 */
const VECTORS: ReadonlyArray<readonly [string, string, string]> = [
  ["naver-blog", "client_id", "COSMA_SRC_NAVER_BLOG_CLIENT_ID"],
  ["probe-blog", "token", "COSMA_SRC_PROBE_BLOG_TOKEN"],
  ["a..b", "token", "COSMA_SRC_A_B_TOKEN"],
  [".lead", "token", "COSMA_SRC_LEAD_TOKEN"],
  ["trail.", "token", "COSMA_SRC_TRAIL_TOKEN"],
  ["mixed_CASE-123", "purpose", "COSMA_SRC_MIXED_CASE_123_PURPOSE"],
];

describe("credentialRefName", () => {
  it.each(VECTORS)("derives %s / %s as %s", (sourceId, purpose, expected) => {
    expect(credentialRefName(sourceId, purpose)).toBe(expected);
  });
});

/**
 * M-R9 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`): `apiBase()`'s own loopback
 * refusal (SEC-002 — the operator API binds `127.0.0.1` only, and a dashboard build
 * that could be pointed anywhere else would be a way around that constraint) had no
 * test before this fix wave; M5-RECORD had wrongly credited `vite.config.ts` with a
 * loopback rule this tree's own config file does not have, which is what let the
 * absence go unnoticed.
 */
describe("apiBase", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("refuses a VITE_API_BASE naming a non-loopback host", () => {
    vi.stubEnv("VITE_API_BASE", "http://evil.example.com:8100");
    expect(() => apiBase()).toThrow(/loopback/);
  });

  it("accepts an explicit loopback VITE_API_BASE", () => {
    vi.stubEnv("VITE_API_BASE", "http://127.0.0.1:9999");
    expect(apiBase()).toBe("http://127.0.0.1:9999");
  });

  it("defaults to the loopback base when unset", () => {
    vi.stubEnv("VITE_API_BASE", "");
    expect(apiBase()).toBe("http://127.0.0.1:8100");
  });
});
