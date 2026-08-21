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
  CredentialWriteRefusal,
  DomainRefused,
  HealthResponse,
  Job,
  JobEnqueued,
  JobPage,
  JobState,
  MetricsResponse,
  NormalizeRunCreated,
  RawItemPage,
  RawSummary,
  ResultList,
  RetryOutcome,
  Schedule,
  ScheduleWrite,
  Snapshot,
  SnapshotList,
  Source,
  SourceList,
} from "./types";

// M-X2 (docs/agent-workflow/reviews/REVIEW-M2-M7.md): matches
// `platform_core.config`'s own `COSMA_API_PORT` default — `8000` collides with
// trend-radar's live dashboard (DP-031 D3); the M7 demo ran on `8100`.
const DEFAULT_API_BASE = "http://127.0.0.1:8100";

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

// --------------------------------------------------------------------------- //
// The domain surface (`apps/domain/api.py`, M2). Real and live as of batch
// 5-final — every function below was reconciled against that file's actual
// route signatures after `git merge dev`, not against the plan's prose
// summary (which turned out to be wrong about `/export/results`'s format
// options; see `buildExportUrl`'s own note and docs/p1/M5-RECORD.md).
//
// `POST /sources/{id}/collect` and `POST /sources/{id}/import` live in
// `apps/addon_host/api.py` (M3), composed onto this same surface at
// `python -m addon_host` — not in `apps/domain/api.py`, which still declines
// to build them for the reason its own docstring names (a job nothing could
// claim, at the time M2 was written). `startCollection`/`startImport` below
// were added in the B12 fix wave (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`):
// the routes had existed since M3 merged, and the dashboard shipped with no
// client function for them and a note telling the operator they did not exist.
// --------------------------------------------------------------------------- //

/**
 * Enqueue one collect job for this source (`POST /sources/{id}/collect`,
 * `apps/addon_host/api.py`). Takes no body — everything about the request the
 * collector will make is read from the row this identifier names. A `404`
 * (no such source) or `409` (wrong kind, or disabled) is returned rather than
 * thrown, the same convention `sealSnapshot` and `createNormalizeRun` use.
 */
export async function startCollection(sourceId: string): Promise<JobEnqueued | DomainRefused> {
  const response = await fetch(`${apiBase()}/sources/${encodeURIComponent(sourceId)}/collect`, {
    method: "POST",
    headers: { accept: "application/json" },
  });
  if (response.ok || [404, 409].includes(response.status)) {
    return (await response.json()) as JobEnqueued | DomainRefused;
  }
  throw new ApiFailure(response.status, await response.text());
}

/**
 * Enqueue one import job for this source (`POST /sources/{id}/import`,
 * `apps/addon_host/api.py`). The dataset half of `startCollection`, same
 * shape and same refusal handling.
 */
export async function startImport(sourceId: string): Promise<JobEnqueued | DomainRefused> {
  const response = await fetch(`${apiBase()}/sources/${encodeURIComponent(sourceId)}/import`, {
    method: "POST",
    headers: { accept: "application/json" },
  });
  if (response.ok || [404, 409].includes(response.status)) {
    return (await response.json()) as JobEnqueued | DomainRefused;
  }
  throw new ApiFailure(response.status, await response.text());
}

export function listSources(): Promise<SourceList> {
  return getJson<SourceList>("/sources");
}

export function readSource(sourceId: string): Promise<Source> {
  return getJson<Source>(`/sources/${encodeURIComponent(sourceId)}`);
}

/** `GET /sources/{id}/raw`: counts and a last-retrieved instant, never payloads. */
export function readRawSummary(sourceId: string): Promise<RawSummary> {
  return getJson<RawSummary>(`/sources/${encodeURIComponent(sourceId)}/raw`);
}

/**
 * The env-file key name `apps/domain/api.py`'s `credential_ref_for` derives:
 * `COSMA_SRC_<SOURCE_ID>_<PURPOSE>`. M-X3 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`):
 * this used to replace each forbidden character individually and keep leading/trailing
 * underscores, diverging from `credential_ref_for`'s collapse-and-strip on consecutive
 * separators and edges (`"a..b"` → `A__B` here vs `A_B` there; `".lead"` → `_LEAD` here
 * vs `LEAD` there) — the operator-facing purpose of this function is showing which key
 * to populate, so a divergence here is a UI that names the wrong key. Now matches
 * `credential_ref_for` exactly: `test_credential_ref_derivation_agrees.test.ts` and
 * `apps/tests/test_credential_ref_derivation_agrees.py` assert both sides against the
 * same vector table.
 */
function envSafe(value: string): string {
  return value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function credentialRefName(sourceId: string, purpose: string): string {
  return `COSMA_SRC_${envSafe(sourceId)}_${envSafe(purpose)}`;
}

/** Thrown when the credentials write route refuses with the `422` `error_class`/`error_summary` shape — never the submitted value, which this type has no field for. */
export class CredentialWriteFailure extends Error {
  readonly error_class: string;
  readonly error_summary: string;

  constructor(refusal: CredentialWriteRefusal) {
    super(`${refusal.error_class}: ${refusal.error_summary}`);
    this.name = "CredentialWriteFailure";
    this.error_class = refusal.error_class;
    this.error_summary = refusal.error_summary;
  }
}

export function isCredentialWriteFailure(error: unknown): error is CredentialWriteFailure {
  return error instanceof CredentialWriteFailure;
}

function parseCredentialRefusal(bodyText: string): CredentialWriteRefusal | null {
  try {
    const parsed: unknown = JSON.parse(bodyText);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as Record<string, unknown>).error_class === "string" &&
      typeof (parsed as Record<string, unknown>).error_summary === "string"
    ) {
      return parsed as CredentialWriteRefusal;
    }
  } catch {
    // Not JSON, or not the refusal shape (e.g. a 404's plain {detail}) —
    // falls through to the generic failure below.
  }
  return null;
}

/**
 * Write one credential value (DP-034 D1). The route answers `204` with no
 * body on success; this function returns `void` — there is no read path, by
 * design, so there is nothing to hand back. The submitted value lives only
 * inside this call's own request body; it is never retained, returned, or
 * logged by this function.
 */
export async function writeCredential(sourceId: string, purpose: string, value: string): Promise<void> {
  const response = await fetch(`${apiBase()}/sources/${encodeURIComponent(sourceId)}/credentials`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ purpose, value }),
  });
  if (response.status === 204) {
    return;
  }
  const bodyText = await response.text();
  const refusal = parseCredentialRefusal(bodyText);
  if (refusal !== null) {
    throw new CredentialWriteFailure(refusal);
  }
  throw new ApiFailure(response.status, bodyText);
}

/**
 * A page of one source's Raw items, ordered by `seq` ascending (oldest
 * first — `apps/domain/api.py`'s `LIST_ITEMS` query, not a guess). DP-033
 * D2: `payload` is plain text, rendered as such and never as markup.
 */
export function readRawItems(sourceId: string, offset: number, limit: number): Promise<RawItemPage> {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return getJson<RawItemPage>(`/sources/${encodeURIComponent(sourceId)}/raw/items?${query.toString()}`);
}

export function readSchedule(sourceId: string): Promise<Schedule> {
  return getJson<Schedule>(`/sources/${encodeURIComponent(sourceId)}/schedule`);
}

/** `PUT /sources/{id}/schedule`: upserts. Restricted server-side to a `collector` source (`apps/domain/api.py`'s `write_schedule`). */
export async function writeSchedule(sourceId: string, body: ScheduleWrite): Promise<Schedule> {
  const response = await fetch(`${apiBase()}/sources/${encodeURIComponent(sourceId)}/schedule`, {
    method: "PUT",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiFailure(response.status, await response.text());
  }
  return (await response.json()) as Schedule;
}

export function listSnapshots(sourceId?: string): Promise<SnapshotList> {
  const query = sourceId === undefined ? "" : `?source_id=${encodeURIComponent(sourceId)}`;
  return getJson<SnapshotList>(`/snapshots${query}`);
}

export function readSnapshot(snapshotId: string): Promise<Snapshot> {
  return getJson<Snapshot>(`/snapshots/${encodeURIComponent(snapshotId)}`);
}

/**
 * Seal every Raw item of one source into a new snapshot (PoC Contract §8: a
 * deliberate act, distinct from normalizing). A `404`/`409` refusal (no such
 * source; wrong kind; disabled) is returned rather than thrown — the screen
 * has to display it in full.
 */
export async function sealSnapshot(sourceId: string): Promise<Snapshot | DomainRefused> {
  const response = await fetch(`${apiBase()}/sources/${encodeURIComponent(sourceId)}/snapshots`, {
    method: "POST",
    headers: { accept: "application/json" },
  });
  if (response.ok || response.status === 404 || response.status === 409) {
    return (await response.json()) as Snapshot | DomainRefused;
  }
  throw new ApiFailure(response.status, await response.text());
}

/**
 * Enqueue one normalize job over a sealed snapshot. `normalizerSourceId`
 * names a registered **source of kind `normalizer`** — not an
 * addon-id/version pair — because that is what `apps/domain/api.py`'s
 * `start_normalization` actually takes (`{source_id}` in the body, looked up
 * and required to be `kind == "normalizer"`). The job this creates stays
 * `PENDING` until M3 registers an `addon:*` worker; a `201` here means "the
 * job was created," not "it ran." A `404`/`409`/`422` refusal is returned
 * rather than thrown, for the same reason `sealSnapshot` returns one.
 */
export async function createNormalizeRun(
  snapshotId: string,
  normalizerSourceId: string,
): Promise<NormalizeRunCreated | DomainRefused> {
  const response = await fetch(`${apiBase()}/snapshots/${encodeURIComponent(snapshotId)}/normalize`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ source_id: normalizerSourceId }),
  });
  if (response.ok || [404, 409, 422].includes(response.status)) {
    return (await response.json()) as NormalizeRunCreated | DomainRefused;
  }
  throw new ApiFailure(response.status, await response.text());
}

/** Every normalized result over one snapshot, all versions unless `addonVersion` narrows it — coexistence is the point (PoC Contract §5). */
export function readResults(snapshotId: string, addonVersion?: string): Promise<ResultList> {
  const query = addonVersion === undefined ? "" : `?addon_version=${encodeURIComponent(addonVersion)}`;
  return getJson<ResultList>(`/snapshots/${encodeURIComponent(snapshotId)}/results${query}`);
}
