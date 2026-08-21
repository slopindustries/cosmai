// DP-033 D3: a scope-filtered, streamed export, delivered as a URL rather
// than a network call this screen makes itself. `buildExportUrl`
// (`./download/buildExportUrl.ts`) is the actual deliverable — correct
// query-string construction against `apps/domain/api.py`'s real
// `export_raw`/`export_results` routes (see that module's own mismatch note
// for what changed reconciling against the real signatures). No fetch
// happens here; the operator opens the link or copies the curl line.
//
// Real as of batch 5-final: the source selector's options come from `GET
// /sources` (`apps/domain/api.py`, merged from `dev`).

import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { JSX } from "react";
import { useState } from "react";

import { apiBase } from "../api/client";
import { useSourcesQuery } from "../api/queries";
import type { ExportFormat, ExportKind } from "./download/buildExportUrl";
import { buildExportUrl, curlLine } from "./download/buildExportUrl";

export function DownloadScreen(): JSX.Element {
  const sourcesQuery = useSourcesQuery();
  const sources = sourcesQuery.data?.sources ?? [];

  const [kind, setKind] = useState<ExportKind>("raw");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const sourceId = selectedSourceId ?? sources[0]?.source_id ?? "";
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [keyPrefix, setKeyPrefix] = useState("");
  const [format, setFormat] = useState<ExportFormat>("jsonl");

  const url = buildExportUrl(apiBase(), { sourceId, from, to, keyPrefix, format, kind });

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Downloads
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        No request is sent from this screen — it only builds a scope-filtered, streamable export
        URL (DP-033 D3) for the operator to open or curl directly.
      </Typography>

      {sourcesQuery.isError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : String(sourcesQuery.error)}
        </Alert>
      ) : null}

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack spacing={2}>
          <RadioGroup row value={kind} onChange={(event) => setKind(event.target.value as ExportKind)}>
            <FormControlLabel value="raw" control={<Radio />} label="Raw" />
            <FormControlLabel value="results" control={<Radio />} label="Normalized results" />
          </RadioGroup>

          {sources.length > 0 ? (
            <TextField
              select
              size="small"
              label="source"
              value={sourceId}
              onChange={(event) => setSelectedSourceId(event.target.value)}
              sx={{ maxWidth: 260 }}
            >
              {sources.map((option) => (
                <MenuItem key={option.source_id} value={option.source_id}>
                  {option.source_id}
                </MenuItem>
              ))}
            </TextField>
          ) : sourcesQuery.data ? (
            <Typography variant="body2" color="text.secondary">
              No source is registered yet.
            </Typography>
          ) : null}

          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="from"
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              label="to"
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              label="item_key prefix"
              value={keyPrefix}
              onChange={(event) => setKeyPrefix(event.target.value)}
            />
          </Stack>

          {/* Both /export/raw and /export/results accept jsonl or csv identically
              (apps/domain/api.py) — the format choice is never disabled by kind. */}
          <RadioGroup row value={format} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
            <FormControlLabel value="jsonl" control={<Radio />} label="JSONL" />
            <FormControlLabel value="csv" control={<Radio />} label="CSV" />
          </RadioGroup>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          export
        </Typography>
        <Box component="pre" data-testid="export-url" sx={{ fontSize: 12, m: 0, whiteSpace: "pre-wrap", overflowX: "auto" }}>
          {url}
        </Box>
        <Stack direction="row" spacing={2} sx={{ mt: 1.5 }} alignItems="center">
          <Button component="a" href={url} variant="contained" data-testid="download-link">
            Download
          </Button>
        </Stack>
        <Typography variant="body2" sx={{ mt: 2 }}>
          curl
        </Typography>
        <Box
          component="pre"
          data-testid="export-curl"
          sx={{ fontSize: 12, m: 0, whiteSpace: "pre-wrap", overflowX: "auto" }}
        >
          {curlLine(url)}
        </Box>
      </Paper>
    </Box>
  );
}
