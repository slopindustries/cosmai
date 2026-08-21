// TanStack Query hooks over the fetch wrappers in `client.ts`. Each hook's query
// key is the argument tuple that determines its result, so a state filter, a page
// offset, or the protected-debug toggle each get their own cache entry instead of
// silently reusing another request's answer.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createNormalizeRun,
  listJobs,
  listSnapshots,
  listSources,
  readAttempts,
  readHealth,
  readJob,
  readMetrics,
  readRawItems,
  readRawSummary,
  readResults,
  readSchedule,
  readSnapshot,
  readSource,
  requestRetry,
  sealSnapshot,
  startCollection,
  startImport,
  writeCredential,
  writeSchedule,
} from "./client";
import type { JobState, ScheduleWrite } from "./types";

export function useJobsQuery(state: JobState | null, limit: number, offset: number) {
  return useQuery({
    queryKey: ["jobs", state, limit, offset] as const,
    queryFn: () => listJobs(state, limit, offset),
  });
}

export function useJobQuery(jobId: string) {
  return useQuery({
    queryKey: ["job", jobId] as const,
    queryFn: () => readJob(jobId),
    enabled: jobId !== "",
  });
}

export function useAttemptsQuery(jobId: string, wantProtected: boolean) {
  return useQuery({
    queryKey: ["attempts", jobId, wantProtected] as const,
    queryFn: () => readAttempts(jobId, wantProtected),
    enabled: jobId !== "",
  });
}

/**
 * The one write this dashboard's jobs screen offers. A successful call invalidates
 * the job, its attempts, and every jobs-list page so the accepted transition shows
 * up without a manual reload.
 */
export function useRetryMutation(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => requestRetry(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      void queryClient.invalidateQueries({ queryKey: ["attempts", jobId] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useHealthQuery() {
  return useQuery({ queryKey: ["health"] as const, queryFn: readHealth });
}

export function useMetricsQuery() {
  return useQuery({ queryKey: ["metrics"] as const, queryFn: readMetrics });
}

export function useRawItemsQuery(sourceId: string, offset: number, limit: number) {
  return useQuery({
    queryKey: ["rawItems", sourceId, offset, limit] as const,
    queryFn: () => readRawItems(sourceId, offset, limit),
    enabled: sourceId !== "",
  });
}

/**
 * DP-034 D1's one write. No `onSuccess` invalidation targets a query key here
 * on purpose: DP-034 D1 makes the route genuinely write-only — there is no
 * `GET` anywhere that reports whether a purpose is configured, so there is no
 * cache entry for a successful write to refresh. The UI can only reflect
 * "written this session," never a server-known "configured" truth (see
 * `CredentialForm`).
 */
export function useCredentialWriteMutation() {
  return useMutation({
    mutationFn: ({ sourceId, purpose, value }: { sourceId: string; purpose: string; value: string }) =>
      writeCredential(sourceId, purpose, value),
  });
}

// --------------------------------------------------------------------------- //
// The domain surface (`apps/domain/api.py`, M2). Real as of batch 5-final.
// --------------------------------------------------------------------------- //

export function useSourcesQuery() {
  return useQuery({ queryKey: ["sources"] as const, queryFn: listSources });
}

export function useSourceQuery(sourceId: string) {
  return useQuery({
    queryKey: ["source", sourceId] as const,
    queryFn: () => readSource(sourceId),
    enabled: sourceId !== "",
  });
}

export function useRawSummaryQuery(sourceId: string) {
  return useQuery({
    queryKey: ["rawSummary", sourceId] as const,
    queryFn: () => readRawSummary(sourceId),
    enabled: sourceId !== "",
  });
}

export function useScheduleQuery(sourceId: string) {
  return useQuery({
    queryKey: ["schedule", sourceId] as const,
    queryFn: () => readSchedule(sourceId),
    enabled: sourceId !== "",
  });
}

export function useScheduleWriteMutation(sourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ScheduleWrite) => writeSchedule(sourceId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedule", sourceId] });
    },
  });
}

/**
 * B12 (docs/agent-workflow/reviews/REVIEW-M2-M7.md): `POST /sources/{id}/collect`
 * has existed since M3 merged `addon_host.api`; this hook and `useStartImportMutation`
 * below are what wire the collector-domain and importer-domain screens' actions to it.
 * Invalidates the jobs list so the enqueued job shows up in job history without a
 * manual reload — the same convention `useRetryMutation` and `useSealMutation` use.
 */
export function useStartCollectionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => startCollection(sourceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/** The importer's mirror of `useStartCollectionMutation`. */
export function useStartImportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => startImport(sourceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useSnapshotsQuery(sourceId: string) {
  return useQuery({
    queryKey: ["snapshots", sourceId] as const,
    queryFn: () => listSnapshots(sourceId),
    enabled: sourceId !== "",
  });
}

export function useSnapshotQuery(snapshotId: string) {
  return useQuery({
    queryKey: ["snapshot", snapshotId] as const,
    queryFn: () => readSnapshot(snapshotId),
    enabled: snapshotId !== "",
  });
}

/** PoC Contract §8: sealing is its own act. Invalidates only this source's snapshot list. */
export function useSealMutation(sourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => sealSnapshot(sourceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["snapshots", sourceId] });
    },
  });
}

/** PoC Contract §8: normalizing is a separate act from sealing — its own mutation, its own button. */
export function useCreateNormalizeRunMutation() {
  return useMutation({
    mutationFn: ({ snapshotId, normalizerSourceId }: { snapshotId: string; normalizerSourceId: string }) =>
      createNormalizeRun(snapshotId, normalizerSourceId),
  });
}

export function useResultsQuery(snapshotId: string) {
  return useQuery({
    queryKey: ["results", snapshotId] as const,
    queryFn: () => readResults(snapshotId),
    enabled: snapshotId !== "",
  });
}
