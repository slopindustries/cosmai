// One job's detail: what ran, with which input, when, why it ended the way it
// did, whether anything is left to try, and the one write the operator API
// offers — a safe retry. Answers OPS-001's six questions and OPS-002's refusal in
// full, the way `experiments/integrated-p0/dashboard/src/view.tsx` did for P0-A;
// this is a new implementation over TanStack Query and MUI rather than a copy.

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { JSX } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAttemptsQuery, useJobQuery, useRetryMutation } from "../api/queries";
import type { Attempt, RetryOutcome } from "../api/types";
import { isRetryMissing } from "../api/types";

/** How a value that is null, absent, or empty reads on screen. */
function shown(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "—" : value;
}

export function JobDetailScreen(): JSX.Element {
  const { jobId } = useParams<{ jobId: string }>();
  const id = jobId ?? "";
  const [wantProtected, setWantProtected] = useState(false);

  const jobQuery = useJobQuery(id);
  const attemptsQuery = useAttemptsQuery(id, wantProtected);
  const retryMutation = useRetryMutation(id);

  if (jobQuery.isLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (jobQuery.isError || !jobQuery.data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          {jobQuery.error instanceof Error ? jobQuery.error.message : `no job with id ${id}`}
        </Alert>
        <Button component={Link} to="/jobs" sx={{ mt: 2 }}>
          Back to jobs
        </Button>
      </Box>
    );
  }

  const job = jobQuery.data;
  const attempts = attemptsQuery.data;
  const isProtected = attempts?.representation === "protected";
  const withheld = attempts?.attempts.some((attempt) => attempt.error_detail_present) ?? false;
  const outcome = retryMutation.data ?? null;

  return (
    <Box sx={{ p: 3 }}>
      <Button component={Link} to="/jobs" size="small" sx={{ mb: 2 }}>
        Back to jobs
      </Button>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5">job {job.id.slice(0, 8)}</Typography>
        <Chip label={job.state} color={job.state === "FAILED" ? "error" : "default"} />
      </Stack>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          what ran, when, and how it ended
        </Typography>
        <Stack spacing={0.5}>
          <Typography variant="body2">handler: {job.handler}</Typography>
          <Typography variant="body2">terminal reason: {shown(job.terminal_reason)}</Typography>
          <Typography variant="body2">correlation id: {job.correlation_id}</Typography>
          <Typography variant="body2">created at: {job.created_at}</Typography>
          <Typography variant="body2">last changed at: {job.updated_at}</Typography>
          <Typography variant="body2">
            attempts spent: {job.attempt_count} of {job.max_attempts} (remaining{" "}
            {job.attempts_remaining})
          </Typography>
          <Typography variant="body2">
            attempt budget spent: {job.attempt_budget_spent ? "yes" : "no"}
          </Typography>
          <Typography variant="subtitle2" sx={{ mt: 1 }}>
            payload
          </Typography>
          <Box component="pre" sx={{ fontSize: 12, m: 0, overflowX: "auto" }}>
            {JSON.stringify(job.payload, null, 2)}
          </Box>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          retry
        </Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          A safe retry starts from FAILED only. This job is {job.state}.
        </Typography>
        <Button
          variant="contained"
          disabled={retryMutation.isPending}
          onClick={() => retryMutation.mutate()}
        >
          Request retry
        </Button>
        {outcome ? <RetryOutcomeNote outcome={outcome} /> : null}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          attempts
        </Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          representation: <Chip size="small" label={attempts?.representation ?? "default"} />
        </Typography>
        {withheld && !isProtected ? (
          <Box sx={{ mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              At least one attempt has protected debug detail that this representation withholds.
            </Typography>
            <Button size="small" disabled={attemptsQuery.isFetching} onClick={() => setWantProtected(true)}>
              Show protected detail (?debug=protected)
            </Button>
          </Box>
        ) : null}
        {isProtected ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Protected means who may ask, not what is masked: values under reserved keys are still
            masked here.
          </Typography>
        ) : null}
        {attemptsQuery.isLoading ? <CircularProgress size={20} /> : null}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>no</TableCell>
                <TableCell>worker</TableCell>
                <TableCell>outcome</TableCell>
                <TableCell>error class</TableCell>
                <TableCell>class retryable</TableCell>
                <TableCell>started</TableCell>
                <TableCell>finished</TableCell>
                <TableCell>summary</TableCell>
                <TableCell>protected detail</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(attempts?.attempts ?? []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9}>This job has no attempt yet.</TableCell>
                </TableRow>
              ) : (
                (attempts?.attempts ?? []).map((attempt) => (
                  <TableRow key={attempt.id}>
                    <TableCell>{attempt.attempt_no}</TableCell>
                    <TableCell>{attempt.worker_id}</TableCell>
                    <TableCell>{attempt.outcome ?? "open"}</TableCell>
                    <TableCell>{shown(attempt.error_class)}</TableCell>
                    <TableCell>
                      {attempt.error_class_retryable === null
                        ? "unknown"
                        : attempt.error_class_retryable
                          ? "yes"
                          : "no"}
                    </TableCell>
                    <TableCell>{attempt.started_at}</TableCell>
                    <TableCell>{shown(attempt.finished_at)}</TableCell>
                    <TableCell>{shown(attempt.error_summary)}</TableCell>
                    <TableCell>
                      <ProtectedCell attempt={attempt} isProtected={isProtected} />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
}

/**
 * Three states, and the middle one is the one that matters: no detail exists, or
 * detail exists and is being withheld, or detail exists and was asked for. The
 * detail itself is rendered only in the third case — this is what keeps "absent
 * from the default representation" a property of the component, not a convention.
 */
function ProtectedCell({
  attempt,
  isProtected,
}: {
  attempt: Attempt;
  isProtected: boolean;
}): JSX.Element {
  if (!attempt.error_detail_present) {
    return (
      <Typography variant="body2" color="text.secondary">
        none
      </Typography>
    );
  }
  if (!isProtected) {
    return (
      <Typography variant="body2" color="warning.main">
        present, withheld
      </Typography>
    );
  }
  return (
    <Box component="pre" sx={{ fontSize: 12, m: 0, overflowX: "auto" }}>
      {JSON.stringify(attempt.error_detail, null, 2)}
    </Box>
  );
}

function RetryOutcomeNote({ outcome }: { outcome: RetryOutcome }): JSX.Element {
  if (isRetryMissing(outcome)) {
    return (
      <Alert severity="error" sx={{ mt: 1 }}>
        Not found: {outcome.detail}
      </Alert>
    );
  }
  if (outcome.accepted) {
    return (
      <Alert severity="success" sx={{ mt: 1 }}>
        Retry accepted: {outcome.previous_state} → {outcome.current_state}
      </Alert>
    );
  }
  return (
    <Alert severity="warning" sx={{ mt: 1 }}>
      Retry refused: {outcome.reason}
    </Alert>
  );
}
