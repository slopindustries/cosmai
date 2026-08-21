// The shapes the M1 operator API returns.
//
// Every field name here is copied from `apps/platform_core/api/app.py` —
// `job_view`, `attempt_view`, `health`, `read_metrics` — never coined. That file's
// docstrings are the source of truth for what each field means; this module only
// gives it a TypeScript shape. See `apps/platform_core/obs/metrics.py` for the
// `MetricsReading`/`DurationReading` fields and `apps/platform_core/errors.py`'s
// `PlatformError.operator_view()` for the unhealthy-health fields.

/** `jobs.state`, whose CHECK constraint fixes these four values. */
export type JobState = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";

export const JOB_STATES: readonly JobState[] = ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"];

/** `job_attempt.outcome`, likewise fixed by its CHECK constraint. */
export type AttemptOutcome =
  | "SUCCEEDED"
  | "RETRYABLE_FAILURE"
  | "PERMANENT_FAILURE"
  | "ABANDONED";

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

export type Representation = "default" | "protected";

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

export function isRetryMissing(outcome: RetryOutcome): outcome is RetryMissing {
  return !("accepted" in outcome);
}

/** `GET /health`, the reachable case. */
export interface HealthOk {
  status: "ok";
  database: "reachable";
  database_name: string;
  log_level: string;
  jobs_by_state: Record<JobState, number>;
}

/** `GET /health`, the `503` case: `PlatformError.operator_view()` folded in. */
export interface HealthUnhealthy {
  status: "unhealthy";
  database: "unreachable";
  database_name: string;
  error_class: string;
  error_summary: string;
}

export type HealthResponse = HealthOk | HealthUnhealthy;

export function isHealthy(health: HealthResponse): health is HealthOk {
  return health.status === "ok";
}

/** `DurationReading.as_dict()`. */
export interface DurationReading {
  count: number;
  total_ms: number;
  min_ms: number;
  max_ms: number;
  mean_ms: number;
}

/** `MetricsReading.as_dict()`. */
export interface MetricsReading {
  transitions: Record<JobState, number>;
  claim_conflicts: number;
  suppressed_duplicate_effects: number;
  abandoned_attempts: number;
  rejected_completions: number;
  attempt_duration_ms: DurationReading;
  lease_recovery_latency_ms: DurationReading;
}

/** `GET /metrics`. `scope`/`pid` say whose counters these are — one process only. */
export interface MetricsResponse {
  scope: string;
  pid: number;
  metrics: MetricsReading;
}

// --------------------------------------------------------------------------- //
// The domain surface (`apps/domain/api.py`, M2 — real as of batch 5-final,
// merged from `dev`). Every field name below is copied from that file's own
// view functions (`source_view`, `snapshot_view`, `result_view`,
// `schedule_view`, `raw_item_view`) — never coined. `apps/domain/store.py`'s
// `SourceRow`/dataclasses back them where a view function itself is thin.
// --------------------------------------------------------------------------- //

/** `source.kind`'s CHECK constraint. */
export type SourceKind = "collector" | "importer" | "normalizer";

/** One approved outbound endpoint: where it goes, and by which method. */
export interface Endpoint {
  path: string;
  method: string;
}

/** One credential part: which header it fills, and the secret-store key name that fills it (DP-018 D1). Never a value. */
export interface CredentialPart {
  header: string;
  ref: string;
}

/** `profile_view`: the operator's own outbound grant, read back. */
export interface OutboundProfile {
  hosts: string[];
  endpoints: Record<string, Endpoint>;
  port: number;
  limits: Record<string, number>;
  allow_loopback: boolean;
  credentials: CredentialPart[];
}

/** `input_profile_view`: the operator's approved input grant for an importer (DP-024). */
export interface InputProfile {
  root: string;
  inputs: Record<string, string>;
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
  input_profile: InputProfile | null;
  data_class: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** The `GET /sources` envelope. */
export interface SourceList {
  sources: Source[];
}

/** `GET /sources/{id}/raw`: how much a source has collected. Counts, never payloads. */
export interface RawSummary {
  source_id: string;
  envelope_count: number;
  item_count: number;
  last_retrieved_at: string | null;
}

/**
 * `POST /sources/{id}/credentials` request body (DP-034 D1). Write-only: there
 * is no corresponding read type, because the value is never read back.
 */
export interface CredentialWriteRequest {
  purpose: string;
  value: string;
}

/**
 * The credentials write route's `422` refusal shape:
 * `ConfigurationInvalidError.operator_view()`, the same
 * `error_class`/`error_summary` convention `HealthUnhealthy` already carries.
 * A `404` (unregistered `source_id`) instead answers FastAPI's own
 * `{detail}` envelope — see `DomainRefused` below.
 */
export interface CredentialWriteRefusal {
  error_class: string;
  error_summary: string;
}

/** One item on the `GET /sources/{id}/raw/items` page. `payload` is plain text (DP-033 D2). */
export interface RawItem {
  item_key: string;
  seq: number;
  emitted_at: string;
  content_type: string;
  payload: string;
}

/**
 * The `GET /sources/{id}/raw/items?offset&limit` envelope. **No `matched`
 * field** — `apps/domain/api.py`'s `read_raw_items` returns `returned` only;
 * a caller cannot tell "this is the last page" from the count alone and must
 * use `returned < limit` instead. (`platform_core.api.app`'s `GET /jobs`
 * does return `matched`; this route does not — the two page envelopes are
 * not the same shape, confirmed by reading `apps/domain/api.py` directly.)
 */
export interface RawItemPage {
  source_id: string;
  offset: number;
  limit: number;
  returned: number;
  items: RawItem[];
}

/** `schedule_view` (DP-033 D5). An unset schedule reads `enabled: false` with every timestamp `null` — not a 404. */
export interface Schedule {
  source_id: string;
  interval_seconds: number | null;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
}

/** `PUT /sources/{id}/schedule` request body. */
export interface ScheduleWrite {
  interval_seconds: number;
  enabled: boolean;
}

/**
 * `snapshot_view`. `verifies` is computed on every read rather than stored: a
 * screen that showed only "sealed" would make a tampered input look ready to
 * run, and `problems` says which member failed because that is what an
 * operator acts on (PoC Contract §8: verification state is its own column).
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

export interface SnapshotList {
  snapshots: Snapshot[];
}

/** A `201` from `POST /snapshots/{id}/normalize`: the job it created and nothing else — the job stays `PENDING` until M3 registers an `addon:*` worker. */
export interface NormalizeRunCreated {
  job_id: string;
  snapshot_id: string;
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

export interface ResultList {
  results: NormalizedResult[];
}

/** DP-030 D2's per-record fault-tolerance marker, when present in a result's `notes`. */
export interface NormalizeError {
  field: string;
  reason: string;
}

/** `result.notes.normalize_error`, or `null` if this record normalized cleanly. */
export function normalizeErrorOf(notes: Record<string, unknown>): NormalizeError | null {
  const candidate = notes["normalize_error"];
  if (
    typeof candidate === "object" &&
    candidate !== null &&
    typeof (candidate as Record<string, unknown>).field === "string" &&
    typeof (candidate as Record<string, unknown>).reason === "string"
  ) {
    return candidate as NormalizeError;
  }
  return null;
}

/**
 * A `404`/`409`/`422` domain refusal: FastAPI's own `HTTPException` envelope
 * (`{detail}`), used by every domain write below except the credentials
 * write's own `422` shape (`CredentialWriteRefusal`).
 */
export interface DomainRefused {
  detail: string;
}

export function isDomainRefused(value: object): value is DomainRefused {
  return "detail" in value;
}
