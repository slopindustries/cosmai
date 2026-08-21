// DP-033 D1: one collector per domain — the management unit. Status header,
// a config form rendered from the add-on manifest's config schema, the
// DP-034 D1 credential section, job history (reusing the jobs monitor's own
// query hook, filtered by handler), and a schedule placeholder (M6).
//
// The *source list and detail* this screen renders (which domains exist,
// their status, their config schema, which credential purposes are already
// configured) are still local mock data: M2's domain API (`GET /sources` and
// friends) has not landed (Lane A ruling, batch dispatch 2026-08-21).
// `docs/superpowers/plans/2026-08-21-m2-m7-batch.md` §신규 API fixes the raw
// item route and the credential write route, and those two are wired for
// real (see `api/client.ts`); everything else here is placeholder data,
// clearly scoped to this comment, replaced in batch 5d.

import {
  Alert,
  Box,
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

import { useJobsQuery } from "../api/queries";
import { CredentialForm } from "./collector/CredentialForm";
import { ConfigSchemaForm } from "./collector/ConfigSchemaForm";
import type { ConfigField } from "./collector/ConfigSchemaForm";

/**
 * One mocked collector per domain. `configSchema` mirrors `[[config.field]]`
 * in an add-on's `addon.toml` (name/type/required/label/help — see e.g.
 * `experiments/integrated-p0/addons/collector.naver.blog/addon.toml`).
 */
interface MockCollectorSource {
  sourceId: string;
  domain: string;
  addonId: string;
  handler: string;
  enabled: boolean;
  lastSuccessAt: string | null;
  nextRunAt: string | null;
  configSchema: readonly ConfigField[];
  configuredCredentialPurposes: readonly string[];
}

const MOCK_SOURCES: readonly MockCollectorSource[] = [
  {
    sourceId: "naver-blog-main",
    domain: "naver.blog",
    addonId: "collector.naver.blog",
    handler: "collector.naver.blog.collect",
    enabled: true,
    lastSuccessAt: "2026-08-20T09:00:00Z",
    nextRunAt: "2026-08-21T09:00:00Z",
    configSchema: [
      {
        name: "query",
        type: "string",
        required: true,
        label: "Search query",
        help: "UTF-8 search term, sent as the API's required query parameter",
      },
      {
        name: "display",
        type: "integer",
        required: false,
        label: "Results per page",
        help: "1-100, defaults to 10",
      },
    ],
    configuredCredentialPurposes: ["client_id"],
  },
  {
    sourceId: "trendradar-main",
    domain: "trendradar",
    addonId: "collector.trendradar.rest",
    handler: "collector.trendradar.rest.collect",
    enabled: false,
    lastSuccessAt: null,
    nextRunAt: null,
    configSchema: [{ name: "board", type: "string", required: true, label: "Board" }],
    configuredCredentialPurposes: [],
  },
];

function shown(value: string | null): string {
  return value === null ? "—" : value;
}

export function CollectorDomainScreen(): JSX.Element {
  const [selectedId, setSelectedId] = useState(MOCK_SOURCES[0]?.sourceId ?? "");
  const source = MOCK_SOURCES.find((candidate) => candidate.sourceId === selectedId) ?? null;

  // Reuses the jobs monitor's own hook (batch 5a) rather than a second query
  // path: this table is the same job list, filtered to one handler.
  const jobsQuery = useJobsQuery(null, 100, 0);
  const jobHistory = (jobsQuery.data?.jobs ?? []).filter((job) => job.handler === source?.handler);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Collectors
      </Typography>
      <TextField
        select
        size="small"
        label="domain"
        value={selectedId}
        onChange={(event) => setSelectedId(event.target.value)}
        sx={{ mb: 2, minWidth: 260 }}
      >
        {MOCK_SOURCES.map((candidate) => (
          <MenuItem key={candidate.sourceId} value={candidate.sourceId}>
            {candidate.domain} ({candidate.addonId})
          </MenuItem>
        ))}
      </TextField>

      {source === null ? (
        <Alert severity="info">No collector selected.</Alert>
      ) : (
        <Stack spacing={2}>
          <Paper sx={{ p: 2 }} data-testid="status-header">
            <Typography variant="subtitle1" gutterBottom>
              status
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip
                label={source.enabled ? "enabled" : "disabled"}
                color={source.enabled ? "success" : "default"}
              />
              <Typography variant="body2">last success: {shown(source.lastSuccessAt)}</Typography>
              <Typography variant="body2">next run: {shown(source.nextRunAt)}</Typography>
            </Stack>
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              config
            </Typography>
            <ConfigSchemaForm
              fields={source.configSchema}
              onSubmit={() => {
                // Persisting config is M2's write path (source.config); not
                // wired in this batch. This form's own validation is what
                // this batch actually tests.
              }}
            />
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              credential
            </Typography>
            <CredentialForm
              sourceId={source.sourceId}
              configuredPurposes={source.configuredCredentialPurposes}
            />
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              job history
            </Typography>
            {jobsQuery.isLoading ? <Typography variant="body2">Loading…</Typography> : null}
            {jobsQuery.isError ? (
              <Alert severity="error">
                {jobsQuery.error instanceof Error ? jobsQuery.error.message : String(jobsQuery.error)}
              </Alert>
            ) : null}
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>job</TableCell>
                    <TableCell>state</TableCell>
                    <TableCell>created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobHistory.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3}>No job history for this collector yet.</TableCell>
                    </TableRow>
                  ) : (
                    jobHistory.map((job) => (
                      <TableRow key={job.id}>
                        <TableCell>{job.id.slice(0, 8)}</TableCell>
                        <TableCell>{job.state}</TableCell>
                        <TableCell>{job.created_at}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Paper sx={{ p: 2 }} variant="outlined" data-testid="schedule-placeholder">
            <Typography variant="subtitle1" gutterBottom>
              schedule
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No scheduler process exists yet. DP-033 D5's per-source interval and enable/disable
              toggle land in M6; this box is the reserved place for it once it does.
            </Typography>
          </Paper>
        </Stack>
      )}
    </Box>
  );
}
