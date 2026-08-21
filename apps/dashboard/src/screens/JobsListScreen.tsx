// The job list: a page of jobs, newest first, filtered by state and paged by
// `limit`/`offset`. OPS-001's own entry point — the path an operator takes to find
// a failure among jobs that mostly succeeded.

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
import { useNavigate } from "react-router-dom";

import { useJobsQuery } from "../api/queries";
import { JOB_STATES } from "../api/types";
import type { JobState } from "../api/types";

const LIMIT_OPTIONS = [25, 50, 100, 200] as const;

function shortId(identifier: string): string {
  return identifier.slice(0, 8);
}

export function JobsListScreen(): JSX.Element {
  const [state, setState] = useState<JobState | null>(null);
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState(0);
  const navigate = useNavigate();

  const { data, isLoading, isError, error } = useJobsQuery(state, limit, offset);

  function onStateChange(next: JobState | null): void {
    setState(next);
    setOffset(0);
  }

  function onLimitChange(next: number): void {
    setLimit(next);
    setOffset(0);
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Jobs
      </Typography>

      <Stack direction="row" spacing={1} sx={{ mb: 2 }} alignItems="center" flexWrap="wrap" useFlexGap>
        <Typography variant="body2" sx={{ mr: 1 }}>
          state:
        </Typography>
        <Chip
          label="any"
          color={state === null ? "primary" : "default"}
          onClick={() => onStateChange(null)}
          data-testid="state-chip-any"
        />
        {JOB_STATES.map((candidate) => (
          <Chip
            key={candidate}
            label={candidate}
            color={state === candidate ? "primary" : "default"}
            onClick={() => onStateChange(candidate)}
            data-testid={`state-chip-${candidate}`}
          />
        ))}
        <TextField
          select
          size="small"
          label="limit"
          value={limit}
          onChange={(event) => onLimitChange(Number(event.target.value))}
          sx={{ ml: "auto", minWidth: 100 }}
        >
          {LIMIT_OPTIONS.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
      </Stack>

      {isLoading ? <CircularProgress size={24} /> : null}
      {isError ? (
        <Alert severity="error">{error instanceof Error ? error.message : String(error)}</Alert>
      ) : null}

      {data ? (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            showing {data.returned} of {data.matched} matched
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>job</TableCell>
                  <TableCell>handler</TableCell>
                  <TableCell>state</TableCell>
                  <TableCell>attempts</TableCell>
                  <TableCell>created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.jobs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5}>No job matched this filter.</TableCell>
                  </TableRow>
                ) : (
                  data.jobs.map((job) => (
                    <TableRow
                      key={job.id}
                      hover
                      onClick={() => navigate(`/jobs/${job.id}`)}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell>{shortId(job.id)}</TableCell>
                      <TableCell>{job.handler}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={job.state}
                          color={job.state === "FAILED" ? "error" : "default"}
                        />
                      </TableCell>
                      <TableCell>
                        {job.attempt_count} / {job.max_attempts}
                      </TableCell>
                      <TableCell>{job.created_at}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
            <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              Previous
            </Button>
            <Button disabled={offset + limit >= data.matched} onClick={() => setOffset(offset + limit)}>
              Next
            </Button>
          </Stack>
        </>
      ) : null}
    </Box>
  );
}
