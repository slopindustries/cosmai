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
