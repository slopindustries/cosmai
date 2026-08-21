// DP-033 D1: one collector per domain — the management unit. Status header,
// a config form, the DP-034 D1 credential section, job history (reusing the
// jobs monitor's own query hook, filtered by handler), and a schedule editor.
//
// Real as of batch 5-final: the source list/detail (`GET /sources`), raw
// summary (`GET /sources/{id}/raw`), and schedule (`GET|PUT
// /sources/{id}/schedule`) all come from `apps/domain/api.py` / M6's
// scheduler, merged from `dev`.
//
// - **The config-schema form still renders a per-`addon_id` mock.**
//   `apps/domain/api.py`'s `source_view` returns `config` (the source's
//   current *values*) but no route anywhere exposes the add-on manifest's
//   *schema* (`[[config.field]]`) — that lives in `addon.toml` and only
//   `addon_host` (M3) will ever parse it. `MOCK_CONFIG_SCHEMAS` below is a
//   per-addon guess at that shape, kept from batch 5b/5c; it renders and
//   validates, but submitting it is a no-op (no write route exists either).
// - **"Collect now" is wired.** `POST /sources/{id}/collect` has existed in
//   `apps/addon_host/api.py` since M3 merged; this screen shipped with the
//   action disabled and a note claiming the route did not exist (B12,
//   `docs/agent-workflow/reviews/REVIEW-M2-M7.md`). `useStartCollectionMutation`
//   fires the request and this pane renders the `201`/refusal it gets back.

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  Switch,
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

import {
  useJobsQuery,
  useRawSummaryQuery,
  useScheduleQuery,
  useScheduleWriteMutation,
  useSourcesQuery,
  useStartCollectionMutation,
} from "../api/queries";
import { isDomainRefused } from "../api/types";
import { CredentialForm } from "./collector/CredentialForm";
import { ConfigSchemaForm } from "./collector/ConfigSchemaForm";
import type { ConfigField } from "./collector/ConfigSchemaForm";

/** A per-`addon_id` guess at the manifest config schema — see this file's header comment. */
const MOCK_CONFIG_SCHEMAS: Readonly<Record<string, readonly ConfigField[]>> = {
  "collector.naver.blog": [
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
  "collector.trendradar.rest": [{ name: "board", type: "string", required: true, label: "Board" }],
};

function shown(value: string | null): string {
  return value === null ? "—" : value;
}

export function CollectorDomainScreen(): JSX.Element {
  const sourcesQuery = useSourcesQuery();
  const collectors = (sourcesQuery.data?.sources ?? []).filter((source) => source.kind === "collector");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const effectiveId = selectedId ?? collectors[0]?.source_id ?? "";
  const source = collectors.find((candidate) => candidate.source_id === effectiveId) ?? null;

  const rawSummaryQuery = useRawSummaryQuery(effectiveId);
  const scheduleQuery = useScheduleQuery(effectiveId);
  const scheduleMutation = useScheduleWriteMutation(effectiveId);
  const [intervalInput, setIntervalInput] = useState("3600");
  const collectMutation = useStartCollectionMutation();
  const collectOutcome = collectMutation.data;

  // Reuses the jobs monitor's own hook (batch 5a) rather than a second query
  // path: this table is the same job list, filtered to one handler. The
  // handler naming convention (`addon:<addon_id>`) is `apps/domain/api.py`'s
  // own `HANDLER_PREFIX`, not a guess.
  const jobsQuery = useJobsQuery(null, 100, 0);
  const jobHistory = (jobsQuery.data?.jobs ?? []).filter(
    (job) => source !== null && job.handler === `addon:${source.addon_id}`,
  );

  const configSchema = source === null ? [] : (MOCK_CONFIG_SCHEMAS[source.addon_id] ?? []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Collectors
      </Typography>

      {sourcesQuery.isLoading ? <CircularProgress size={24} /> : null}
      {sourcesQuery.isError ? (
        <Alert severity="error">
          {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : String(sourcesQuery.error)}
        </Alert>
      ) : null}

      {sourcesQuery.data && collectors.length === 0 ? (
        <Alert severity="info">No collector source is registered yet.</Alert>
      ) : null}

      {collectors.length > 0 ? (
        <TextField
          select
          size="small"
          label="domain"
          value={effectiveId}
          onChange={(event) => setSelectedId(event.target.value)}
          sx={{ mb: 2, minWidth: 260 }}
        >
          {collectors.map((candidate) => (
            <MenuItem key={candidate.source_id} value={candidate.source_id}>
              {candidate.source_id} ({candidate.addon_id})
            </MenuItem>
          ))}
        </TextField>
      ) : null}

      {source === null ? null : (
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
              <Typography variant="body2">
                last retrieved: {shown(rawSummaryQuery.data?.last_retrieved_at ?? null)}
              </Typography>
              <Typography variant="body2">
                items collected: {rawSummaryQuery.data?.item_count ?? "—"}
              </Typography>
              <Typography variant="body2">
                next scheduled run: {shown(scheduleQuery.data?.next_run_at ?? null)}
              </Typography>
              <Button
                variant="outlined"
                disabled={collectMutation.isPending}
                onClick={() => collectMutation.mutate(source.source_id)}
                data-testid="collect-now-button"
              >
                Collect now
              </Button>
            </Stack>
            {collectOutcome ? (
              isDomainRefused(collectOutcome) ? (
                <Alert severity="error" sx={{ mt: 1 }} data-testid="collect-outcome">
                  Collection refused: {collectOutcome.detail}
                </Alert>
              ) : (
                <Alert severity="success" sx={{ mt: 1 }} data-testid="collect-outcome">
                  Collect job {collectOutcome.job_id.slice(0, 8)} enqueued for {collectOutcome.source_id}.
                </Alert>
              )
            ) : null}
            {collectMutation.isError ? (
              <Alert severity="error" sx={{ mt: 1 }}>
                {collectMutation.error instanceof Error
                  ? collectMutation.error.message
                  : String(collectMutation.error)}
              </Alert>
            ) : null}
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              config
            </Typography>
            {configSchema.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No config schema is available for {source.addon_id} yet — no route exposes the
                add-on manifest's schema until M3.
              </Typography>
            ) : (
              <ConfigSchemaForm
                fields={configSchema}
                onSubmit={() => {
                  // Persisting config is a write to source.config; no route
                  // for it exists yet either. This form's own validation is
                  // what this screen's test exercises.
                }}
              />
            )}
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              credential
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              registered ref: {shown(source.credential_ref)}
            </Typography>
            <CredentialForm sourceId={source.source_id} />
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

          <Paper sx={{ p: 2 }} data-testid="schedule-pane">
            <Typography variant="subtitle1" gutterBottom>
              schedule
            </Typography>
            {scheduleQuery.isLoading ? <CircularProgress size={20} /> : null}
            {scheduleQuery.data ? (
              <Stack spacing={1}>
                <Typography variant="body2">
                  {scheduleQuery.data.enabled
                    ? `enabled, every ${String(scheduleQuery.data.interval_seconds)}s`
                    : "not configured or disabled"}
                </Typography>
                <Typography variant="body2">
                  next run: {shown(scheduleQuery.data.next_run_at)} · last run:{" "}
                  {shown(scheduleQuery.data.last_run_at)}
                </Typography>
                <Stack direction="row" spacing={2} alignItems="center">
                  <TextField
                    size="small"
                    label="interval (s)"
                    value={intervalInput}
                    onChange={(event) => setIntervalInput(event.target.value)}
                    sx={{ maxWidth: 140 }}
                  />
                  <Stack direction="row" alignItems="center">
                    <Typography variant="body2">enabled</Typography>
                    <Switch
                      checked={scheduleQuery.data.enabled}
                      onChange={(event) => {
                        const interval = Number.parseInt(intervalInput, 10);
                        if (Number.isNaN(interval) || interval <= 0) {
                          return;
                        }
                        scheduleMutation.mutate({ interval_seconds: interval, enabled: event.target.checked });
                      }}
                    />
                  </Stack>
                  <Button
                    variant="outlined"
                    disabled={scheduleMutation.isPending}
                    onClick={() => {
                      const interval = Number.parseInt(intervalInput, 10);
                      if (Number.isNaN(interval) || interval <= 0) {
                        return;
                      }
                      scheduleMutation.mutate({
                        interval_seconds: interval,
                        enabled: scheduleQuery.data?.enabled ?? true,
                      });
                    }}
                  >
                    Save schedule
                  </Button>
                </Stack>
              </Stack>
            ) : null}
            {scheduleMutation.isError ? (
              <Alert severity="error" sx={{ mt: 1 }}>
                {scheduleMutation.error instanceof Error
                  ? scheduleMutation.error.message
                  : String(scheduleMutation.error)}
              </Alert>
            ) : null}
          </Paper>
        </Stack>
      )}
    </Box>
  );
}
