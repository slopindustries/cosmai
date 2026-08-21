// Health and metrics: whether the platform can do the one thing every other
// endpoint needs (`GET /health`), this process's own counters (`GET /metrics`),
// and a placeholder for scheduler status — DP-033 D1 carries P0's health screen
// forward "plus scheduler status", and the scheduler itself is M6, not this batch.

import {
  Alert,
  Box,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import type { JSX } from "react";

import { useHealthQuery, useMetricsQuery } from "../api/queries";
import { isHealthy } from "../api/types";

export function HealthScreen(): JSX.Element {
  const healthQuery = useHealthQuery();
  const metricsQuery = useMetricsQuery();

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Health &amp; metrics
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          platform health
        </Typography>
        {healthQuery.isLoading ? <CircularProgress size={20} /> : null}
        {healthQuery.isError ? (
          <Alert severity="error">
            {healthQuery.error instanceof Error ? healthQuery.error.message : String(healthQuery.error)}
          </Alert>
        ) : null}
        {healthQuery.data ? (
          isHealthy(healthQuery.data) ? (
            <Stack spacing={0.5}>
              <Alert severity="success">status: {healthQuery.data.status}</Alert>
              <Typography variant="body2">
                database: {healthQuery.data.database} ({healthQuery.data.database_name})
              </Typography>
              <Typography variant="body2">log level: {healthQuery.data.log_level}</Typography>
              <Typography variant="body2">jobs by state:</Typography>
              <Box component="pre" sx={{ fontSize: 12, m: 0 }}>
                {JSON.stringify(healthQuery.data.jobs_by_state, null, 2)}
              </Box>
            </Stack>
          ) : (
            <Stack spacing={0.5}>
              <Alert severity="error">status: {healthQuery.data.status}</Alert>
              <Typography variant="body2">
                database: {healthQuery.data.database} ({healthQuery.data.database_name})
              </Typography>
              <Typography variant="body2">error class: {healthQuery.data.error_class}</Typography>
              <Typography variant="body2">error summary: {healthQuery.data.error_summary}</Typography>
            </Stack>
          )
        ) : null}
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          metrics
        </Typography>
        {metricsQuery.isLoading ? <CircularProgress size={20} /> : null}
        {metricsQuery.isError ? (
          <Alert severity="error">
            {metricsQuery.error instanceof Error ? metricsQuery.error.message : String(metricsQuery.error)}
          </Alert>
        ) : null}
        {metricsQuery.data ? (
          <Stack spacing={0.5}>
            <Typography variant="body2">
              scope: {metricsQuery.data.scope} (pid {metricsQuery.data.pid})
            </Typography>
            <Typography variant="body2">claim conflicts: {metricsQuery.data.metrics.claim_conflicts}</Typography>
            <Typography variant="body2">
              suppressed duplicate effects: {metricsQuery.data.metrics.suppressed_duplicate_effects}
            </Typography>
            <Typography variant="body2">
              abandoned attempts: {metricsQuery.data.metrics.abandoned_attempts}
            </Typography>
            <Typography variant="body2">
              rejected completions: {metricsQuery.data.metrics.rejected_completions}
            </Typography>
            <Typography variant="body2">transitions:</Typography>
            <Box component="pre" sx={{ fontSize: 12, m: 0 }}>
              {JSON.stringify(metricsQuery.data.metrics.transitions, null, 2)}
            </Box>
          </Stack>
        ) : null}
      </Paper>

      <Paper sx={{ p: 2 }} variant="outlined" data-testid="scheduler-placeholder">
        <Typography variant="subtitle1" gutterBottom>
          scheduler
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No scheduler process exists yet. DP-033 D5's scheduler and its due/enabled status land in
          M6; this box is the reserved place for it once it does.
        </Typography>
      </Paper>
    </Box>
  );
}
