// TanStack Query hooks over the fetch wrappers in `client.ts`. Each hook's query
// key is the argument tuple that determines its result, so a state filter, a page
// offset, or the protected-debug toggle each get their own cache entry instead of
// silently reusing another request's answer.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listJobs,
  readAttempts,
  readHealth,
  readJob,
  readMetrics,
  readRawItems,
  requestRetry,
  writeCredential,
} from "./client";
import type { JobState } from "./types";

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
 * on purpose: there is no read query for a credential's value to invalidate —
 * the "configured" status callers show today comes from mocked source detail
 * (batch 5d wires it to the real thing), not from a cache this mutation could
 * refresh.
 */
export function useCredentialWriteMutation() {
  return useMutation({
    mutationFn: ({ sourceId, purpose, value }: { sourceId: string; purpose: string; value: string }) =>
      writeCredential(sourceId, purpose, value),
  });
}
