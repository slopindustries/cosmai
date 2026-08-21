// DP-033 D3: a scope-filtered, streamed export, delivered as a URL rather
// than a network call this screen makes itself. `buildExportUrl`
// (`./download/buildExportUrl.ts`) is the actual deliverable — correct
// query-string construction against the shape the batch plan's §신규 API
// fixes: `GET /export/raw?source_id&from&to&key_prefix&format=jsonl|csv` and
// `GET /export/results?...&format=csv` (results is CSV-only — the plan's own
// text: "정규화 결과는 CSV 평탄화"). No fetch happens here; the operator opens
// the link or copies the curl line. M6 serves the route.

import {
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
import { MOCK_SOURCE_OPTIONS } from "../mocks/sources";
import type { ExportFormat, ExportKind } from "./download/buildExportUrl";
import { buildExportUrl, curlLine } from "./download/buildExportUrl";

export function DownloadScreen(): JSX.Element {
  const [kind, setKind] = useState<ExportKind>("raw");
  const [sourceId, setSourceId] = useState(MOCK_SOURCE_OPTIONS[0]?.sourceId ?? "");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [keyPrefix, setKeyPrefix] = useState("");
  const [format, setFormat] = useState<ExportFormat>("jsonl");

  function onKindChange(next: ExportKind): void {
    setKind(next);
    if (next === "results") {
      // Not a UI-only nicety: /export/results has no JSONL option in the
      // plan's own fixed shape, so the state itself follows the kind.
      setFormat("csv");
    }
  }

  const effectiveFormat: ExportFormat = kind === "results" ? "csv" : format;
  const url = buildExportUrl(apiBase(), { sourceId, from, to, keyPrefix, format: effectiveFormat, kind });

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Downloads
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        No request is sent from this screen — it only builds a scope-filtered, streamable export
        URL (DP-033 D3) for the operator to open or curl directly. M6 serves the route.
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack spacing={2}>
          <RadioGroup row value={kind} onChange={(event) => onKindChange(event.target.value as ExportKind)}>
            <FormControlLabel value="raw" control={<Radio />} label="Raw" />
            <FormControlLabel value="results" control={<Radio />} label="Normalized results" />
          </RadioGroup>

          <TextField
            select
            size="small"
            label="source"
            value={sourceId}
            onChange={(event) => setSourceId(event.target.value)}
            sx={{ maxWidth: 260 }}
          >
            {MOCK_SOURCE_OPTIONS.map((option) => (
              <MenuItem key={option.sourceId} value={option.sourceId}>
                {option.label}
              </MenuItem>
            ))}
          </TextField>

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

          <RadioGroup row value={effectiveFormat} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
            <FormControlLabel value="jsonl" control={<Radio />} label="JSONL" disabled={kind === "results"} />
            <FormControlLabel value="csv" control={<Radio />} label="CSV" />
          </RadioGroup>
          {kind === "results" ? (
            <Typography variant="body2" color="text.secondary">
              Normalized results export as CSV only (flattened) — JSONL applies to Raw exports.
            </Typography>
          ) : null}
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
