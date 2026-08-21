// Typed fetch wrappers over the M1 operator API (`apps/platform_core/api/app.py`).
//
// **The API address defaults to the loopback binding SEC-002 gives the API, and
// refuses anything else.** `VITE_API_BASE` can move it for a build served from
// somewhere other than the default, but a non-loopback host is refused: the
// operator API only ever binds to `127.0.0.1`, and a dashboard that could be
// pointed at a remote host would be a way around that constraint rather than a
// client of it (same rule `experiments/integrated-p0/dashboard/src/api.ts` applies
// to `VITE_API_BASE` and `vite.config.ts` applies to `COSMA_API_ORIGIN`).

import type {
  AttemptPage,
  HealthResponse,
  Job,
  JobPage,
  JobState,
  MetricsResponse,
  RetryOutcome,
} from "./types";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

export function apiBase(): string {
  const configured: unknown = import.meta.env.VITE_API_BASE;
  const base = typeof configured === "string" && configured !== "" ? configured : DEFAULT_API_BASE;
  const host = new URL(base).hostname;
  if (!LOOPBACK_HOSTS.has(host)) {
    throw new Error(
      `VITE_API_BASE must name a loopback host, not ${host} — the operator API ` +
        "binds to 127.0.0.1 only and this dashboard must not become a way to reach anything else",
    );
  }
  return base.replace(/\/$/, "");
}

/** Thrown for any status the caller has no specific handling for. */
export class ApiFailure extends Error {
  readonly status: number;

  constructor(status: number, body: string) {
    super(`${status} — ${body}`);
    this.status = status;
    this.name = "ApiFailure";
  }
}

async function getJson<T>(path: string, okStatuses: readonly number[] = []): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { headers: { accept: "application/json" } });
  if (!response.ok && !okStatuses.includes(response.status)) {
    throw new ApiFailure(response.status, await response.text());
  }
  return (await response.json()) as T;
}

export function listJobs(state: JobState | null, limit: number, offset: number): Promise<JobPage> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (state !== null) {
    query.set("state", state);
  }
  return getJson<JobPage>(`/jobs?${query.toString()}`);
}

export function readJob(jobId: string): Promise<Job> {
  return getJson<Job>(`/jobs/${encodeURIComponent(jobId)}`);
}

/**
 * The attempts of one job. `wantProtected` adds `?debug=protected`, the explicit
 * action SEC-004 requires: protected detail is reachable, and only by asking for
 * it by name.
 */
export function readAttempts(jobId: string, wantProtected: boolean): Promise<AttemptPage> {
  const suffix = wantProtected ? "?debug=protected" : "";
  return getJson<AttemptPage>(`/jobs/${encodeURIComponent(jobId)}/attempts${suffix}`);
}

/**
 * Request a retry. A `409` and a `404` are returned rather than thrown, because
 * both are answers the screen has to display in full; anything else is a failure
 * of the dashboard's own making and is thrown.
 */
export async function requestRetry(jobId: string): Promise<RetryOutcome> {
  const response = await fetch(`${apiBase()}/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    headers: { accept: "application/json" },
  });
  if (response.ok || response.status === 409 || response.status === 404) {
    return (await response.json()) as RetryOutcome;
  }
  throw new ApiFailure(response.status, await response.text());
}

/** `/health` answers `503` on a failure with a body worth showing, not throwing. */
export function readHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health", [503]);
}

export function readMetrics(): Promise<MetricsResponse> {
  return getJson<MetricsResponse>("/metrics");
}
