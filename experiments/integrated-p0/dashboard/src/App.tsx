// The two containers, and the only state this dashboard keeps.
//
// **No router and no fetch cache.** DP-006 D6 declines React Router and TanStack
// Query because two screens do not have the problems they solve. Which job is open
// is one `useState`; the browser's back button is not part of any OPS scenario.
//
// **Every read is explicit and re-runnable.** There is no polling. A `useEffect`
// per screen loads when its inputs change, and a "reload" button re-runs it, so
// what is on screen is always the answer to a request an operator can point at.
// A screen that refreshed itself would make "the API said this at that moment"
// unrecoverable, which is the one thing an operator diagnosing a failure needs.

import { useCallback, useEffect, useState } from "react";
import type { JSX } from "react";
import type { AttemptPage, Job, JobPage, JobState, RetryOutcome } from "./api";
import { listJobs, readAttempts, readJob, requestRetry } from "./api";
import { JobDetailView, JobTable, StateFilter } from "./view";

const PAGE_LIMIT = 50;

function messageOf(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure);
}

export function App(): JSX.Element {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return (
    <div className="app">
      <header className="app-header">
        <h1>CosmaSignal P0-A operator surface</h1>
        <p className="note">
          Disposable P0-A instrumentation over the operator API. Two screens: the
          job list, and one job in detail with its attempts and a retry.
        </p>
      </header>
      <JobListScreen selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId === null ? (
        <p className="empty">Choose a job above to see why it ended the way it did.</p>
      ) : (
        <JobDetailScreen jobId={selectedId} />
      )}
    </div>
  );
}

function JobListScreen({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (jobId: string) => void;
}): JSX.Element {
  const [state, setState] = useState<JobState | null>(null);
  const [page, setPage] = useState<JobPage | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let current = true;
    setFailure(null);
    listJobs(state, PAGE_LIMIT)
      .then((loaded) => {
        if (current) {
          setPage(loaded);
        }
      })
      .catch((problem: unknown) => {
        if (current) {
          setFailure(messageOf(problem));
        }
      });
    return () => {
      current = false;
    };
  }, [state, reloads]);

  return (
    <section className="screen">
      <div className="screen-header">
        <h2>jobs</h2>
        <StateFilter state={state} onChange={setState} />
        <button className="action" type="button" onClick={() => setReloads(reloads + 1)}>
          Reload
        </button>
        {page === null ? null : (
          <span className="note">
            showing {page.returned} of {page.matched} matched
          </span>
        )}
      </div>
      {failure === null ? null : <p className="failure">{failure}</p>}
      {page === null ? (
        <p className="empty">Loading.</p>
      ) : (
        <JobTable page={page} selectedId={selectedId} onSelect={onSelect} />
      )}
    </section>
  );
}

function JobDetailScreen({ jobId }: { jobId: string }): JSX.Element {
  const [job, setJob] = useState<Job | null>(null);
  const [attempts, setAttempts] = useState<AttemptPage | null>(null);
  const [wantProtected, setWantProtected] = useState(false);
  const [retry, setRetry] = useState<RetryOutcome | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let current = true;
    setFailure(null);
    Promise.all([readJob(jobId), readAttempts(jobId, wantProtected)])
      .then(([loadedJob, loadedAttempts]) => {
        if (current) {
          setJob(loadedJob);
          setAttempts(loadedAttempts);
        }
      })
      .catch((problem: unknown) => {
        if (current) {
          setFailure(messageOf(problem));
        }
      });
    return () => {
      current = false;
    };
  }, [jobId, wantProtected, reloads]);

  // Selecting a different job clears the previous job's retry answer and drops
  // back to the default representation. Carrying either across would put one job's
  // outcome under another job's heading.
  useEffect(() => {
    setRetry(null);
    setWantProtected(false);
  }, [jobId]);

  const onRetry = useCallback(() => {
    setBusy(true);
    requestRetry(jobId)
      .then((outcome) => {
        setRetry(outcome);
        setReloads((previous) => previous + 1);
      })
      .catch((problem: unknown) => {
        setFailure(messageOf(problem));
      })
      .finally(() => {
        setBusy(false);
      });
  }, [jobId]);

  const onAskProtected = useCallback(() => {
    setWantProtected(true);
  }, []);

  if (failure !== null) {
    return (
      <section className="screen">
        <h2>job {jobId}</h2>
        <p className="failure">{failure}</p>
      </section>
    );
  }
  if (job === null || attempts === null) {
    return (
      <section className="screen">
        <p className="empty">Loading.</p>
      </section>
    );
  }
  return (
    <section className="screen">
      <JobDetailView
        job={job}
        attempts={attempts}
        retry={retry}
        onAskProtected={onAskProtected}
        onRetry={onRetry}
        busy={busy}
      />
    </section>
  );
}
