// DP-033 D1 / spec §6 / PoC Contract §8: a management frame over sealed
// snapshots, normalize-run creation, and version-coexisting results.
//
// Contract §8: "Four operator actions, one per act: collect, seal, normalize,
// read... Sealing and normalizing are separate deliberate acts and must not
// be combined into one control." This screen keeps them as two buttons in
// two sections (`seal-button` in the snapshots pane, `create-run-button` in
// the create-run pane) rather than one action that both seals and
// normalizes. Contract §8 also fixes that "a snapshot's verification state
// is its own column, never folded into a status word" — the snapshots table
// below has a dedicated `verifies` column rather than folding it into, say, a
// combined status chip.
//
// Real as of batch 5-final: sealing (`POST /sources/{id}/snapshots`),
// listing snapshots (`GET /snapshots?source_id`), creating a normalize run
// (`POST /snapshots/{id}/normalize`), and reading results (`GET
// /snapshots/{id}/results`) all come from `apps/domain/api.py`, merged from
// `dev`.
//
// **Mismatch found and fixed reconciling against the real route:** batch 5d's
// "create run" picker offered a mocked `{addon_id, version}` pair. The real
// route (`start_normalization`) takes `{source_id}` — a registered **source
// of kind `normalizer`**, not an addon/version pair — because a normalizer
// is itself a registered source row with its own `addon_id`/`addon_version`
// already fixed at registration. Fixed: the picker below lists registered
// `kind === "normalizer"` sources instead.
//
// The created normalize job stays `PENDING` until M3 registers an `addon:*`
// worker (`apps/domain/api.py`'s own docstring), so a `201` here reads as
// "the job was created," not "it ran" — the results pane will show nothing
// for a fresh run until M3 lands, which is expected and not a bug in this
// screen.

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import type { JSX } from "react";
import { useState } from "react";

import { useCreateNormalizeRunMutation, useResultsQuery, useSealMutation, useSnapshotsQuery, useSourcesQuery } from "../api/queries";
import type { NormalizedResult } from "../api/types";
import { isDomainRefused, normalizeErrorOf } from "../api/types";

function shortDigest(sha256: string): string {
  return sha256.slice(0, 12);
}

/** One (addon, version, output_contract_version) group — one side of "versions coexist" (PoC Contract §5). */
interface ResultGroup {
  addon_id: string;
  addon_version: string;
  output_contract_version: string;
  records: NormalizedResult[];
}

function groupResults(results: readonly NormalizedResult[]): ResultGroup[] {
  const groups = new Map<string, ResultGroup>();
  for (const result of results) {
    const key = `${result.addon_id}@${result.addon_version}@${result.output_contract_version}`;
    const existing = groups.get(key);
    if (existing) {
      existing.records.push(result);
    } else {
      groups.set(key, {
        addon_id: result.addon_id,
        addon_version: result.addon_version,
        output_contract_version: result.output_contract_version,
        records: [result],
      });
    }
  }
  return [...groups.values()];
}

export function NormalizeManagementScreen(): JSX.Element {
  const sourcesQuery = useSourcesQuery();
  const sealableSources = (sourcesQuery.data?.sources ?? []).filter(
    (source) => source.kind === "collector" || source.kind === "importer",
  );
  const normalizerSources = (sourcesQuery.data?.sources ?? []).filter((source) => source.kind === "normalizer");

  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const sourceId = selectedSourceId ?? sealableSources[0]?.source_id ?? "";
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [normalizerChoice, setNormalizerChoice] = useState<string | null>(null);
  const normalizerSourceId = normalizerChoice ?? normalizerSources[0]?.source_id ?? "";

  const snapshotsQuery = useSnapshotsQuery(sourceId);
  const snapshots = snapshotsQuery.data?.snapshots ?? [];
  const selectedSnapshot = snapshots.find((snap) => snap.snapshot_id === selectedSnapshotId) ?? null;

  const resultsQuery = useResultsQuery(selectedSnapshotId ?? "");
  const resultGroups = groupResults(resultsQuery.data?.results ?? []);

  const sealMutation = useSealMutation(sourceId);
  const createRunMutation = useCreateNormalizeRunMutation();

  function onSourceChange(next: string): void {
    setSelectedSourceId(next);
    setSelectedSnapshotId(null);
  }

  function onSeal(): void {
    sealMutation.mutate();
  }

  function onCreateRun(): void {
    if (selectedSnapshot === null || normalizerSourceId === "") {
      return;
    }
    createRunMutation.mutate({ snapshotId: selectedSnapshot.snapshot_id, normalizerSourceId });
  }

  const sealOutcome = sealMutation.data;
  const runOutcome = createRunMutation.data;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Normalization
      </Typography>

      {sourcesQuery.isError ? (
        <Alert severity="error">
          {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : String(sourcesQuery.error)}
        </Alert>
      ) : null}

      {sealableSources.length > 0 ? (
        <TextField
          select
          size="small"
          label="source"
          value={sourceId}
          onChange={(event) => onSourceChange(event.target.value)}
          sx={{ mb: 2, minWidth: 220 }}
        >
          {sealableSources.map((option) => (
            <MenuItem key={option.source_id} value={option.source_id}>
              {option.source_id} ({option.kind})
            </MenuItem>
          ))}
        </TextField>
      ) : sourcesQuery.data ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          No collector or importer source is registered yet — sealing needs one of those kinds.
        </Alert>
      ) : null}

      {/* Pane A: sealed snapshots — one operator act (seal), its own button. */}
      <Paper sx={{ p: 2, mb: 2 }} data-testid="snapshots-pane">
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle1">sealed snapshots</Typography>
          <Button variant="outlined" onClick={onSeal} disabled={sourceId === "" || sealMutation.isPending} data-testid="seal-button">
            Seal snapshot
          </Button>
        </Stack>
        {sealOutcome ? (
          isDomainRefused(sealOutcome) ? (
            <Alert severity="error" sx={{ mb: 1 }}>
              Seal refused: {sealOutcome.detail}
            </Alert>
          ) : (
            <Alert severity="success" sx={{ mb: 1 }}>
              Sealed snapshot {sealOutcome.snapshot_id.slice(0, 8)} ({sealOutcome.item_count} items).
            </Alert>
          )
        ) : null}
        {snapshotsQuery.isLoading ? <CircularProgress size={20} /> : null}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>snapshot</TableCell>
                <TableCell>items</TableCell>
                <TableCell>manifest digest</TableCell>
                <TableCell>sealed at</TableCell>
                {/* Contract §8: verification state is its own column, never folded into a status word. */}
                <TableCell>verifies</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {snapshots.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5}>No sealed snapshot for this source yet.</TableCell>
                </TableRow>
              ) : (
                snapshots.map((snap) => (
                  <TableRow
                    key={snap.snapshot_id}
                    hover
                    selected={snap.snapshot_id === selectedSnapshotId}
                    onClick={() => setSelectedSnapshotId(snap.snapshot_id)}
                    sx={{ cursor: "pointer" }}
                  >
                    <TableCell>{snap.snapshot_id.slice(0, 8)}</TableCell>
                    <TableCell>{snap.item_count}</TableCell>
                    <TableCell>
                      <code>{shortDigest(snap.manifest_sha256)}</code>
                    </TableCell>
                    <TableCell>{snap.sealed_at ?? "—"}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={snap.verifies ? "verifies" : `fails — ${snap.problems.join("; ")}`}
                        color={snap.verifies ? "success" : "error"}
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Pane B: create run — the other operator act (normalize), a separate button. */}
      <Paper sx={{ p: 2, mb: 2 }} data-testid="create-run-pane">
        <Typography variant="subtitle1" gutterBottom>
          create run
        </Typography>
        {selectedSnapshot === null ? (
          <Alert severity="info">Select a sealed snapshot above to create a normalize run.</Alert>
        ) : normalizerSources.length === 0 ? (
          <Alert severity="info">No normalizer source is registered yet.</Alert>
        ) : (
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2">
              snapshot: <code>{selectedSnapshot.snapshot_id.slice(0, 8)}</code>
            </Typography>
            <TextField
              select
              size="small"
              label="normalizer"
              value={normalizerSourceId}
              onChange={(event) => setNormalizerChoice(event.target.value)}
              sx={{ minWidth: 300 }}
            >
              {normalizerSources.map((normalizer) => (
                <MenuItem key={normalizer.source_id} value={normalizer.source_id}>
                  {normalizer.addon_id} @ {normalizer.addon_version} ({normalizer.source_id})
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              onClick={onCreateRun}
              data-testid="create-run-button"
              disabled={!selectedSnapshot.verifies || createRunMutation.isPending}
            >
              Create run
            </Button>
          </Stack>
        )}
        {runOutcome ? (
          isDomainRefused(runOutcome) ? (
            <Alert severity="error" sx={{ mt: 1 }}>
              Run refused: {runOutcome.detail}
            </Alert>
          ) : (
            <Alert severity="success" sx={{ mt: 1 }}>
              Normalize run enqueued as job {runOutcome.job_id.slice(0, 8)}. It stays PENDING until
              M3 registers a worker for it.
            </Alert>
          )
        ) : null}
      </Paper>

      {/* Pane C: results — versions coexist, side by side, per-record error badge. */}
      <Paper sx={{ p: 2 }} data-testid="results-pane">
        <Typography variant="subtitle1" gutterBottom>
          results
        </Typography>
        {selectedSnapshot === null ? (
          <Alert severity="info">Select a sealed snapshot above to view its normalized results.</Alert>
        ) : resultsQuery.isLoading ? (
          <CircularProgress size={20} />
        ) : resultGroups.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No normalize run has completed for this snapshot yet.
          </Typography>
        ) : (
          <Box sx={{ display: "flex", gap: 2, overflowX: "auto" }}>
            {resultGroups.map((group) => {
              const errorCount = group.records.filter((record) => normalizeErrorOf(record.notes) !== null).length;
              return (
                <Paper
                  key={`${group.addon_id}@${group.addon_version}@${group.output_contract_version}`}
                  variant="outlined"
                  sx={{ p: 2, minWidth: 300, flex: "1 1 300px" }}
                  data-testid="result-version-group"
                >
                  <Typography variant="subtitle2">
                    {group.addon_id} @ {group.addon_version}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    output contract {group.output_contract_version}
                  </Typography>
                  {/* DP-030 D2: the run summary aggregates the error-record count. */}
                  <Typography variant="body2" sx={{ mb: 1 }} data-testid="result-group-summary">
                    {group.records.length} record{group.records.length === 1 ? "" : "s"}, {errorCount}{" "}
                    error{errorCount === 1 ? "" : "s"}
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>item key</TableCell>
                          <TableCell>body</TableCell>
                          <TableCell>error</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {group.records.map((record) => {
                          const error = normalizeErrorOf(record.notes);
                          return (
                            <TableRow key={record.id}>
                              <TableCell>{record.source_item_key}</TableCell>
                              <TableCell>
                                <code>{JSON.stringify(record.body)}</code>
                              </TableCell>
                              <TableCell>
                                {error === null ? (
                                  <Typography variant="body2" color="text.secondary">
                                    —
                                  </Typography>
                                ) : (
                                  <Chip
                                    size="small"
                                    color="warning"
                                    label={`normalize_error: ${error.field}`}
                                    data-testid="normalize-error-badge"
                                  />
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              );
            })}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
