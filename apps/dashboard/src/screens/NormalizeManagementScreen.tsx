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
// Every write here (seal, create run) is a **local mock** — neither action
// has a route this batch's brief or the plan fixes yet (unlike the
// credential and raw-item calls batch 5b/5c wired for real against fixed
// shapes). Batch 5-final wires both to the real M2 domain routes
// (`extend_with_domain`'s reproduction of P0's `addon_host/api.py`,
// specifically its `sealSnapshot`/`startNormalization` shapes) once M2
// merges. The snapshot list, normalizer list, and results are likewise mock
// data pending `GET /sources`/`GET /snapshots`/`GET /snapshots/{id}/results`.

import {
  Alert,
  Box,
  Button,
  Chip,
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

import { MOCK_SOURCE_OPTIONS } from "../mocks/sources";

interface MockSnapshot {
  snapshot_id: string;
  source_id: string;
  item_count: number;
  manifest_sha256: string;
  sealed_at: string | null;
  verifies: boolean;
  problems: readonly string[];
}

interface MockNormalizerOption {
  addon_id: string;
  version: string;
}

/** One record's normalization outcome. `normalize_error` mirrors DP-030 D2's `notes.normalize_error {field, reason}`. */
interface MockNormalizedRecord {
  id: string;
  source_item_key: string;
  body_preview: string;
  normalize_error: { field: string; reason: string } | null;
}

/** One (addon, version, output_contract_version) group — one side of "versions coexist" (PoC Contract §5). */
interface MockResultGroup {
  addon_id: string;
  addon_version: string;
  output_contract_version: string;
  records: readonly MockNormalizedRecord[];
}

const SEEDED_SNAPSHOT_ID = "22222222-1111-1111-1111-111111111111";

const INITIAL_SNAPSHOTS: Readonly<Record<string, readonly MockSnapshot[]>> = {
  "naver-blog-main": [
    {
      snapshot_id: SEEDED_SNAPSHOT_ID,
      source_id: "naver-blog-main",
      item_count: 42,
      manifest_sha256: "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff",
      sealed_at: "2026-08-20T10:00:00Z",
      verifies: true,
      problems: [],
    },
  ],
  "trendradar-main": [],
};

const MOCK_NORMALIZERS: readonly MockNormalizerOption[] = [
  { addon_id: "normalizer.naver.blog", version: "0.1.0" },
  { addon_id: "normalizer.naver.blog", version: "0.2.0" },
  { addon_id: "normalizer.obf.product", version: "0.1.0" },
];

/** Two versions over the one seeded snapshot — the version-coexistence case this screen has to render side by side. */
const MOCK_RESULTS: Readonly<Record<string, readonly MockResultGroup[]>> = {
  [SEEDED_SNAPSHOT_ID]: [
    {
      addon_id: "normalizer.naver.blog",
      addon_version: "0.1.0",
      output_contract_version: "0.2",
      records: [
        {
          id: "result-0.1.0-post-1",
          source_item_key: "post-1",
          body_preview: '{"title":"hello"}',
          normalize_error: null,
        },
        {
          id: "result-0.1.0-post-2",
          source_item_key: "post-2",
          body_preview: '{"title":null}',
          normalize_error: { field: "published_at", reason: "unparseable date" },
        },
      ],
    },
    {
      addon_id: "normalizer.naver.blog",
      addon_version: "0.2.0",
      output_contract_version: "0.3",
      records: [
        {
          id: "result-0.2.0-post-1",
          source_item_key: "post-1",
          body_preview: '{"title":"hello","record_type":"document"}',
          normalize_error: null,
        },
        {
          id: "result-0.2.0-post-2",
          source_item_key: "post-2",
          body_preview: '{"title":"second post","record_type":"document"}',
          normalize_error: null,
        },
      ],
    },
  ],
};

function shortDigest(sha256: string): string {
  return sha256.slice(0, 12);
}

let mockSnapshotSequence = 0;

/** Mock seal: no fixed route exists yet for this batch — see the file header. */
function mockSealSnapshot(sourceId: string): MockSnapshot {
  mockSnapshotSequence += 1;
  return {
    snapshot_id: `mock-snapshot-${mockSnapshotSequence}`,
    source_id: sourceId,
    item_count: 0,
    manifest_sha256: "0".repeat(64),
    sealed_at: new Date().toISOString(),
    verifies: true,
    problems: [],
  };
}

export function NormalizeManagementScreen(): JSX.Element {
  const [sourceId, setSourceId] = useState(MOCK_SOURCE_OPTIONS[0]?.sourceId ?? "");
  const [snapshotsBySource, setSnapshotsBySource] =
    useState<Readonly<Record<string, readonly MockSnapshot[]>>>(INITIAL_SNAPSHOTS);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const firstNormalizer = MOCK_NORMALIZERS[0];
  const [normalizerChoice, setNormalizerChoice] = useState(
    firstNormalizer === undefined ? "" : `${firstNormalizer.addon_id}@${firstNormalizer.version}`,
  );
  const [sealNotice, setSealNotice] = useState<string | null>(null);
  const [runNotice, setRunNotice] = useState<string | null>(null);

  const snapshots = snapshotsBySource[sourceId] ?? [];
  const selectedSnapshot = snapshots.find((snap) => snap.snapshot_id === selectedSnapshotId) ?? null;
  const resultGroups = selectedSnapshotId === null ? [] : (MOCK_RESULTS[selectedSnapshotId] ?? []);

  function onSourceChange(next: string): void {
    setSourceId(next);
    setSelectedSnapshotId(null);
    setRunNotice(null);
  }

  function onSeal(): void {
    const created = mockSealSnapshot(sourceId);
    setSnapshotsBySource((previous) => ({
      ...previous,
      [sourceId]: [...(previous[sourceId] ?? []), created],
    }));
    setSealNotice(`Sealed snapshot ${created.snapshot_id} (mocked — no request was sent).`);
  }

  function onCreateRun(): void {
    if (selectedSnapshot === null) {
      return;
    }
    setRunNotice(
      `Normalize run requested for ${selectedSnapshot.snapshot_id.slice(0, 8)} with ` +
        `${normalizerChoice} (mocked — no request was sent).`,
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Normalization
      </Typography>

      <TextField
        select
        size="small"
        label="source"
        value={sourceId}
        onChange={(event) => onSourceChange(event.target.value)}
        sx={{ mb: 2, minWidth: 220 }}
      >
        {MOCK_SOURCE_OPTIONS.map((option) => (
          <MenuItem key={option.sourceId} value={option.sourceId}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>

      {/* Pane A: sealed snapshots — one operator act (seal), its own button. */}
      <Paper sx={{ p: 2, mb: 2 }} data-testid="snapshots-pane">
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle1">sealed snapshots</Typography>
          <Button variant="outlined" onClick={onSeal} data-testid="seal-button">
            Seal snapshot
          </Button>
        </Stack>
        {sealNotice === null ? null : (
          <Alert severity="success" sx={{ mb: 1 }}>
            {sealNotice}
          </Alert>
        )}
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
        ) : (
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2">
              snapshot: <code>{selectedSnapshot.snapshot_id.slice(0, 8)}</code>
            </Typography>
            <TextField
              select
              size="small"
              label="normalizer"
              value={normalizerChoice}
              onChange={(event) => setNormalizerChoice(event.target.value)}
              sx={{ minWidth: 260 }}
            >
              {MOCK_NORMALIZERS.map((normalizer) => {
                const key = `${normalizer.addon_id}@${normalizer.version}`;
                return (
                  <MenuItem key={key} value={key}>
                    {normalizer.addon_id} @ {normalizer.version}
                  </MenuItem>
                );
              })}
            </TextField>
            <Button
              variant="contained"
              onClick={onCreateRun}
              data-testid="create-run-button"
              disabled={!selectedSnapshot.verifies}
            >
              Create run
            </Button>
          </Stack>
        )}
        {runNotice === null ? null : (
          <Alert severity="success" sx={{ mt: 1 }}>
            {runNotice}
          </Alert>
        )}
      </Paper>

      {/* Pane C: results — versions coexist, side by side, per-record error badge. */}
      <Paper sx={{ p: 2 }} data-testid="results-pane">
        <Typography variant="subtitle1" gutterBottom>
          results
        </Typography>
        {selectedSnapshot === null ? (
          <Alert severity="info">Select a sealed snapshot above to view its normalized results.</Alert>
        ) : resultGroups.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No normalize run has completed for this snapshot yet.
          </Typography>
        ) : (
          <Box sx={{ display: "flex", gap: 2, overflowX: "auto" }}>
            {resultGroups.map((group) => {
              const errorCount = group.records.filter((record) => record.normalize_error !== null).length;
              return (
                <Paper
                  key={`${group.addon_id}@${group.addon_version}`}
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
                        {group.records.map((record) => (
                          <TableRow key={record.id}>
                            <TableCell>{record.source_item_key}</TableCell>
                            <TableCell>
                              <code>{record.body_preview}</code>
                            </TableCell>
                            <TableCell>
                              {record.normalize_error === null ? (
                                <Typography variant="body2" color="text.secondary">
                                  —
                                </Typography>
                              ) : (
                                <Chip
                                  size="small"
                                  color="warning"
                                  label={`normalize_error: ${record.normalize_error.field}`}
                                  data-testid="normalize-error-badge"
                                />
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
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
