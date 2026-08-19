// The shapes the operator API returns, and the four calls this dashboard makes.
//
// **Every type here is derived, not invented.** Each field name below is copied
// from `platform_core/api/app.py` — `job_view`, `attempt_view` — whose fields come
// in turn from the columns in `db/migrations/0001_platform_core.sql`. Both of those
// files are parsed by the P0-A boundary guard in `tests/environment/`; this file is
// not (the guard reads `.py` and `.sql`, and checks TypeScript by path name only).
// Inheriting the names instead of coining new ones is what leaves no route for
// P0-B vocabulary to enter through a screen. See this directory's README.
//
// Nothing here validates. A response is cast to the shape the API is contracted to
// return, and a mismatch shows up as a blank cell rather than as a thrown error,
// which for an instrumentation screen is the right failure: an operator diagnosing
// a job should not be blocked by a field the dashboard did not expect.

/** `jobs.state`, whose CHECK constraint fixes these four values. */
export type JobState = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";

export const JOB_STATES: readonly JobState[] = ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"];

/** `job_attempt.outcome`, likewise fixed by its CHECK constraint. */
export type AttemptOutcome = "SUCCEEDED" | "RETRYABLE_FAILURE" | "PERMANENT_FAILURE" | "ABANDONED";

/** `job_view`: the `job` columns, plus the two fields it derives. */
export interface Job {
  id: string;
  handler: string;
  payload: unknown;
  state: JobState;
  attempt_count: number;
  max_attempts: number;
  available_at: string;
  lease_owner: string | null;
  lease_expires_at: string | null;
  terminal_reason: string | null;
  correlation_id: string;
  created_at: string;
  updated_at: string;
  attempts_remaining: number;
  attempt_budget_spent: boolean;
}

/** The `GET /jobs` envelope. `matched` is the count before the page was cut. */
export interface JobPage {
  state: JobState | null;
  limit: number;
  offset: number;
  returned: number;
  matched: number;
  jobs: Job[];
}

/**
 * `attempt_view`: the `job_attempt` columns minus `error_detail`, plus the two
 * booleans it derives. `error_detail` is present only when the protected-debug
 * representation was asked for, which is why it is optional here and nowhere else.
 */
export interface Attempt {
  id: string;
  job_id: string;
  attempt_no: number;
  worker_id: string;
  started_at: string;
  finished_at: string | null;
  outcome: AttemptOutcome | null;
  error_class: string | null;
  error_summary: string | null;
  correlation_id: string;
  error_detail_present: boolean;
  error_class_retryable: boolean | null;
  error_detail?: unknown;
}

export type Representation = "default" | "protected";

/** The `GET /jobs/{id}/attempts` envelope. */
export interface AttemptPage {
  job_id: string;
  correlation_id: string;
  representation: Representation;
  attempts: Attempt[];
}

/** A `POST /jobs/{id}/retry` that moved the job. */
export interface RetryAccepted {
  accepted: true;
  job_id: string;
  correlation_id: string;
  previous_state: JobState;
  current_state: JobState;
  job: Job;
}

/**
 * A `409` refusal. `current_state` and `required_state` are the whole point: the
 * API is explicit that "this job is SUCCEEDED; a safe retry starts from FAILED" is
 * actionable and "bad request" is not, so the screen shows these two fields rather
 * than a message of its own making.
 */
export interface RetryRefused {
  accepted: false;
  job_id: string;
  correlation_id: string;
  current_state: JobState;
  required_state: JobState;
  reason: string;
}

/**
 * A `404`: the identity is not there at all. FastAPI's own envelope, which carries
 * `detail` and no `accepted`, so `detail` is what tells the three apart.
 */
export interface RetryMissing {
  detail: string;
}

export type RetryOutcome = RetryAccepted | RetryRefused | RetryMissing;

export function isMissing(outcome: RetryOutcome): outcome is RetryMissing {
  return !("accepted" in outcome);
}

/**
 * Where the API is. Empty by default, which makes every path below same-origin and
 * leaves the dev proxy in `vite.config.ts` to reach the loopback API. `VITE_API_BASE`
 * exists for a build served from somewhere other than Vite; a remote address is
 * refused, for the reason the proxy target is refused one.
 *
 * A function rather than a module-level constant, so that importing this module
 * runs nothing. `src/detail-text.tsx` renders the same screen components under Node
 * with no environment at all, and a throw at import time would make that fail for
 * a reason unrelated to what it is checking.
 */
export function apiBase(): string {
  const configured: unknown = import.meta.env.VITE_API_BASE;
  if (typeof configured !== "string" || configured === "") {
    return "";
  }
  const host = new URL(configured).hostname;
  if (!["127.0.0.1", "localhost", "::1"].includes(host)) {
    throw new Error(`VITE_API_BASE must name a loopback host, not ${host}`);
  }
  return configured.replace(/\/$/, "");
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

async function getJson<T>(path: string): Promise<T> {
  const answer = await fetch(`${apiBase()}${path}`, { headers: { accept: "application/json" } });
  if (!answer.ok) {
    throw new ApiFailure(answer.status, await answer.text());
  }
  return (await answer.json()) as T;
}

export function listJobs(state: JobState | null, limit: number): Promise<JobPage> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (state !== null) {
    query.set("state", state);
  }
  return getJson<JobPage>(`/jobs?${query.toString()}`);
}

export function readJob(jobId: string): Promise<Job> {
  return getJson<Job>(`/jobs/${encodeURIComponent(jobId)}`);
}

/**
 * The attempts of one job. `protected` adds `?debug=protected`, which is the
 * explicit action SEC-004 requires: protected detail is reachable, and only by
 * asking for it by name.
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
  const answer = await fetch(`${apiBase()}/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    headers: { accept: "application/json" },
  });
  if (answer.ok || answer.status === 409 || answer.status === 404) {
    return (await answer.json()) as RetryOutcome;
  }
  throw new ApiFailure(answer.status, await answer.text());
}

// --------------------------------------------------------------------------- //
// The domain surface (`addon_host/api.py`)
//
// Four more kinds of thing, and the same naming rule as everything above: every
// field is copied from `source_view`, `snapshot_view`, and `result_view`, whose
// fields come from the columns in `domain/migrations/0002_domain.sql` and
// `0003_normalized_result.sql`. Nothing here is coined.
//
// `addon_host/api.py`'s own docstring records why these are not jobs: a source
// exists before any job and outlives every one, a snapshot is verifiable long after
// the job that sealed it finished, and two normalizer versions over one snapshot are
// two sets of results. An operator restricted to jobs can see that a collection ran
// and not what it collected.
// --------------------------------------------------------------------------- //

/** `source.kind`, fixed by its CHECK constraint. */
export type SourceKind = "collector" | "importer" | "normalizer";

/** One approved endpoint: where it goes, and by which method (DP-020 D1). */
export interface Endpoint {
  path: string;
  method: string;
}

/**
 * One credential part: which header it fills, and the secret-store **key name** that
 * fills it (DP-018 D1). Never a value — the column's CHECK and the profile reader
 * both refuse anything that is not a key name, and an operator needs to see the name
 * to know which key to put in the store.
 */
export interface CredentialPart {
  header: string;
  ref: string;
}

/** `profile_view`: the operator's own grant, read back to them. */
export interface OutboundProfile {
  hosts: string[];
  endpoints: Record<string, Endpoint>;
  port: number;
  limits: Record<string, number>;
  allow_loopback: boolean;
  credentials: CredentialPart[];
}

/** `source_view`. */
export interface Source {
  source_id: string;
  addon_id: string;
  addon_version: string;
  kind: SourceKind;
  config: Record<string, unknown>;
  config_schema_version: string;
  credential_ref: string | null;
  outbound_profile: OutboundProfile | null;
  data_class: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** What one source has collected. Counts, never payloads. */
export interface RawSummary {
  source_id: string;
  envelope_count: number;
  item_count: number;
  last_retrieved_at: string | null;
}

/**
 * `snapshot_view`. `verifies` is computed on every read rather than stored: a screen
 * that showed only "sealed" would make a tampered input look ready to run, and
 * `problems` says which member failed because that is what an operator acts on.
 */
export interface Snapshot {
  snapshot_id: string;
  source_id: string;
  item_count: number;
  manifest_sha256: string;
  selection: Record<string, unknown>;
  sealed_at: string | null;
  created_at: string;
  verifies: boolean;
  problems: string[];
}

/** `result_view`: one normalized record, both version axes, and the lineage key. */
export interface NormalizedResult {
  id: string;
  snapshot_id: string;
  source_id: string;
  addon_id: string;
  addon_version: string;
  output_contract_version: string;
  source_item_key: string;
  body: Record<string, unknown>;
  body_sha256: string;
  notes: Record<string, unknown>;
  created_at: string;
}

export interface SourceList {
  sources: Source[];
}

export interface SnapshotList {
  snapshots: Snapshot[];
}

export interface ResultList {
  results: NormalizedResult[];
}

/** A `201` from either of the two job-creating writes. */
export interface JobCreated {
  job_id: string;
  source_id?: string;
  snapshot_id?: string;
}

/** A `409` or `404`: FastAPI's own envelope, whose `detail` is written to be read. */
export interface DomainRefused {
  detail: string;
}

export type DomainOutcome = JobCreated | DomainRefused;

export function wasRefused(outcome: DomainOutcome): outcome is DomainRefused {
  return "detail" in outcome;
}

export function listSources(): Promise<SourceList> {
  return getJson<SourceList>("/sources");
}

export function readRaw(sourceId: string): Promise<RawSummary> {
  return getJson<RawSummary>(`/sources/${encodeURIComponent(sourceId)}/raw`);
}

export function listSnapshots(sourceId?: string): Promise<SnapshotList> {
  const query = sourceId === undefined ? "" : `?source_id=${encodeURIComponent(sourceId)}`;
  return getJson<SnapshotList>(`/snapshots${query}`);
}

export function readResults(snapshotId: string): Promise<ResultList> {
  return getJson<ResultList>(`/snapshots/${encodeURIComponent(snapshotId)}/results`);
}

/**
 * The three writes, and what they have in common: each sends an **identifier** and
 * nothing else. There is no parameter on any of them that could become a host, a
 * path, or a URL, which is `p0-security.md`'s outbound rule expressed as a signature
 * rather than as a validation step.
 *
 * A `409` and a `404` are returned rather than thrown, for the reason `requestRetry`
 * gives: both are answers the screen has to display in full.
 */
async function post(path: string, body?: unknown): Promise<DomainOutcome> {
  // Built in two branches rather than with an `undefined` body, because
  // `exactOptionalPropertyTypes` is on and "absent" and "present and undefined" are
  // different things to it — which is the same distinction this codebase keeps
  // everywhere else between a field that was not given and one given as null.
  const request: RequestInit =
    body === undefined
      ? { method: "POST", headers: { accept: "application/json" } }
      : {
          method: "POST",
          headers: { accept: "application/json", "content-type": "application/json" },
          body: JSON.stringify(body),
        };
  const answer = await fetch(`${apiBase()}${path}`, request);
  if (answer.ok || answer.status === 409 || answer.status === 404 || answer.status === 422) {
    return (await answer.json()) as DomainOutcome;
  }
  throw new ApiFailure(answer.status, await answer.text());
}

export function startCollection(sourceId: string): Promise<DomainOutcome> {
  return post(`/sources/${encodeURIComponent(sourceId)}/collect`);
}

export function sealSnapshot(sourceId: string): Promise<DomainOutcome> {
  return post(`/sources/${encodeURIComponent(sourceId)}/snapshots`);
}

export function startNormalization(
  snapshotId: string,
  normalizerSourceId: string,
): Promise<DomainOutcome> {
  return post(`/snapshots/${encodeURIComponent(snapshotId)}/normalize`, {
    source_id: normalizerSourceId,
  });
}
