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
import type {
  AttemptPage,
  DomainOutcome,
  Job,
  JobPage,
  JobState,
  NormalizedResult,
  RawSummary,
  RetryOutcome,
  Snapshot,
  Source,
} from "./api";
import {
  listJobs,
  listSnapshots,
  listSources,
  readAttempts,
  readJob,
  readRaw,
  readResults,
  requestRetry,
  sealSnapshot,
  startCollection,
  startImport,
  startNormalization,
  wasRefused,
} from "./api";
import { ResultTable, SnapshotTable, SourceDetail, SourceTable } from "./domain-view";
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
        <h1>Cosmai P0-A operator surface</h1>
        <p className="note">
          Disposable P0 instrumentation over the operator API. The domain screen drives
          the operator loop — collect, seal, normalize, read — and the job screens below
          are where any of it is diagnosed when it fails.
        </p>
      </header>
      <DomainScreen />
      <JobListScreen selectedId={selectedId} onSelect={setSelectedId} />
      {selectedId === null ? (
        <p className="empty">Choose a job above to see why it ended the way it did.</p>
      ) : (
        <JobDetailScreen jobId={selectedId} />
      )}
    </div>
  );
}

/**
 * The P0-B operator loop, on one screen: sources and what they have collected, sealed
 * snapshots and whether they still verify, and the normalized results of whichever
 * snapshot is open.
 *
 * **Nothing here polls, and every write is followed by an explicit reload.** The same
 * rule the job screens follow: what is on screen is always the answer to a request an
 * operator can point at. A write returns a `job_id` and *not* a result, because
 * collecting and normalizing are jobs a worker runs — the screen says which job was
 * created and leaves the operator to watch it in the job list below.
 *
 * **Two buttons, not one.** `project-state.md` §4 and DP-019 D6 require sealing and
 * normalizing to be separate deliberate acts, and collection never to start either.
 * One convenient button that did all three would be that rule quietly broken.
 */
function DomainScreen(): JSX.Element {
  const [sources, setSources] = useState<Source[]>([]);
  const [raw, setRaw] = useState<Record<string, RawSummary>>({});
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [results, setResults] = useState<NormalizedResult[]>([]);
  const [openSource, setOpenSource] = useState<string | null>(null);
  const [openSnapshot, setOpenSnapshot] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let current = true;
    setFailure(null);
    Promise.all([listSources(), listSnapshots()])
      .then(async ([sourceList, snapshotList]) => {
        const summaries = await Promise.all(
          sourceList.sources
            .filter((source) => source.kind === "collector")
            .map((source) => readRaw(source.source_id)),
        );
        if (!current) {
          return;
        }
        setSources(sourceList.sources);
        setSnapshots(snapshotList.snapshots);
        setRaw(Object.fromEntries(summaries.map((summary) => [summary.source_id, summary])));
      })
      .catch((problem: unknown) => {
        if (current) {
          setFailure(messageOf(problem));
        }
      });
    return () => {
      current = false;
    };
  }, [reloads]);

  useEffect(() => {
    let current = true;
    if (openSnapshot === null) {
      setResults([]);
      return;
    }
    readResults(openSnapshot)
      .then((page) => {
        if (current) {
          setResults(page.results);
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
  }, [openSnapshot, reloads]);

  const act = useCallback(
    (started: Promise<DomainOutcome>, what: string) => {
      setNotice(null);
      started
        .then((outcome) => {
          // A refusal is displayed in full rather than summarised. The API writes its
          // `detail` to be read — "source X is a normalizer and this action needs a
          // collector" is actionable and "failed" is not.
          setNotice(
            wasRefused(outcome)
              ? `${what} refused: ${outcome.detail}`
              : `${what} started as job ${outcome.job_id}`,
          );
          reload();
        })
        .catch((problem: unknown) => setFailure(messageOf(problem)));
    },
    [reload],
  );

  const open = sources.find((source) => source.source_id === openSource) ?? null;
  const normalizers = sources.filter((source) => source.kind === "normalizer");

  return (
    <section className="screen">
      <div className="screen-header">
        <h2>sources</h2>
        <button type="button" onClick={reload}>
          reload
        </button>
      </div>
      {failure === null ? null : <p className="failure">{failure}</p>}
      {notice === null ? null : <p className="notice">{notice}</p>}
      <SourceTable
        sources={sources}
        raw={raw}
        selectedId={openSource}
        onSelect={(sourceId) => setOpenSource(sourceId === openSource ? null : sourceId)}
        onCollect={(sourceId) => act(startCollection(sourceId), `collection of ${sourceId}`)}
        onImport={(sourceId) => act(startImport(sourceId), `import of ${sourceId}`)}
        onSeal={(sourceId) => act(sealSnapshot(sourceId), `snapshot of ${sourceId}`)}
      />
      {open === null ? null : <SourceDetail source={open} />}

      <div className="screen-header">
        <h2>snapshots</h2>
      </div>
      <SnapshotTable
        snapshots={snapshots}
        normalizers={normalizers}
        selectedId={openSnapshot}
        onSelect={(snapshotId) =>
          setOpenSnapshot(snapshotId === openSnapshot ? null : snapshotId)
        }
        onNormalize={(snapshotId, normalizerId) =>
          act(startNormalization(snapshotId, normalizerId), `normalization of ${snapshotId}`)
        }
      />

      {openSnapshot === null ? (
        <p className="empty">Choose a snapshot above to read what it normalized to.</p>
      ) : (
        <>
          <div className="screen-header">
            <h2>normalized results</h2>
          </div>
          <ResultTable results={results} />
        </>
      )}
    </section>
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
