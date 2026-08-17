// Every visible part of the two screens, as pure functions of API data.
//
// Nothing here fetches, holds state, or reads a clock. That is not tidiness: it is
// what lets `src/detail-text.tsx` render the job-detail screen from a frozen set of
// API responses and hand the visible text to a pytest assertion. SEC-004's Action
// step 3 asks for "the dashboard job-detail screen" to be read and searched, and a
// screen that could only be reached by driving a browser would have to be searched
// by a human with a screenshot. Keeping the rendering pure makes the same screen
// checkable by a test on every run.
//
// Naming rule for this file, and for the whole directory: **field names are copied
// from the API, never coined.** See the README.

import type { JSX, ReactNode } from "react";
import { isMissing, JOB_STATES } from "./api";
import type { Attempt, AttemptPage, Job, JobState, RetryOutcome } from "./api";

/** How a value that is null, absent, or empty reads on screen. */
const ABSENT = "—";

// The masking marker itself is deliberately **not** a constant here, and no text on
// either screen spells it out. `obs/redaction.py` owns it, this dashboard only
// displays whatever arrived, and a copy of the literal in the prose would make
// SEC-004's "the marker is present where a value was removed" assertion true of the
// explanatory sentence rather than of the data.

/** How much of an identifier a list row shows. Full identifiers are on the detail. */
const SHORT_ID_LENGTH = 8;

export function shortId(identifier: string): string {
  return identifier.slice(0, SHORT_ID_LENGTH);
}

export function shown(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? ABSENT : value;
}

export function yesNo(value: boolean | null): string {
  if (value === null) {
    return "unknown";
  }
  return value ? "yes" : "no";
}

// --------------------------------------------------------------------------- //
// Presentational pieces. These names are free to be invented because they carry
// no data shape: they describe a box, not a thing the platform stores.
// --------------------------------------------------------------------------- //

export function Badge({ kind, children }: { kind: string; children: string }): JSX.Element {
  return <span className={`badge badge-${kind.toLowerCase()}`}>{children}</span>;
}

function Field({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <span className="field-value">{children}</span>
    </div>
  );
}

function Mono({ children }: { children: string }): JSX.Element {
  return <code className="mono">{children}</code>;
}

// --------------------------------------------------------------------------- //
// Screen 1 — the job list
// --------------------------------------------------------------------------- //

export interface JobTableProps {
  page: { returned: number; matched: number; jobs: Job[] };
  selectedId: string | null;
  onSelect: (jobId: string) => void;
}

/**
 * A page of jobs as one table. `JobTable`, not a name built on the word the P0-A
 * boundary reserves; the things in it are rows.
 *
 * A `FAILED` job has to be findable without reading every line, so its state cell
 * is badged and its whole row is marked. OPS-001 starts by finding a failure among
 * jobs that mostly succeeded.
 */
export function JobTable({ page, selectedId, onSelect }: JobTableProps): JSX.Element {
  if (page.jobs.length === 0) {
    return <p className="empty">No job matched this filter.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th>job</th>
          <th>handler</th>
          <th>state</th>
          <th>attempts</th>
          <th>created</th>
        </tr>
      </thead>
      <tbody>
        {page.jobs.map((job) => (
          <tr
            key={job.id}
            className={[
              job.state === "FAILED" ? "row-failed" : "",
              job.id === selectedId ? "row-selected" : "",
            ]
              .join(" ")
              .trim()}
          >
            <td>
              <button className="link" type="button" onClick={() => onSelect(job.id)}>
                <code className="mono">{shortId(job.id)}</code>
              </button>
            </td>
            <td>{job.handler}</td>
            <td>
              <Badge kind={job.state}>{job.state}</Badge>
            </td>
            <td className="numeric">
              {job.attempt_count} / {job.max_attempts}
            </td>
            <td className="timestamp">{job.created_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export interface StateFilterProps {
  state: JobState | null;
  onChange: (state: JobState | null) => void;
}

export function StateFilter({ state, onChange }: StateFilterProps): JSX.Element {
  return (
    <div className="filter">
      <span className="field-label">state</span>
      {[null, ...JOB_STATES].map((candidate) => (
        <button
          key={candidate ?? "any"}
          type="button"
          className={candidate === state ? "chip chip-on" : "chip"}
          onClick={() => onChange(candidate)}
        >
          {candidate ?? "any"}
        </button>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Screen 2 — the job detail
// --------------------------------------------------------------------------- //

/**
 * The job's opaque input, as the API returned it.
 *
 * The API redacts on the way out, so what arrives here already has a marker where
 * a value under a reserved key used to be. The note above the block says so,
 * because an operator who saw `[REDACTED]` with no explanation would reasonably
 * wonder whether the platform stored the value at all.
 */
export function PayloadPanel({ payload }: { payload: unknown }): JSX.Element {
  return (
    <section className="panel">
      <h3>payload</h3>
      <p className="note">
        The opaque input as submitted, exactly as the API returned it. A value under
        a reserved key arrives already masked and the key name survives, because
        knowing a value was there is diagnostic and the value itself is not.
      </p>
      <pre className="block">{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}

export interface AttemptTableProps {
  page: AttemptPage;
  onAskProtected: () => void;
  busy: boolean;
}

/**
 * Every attempt of one job, and the explicit way to ask for what is withheld.
 *
 * `error_detail_present` is a boolean in the default representation, so this table
 * can say "there is detail you are not being shown" rather than leaving an operator
 * unable to tell that from "there is no detail". The button beside it is the
 * explicit action: it re-reads the same attempts with `?debug=protected`.
 */
export function AttemptTable({ page, onAskProtected, busy }: AttemptTableProps): JSX.Element {
  const isProtected = page.representation === "protected";
  const withheld = page.attempts.some((attempt) => attempt.error_detail_present);
  return (
    <section className="panel">
      <h3>attempts</h3>
      <div className="representation">
        <Field label="representation">
          <Badge kind={page.representation}>{page.representation}</Badge>
        </Field>
        {withheld && !isProtected ? (
          <>
            <span className="note">
              At least one attempt has protected debug detail that this
              representation withholds.
            </span>
            <button className="action" type="button" disabled={busy} onClick={onAskProtected}>
              Show protected detail (?debug=protected)
            </button>
          </>
        ) : null}
        {isProtected ? (
          <span className="note">
            Protected means who may ask, not what is masked: values under reserved
            keys are still masked here.
          </span>
        ) : null}
      </div>
      {page.attempts.length === 0 ? (
        <p className="empty">This job has no attempt yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>no</th>
              <th>worker</th>
              <th>outcome</th>
              <th>error class</th>
              <th>class retryable</th>
              <th>started</th>
              <th>finished</th>
              <th>summary</th>
              <th>protected detail</th>
            </tr>
          </thead>
          <tbody>
            {page.attempts.map((attempt) => (
              <AttemptRow key={attempt.id} attempt={attempt} isProtected={isProtected} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function AttemptRow({
  attempt,
  isProtected,
}: {
  attempt: Attempt;
  isProtected: boolean;
}): JSX.Element {
  return (
    <tr className={attempt.outcome === "SUCCEEDED" ? "" : "row-failed"}>
      <td className="numeric">{attempt.attempt_no}</td>
      <td className="mono">{attempt.worker_id}</td>
      <td>{attempt.outcome === null ? "open" : <Badge kind={attempt.outcome}>{attempt.outcome}</Badge>}</td>
      <td>{shown(attempt.error_class)}</td>
      <td>{yesNo(attempt.error_class_retryable)}</td>
      <td className="timestamp">{attempt.started_at}</td>
      <td className="timestamp">{shown(attempt.finished_at)}</td>
      <td className="summary">{shown(attempt.error_summary)}</td>
      <td>
        <ProtectedCell attempt={attempt} isProtected={isProtected} />
      </td>
    </tr>
  );
}

/**
 * Question 6 of OPS-001, in one cell.
 *
 * Three states, and the middle one is the one that matters: no detail exists, or
 * detail exists and is being withheld, or detail exists and was asked for. The
 * detail itself is rendered only in the third case, which is what makes "absent
 * from the default screen" a property of this component rather than a convention.
 */
function ProtectedCell({
  attempt,
  isProtected,
}: {
  attempt: Attempt;
  isProtected: boolean;
}): JSX.Element {
  if (!attempt.error_detail_present) {
    return <span className="note">none</span>;
  }
  if (!isProtected) {
    return <span className="withheld">present, withheld</span>;
  }
  return <pre className="block">{JSON.stringify(attempt.error_detail, null, 2)}</pre>;
}

export interface RetryPanelProps {
  job: Job;
  outcome: RetryOutcome | null;
  onRetry: () => void;
  busy: boolean;
}

/**
 * The one write the operator API offers, and its refusal in full.
 *
 * A refusal is not reported as "that failed". The API answers a `409` carrying the
 * state the job was in and the state a retry needs, because OPS-002 is explicit
 * that "this job is SUCCEEDED; a safe retry starts from FAILED" is actionable and
 * "bad request" is not. Both fields and the API's own sentence are shown as given.
 */
export function RetryPanel({ job, outcome, onRetry, busy }: RetryPanelProps): JSX.Element {
  return (
    <section className="panel">
      <h3>retry</h3>
      <p className="note">
        A safe retry starts from FAILED only. This job is {job.state}.
      </p>
      <button className="action" type="button" disabled={busy} onClick={onRetry}>
        Request retry
      </button>
      {outcome === null ? null : <RetryOutcomeNote outcome={outcome} />}
    </section>
  );
}

function RetryOutcomeNote({ outcome }: { outcome: RetryOutcome }): JSX.Element {
  if (isMissing(outcome)) {
    return (
      <div className="outcome outcome-refused">
        <strong>Not found.</strong> <span>{outcome.detail}</span>
      </div>
    );
  }
  if (outcome.accepted) {
    return (
      <div className="outcome outcome-accepted">
        <strong>Retry accepted.</strong>
        <Field label="previous state">
          <Badge kind={outcome.previous_state}>{outcome.previous_state}</Badge>
        </Field>
        <Field label="current state">
          <Badge kind={outcome.current_state}>{outcome.current_state}</Badge>
        </Field>
      </div>
    );
  }
  return (
    <div className="outcome outcome-refused">
      <strong>Retry refused.</strong>
      <Field label="current state">
        <Badge kind={outcome.current_state}>{outcome.current_state}</Badge>
      </Field>
      <Field label="required state">
        <Badge kind={outcome.required_state}>{outcome.required_state}</Badge>
      </Field>
      <p className="reason">{outcome.reason}</p>
    </div>
  );
}

export interface JobDetailProps {
  job: Job;
  attempts: AttemptPage;
  retry: RetryOutcome | null;
  onAskProtected: () => void;
  onRetry: () => void;
  busy: boolean;
}

/**
 * The screen SEC-004 step 3 names and OPS-001's six questions are answered from.
 *
 * 1. What ran — `handler`, and the full `id`.
 * 2. With which input — `PayloadPanel`.
 * 3. When — the job's `created_at` and `updated_at`, and each attempt's
 *    `started_at` and `finished_at`.
 * 4. Why did it fail — `terminal_reason` on the job, `error_class` and
 *    `error_summary` on each attempt.
 * 5. Is anything left to try — `attempt_count` against `max_attempts`,
 *    `attempts_remaining`, and `attempt_budget_spent`; and, separately from all
 *    three, `error_class_retryable` per attempt, because a retryable class on a job
 *    with no budget left is the case where one number answers the wrong question.
 * 6. Is detail being withheld — `error_detail_present`, and the button.
 */
export function JobDetailView({
  job,
  attempts,
  retry,
  onAskProtected,
  onRetry,
  busy,
}: JobDetailProps): JSX.Element {
  return (
    <div className="detail">
      <header className="detail-header">
        <h2>
          job <Mono>{job.id}</Mono>
        </h2>
        <Badge kind={job.state}>{job.state}</Badge>
      </header>

      <section className="panel">
        <h3>what ran, when, and how it ended</h3>
        <div className="fields">
          <Field label="handler">{job.handler}</Field>
          <Field label="state">{job.state}</Field>
          <Field label="terminal reason">{shown(job.terminal_reason)}</Field>
          <Field label="correlation id">
            <Mono>{job.correlation_id}</Mono>
          </Field>
          <Field label="created at">{job.created_at}</Field>
          <Field label="last changed at">{job.updated_at}</Field>
          <Field label="available at">{job.available_at}</Field>
          <Field label="lease owner">{shown(job.lease_owner)}</Field>
          <Field label="lease expires at">{shown(job.lease_expires_at)}</Field>
          <Field label="attempts spent">
            {job.attempt_count} of {job.max_attempts}
          </Field>
          <Field label="attempts remaining">{job.attempts_remaining}</Field>
          <Field label="attempt budget spent">{yesNo(job.attempt_budget_spent)}</Field>
        </div>
      </section>

      <PayloadPanel payload={job.payload} />
      <RetryPanel job={job} outcome={retry} onRetry={onRetry} busy={busy} />
      <AttemptTable page={attempts} onAskProtected={onAskProtected} busy={busy} />
    </div>
  );
}
