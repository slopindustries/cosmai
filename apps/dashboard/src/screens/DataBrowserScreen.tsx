// DP-033 D1/D2: a source selector, a paginated Raw item table, and a payload
// detail pane. **DP-033 D2's control lives here**: the payload preview and
// the detail pane render as plain text only — a payload is a JSX text child,
// which React always escapes, never as `dangerouslySetInnerHTML` or any
// other path that would let a payload be parsed as markup. A payload
// containing `<script>` must show up as the literal characters `<script>`,
// never as an executed or even parsed element — see
// `__tests__/DataBrowserScreen.test.tsx`'s dedicated test.
//
// Real as of batch 5-final: both the raw-item page (`GET
// /sources/{id}/raw/items?offset&limit`) and the source selector's options
// (`GET /sources`) come from `apps/domain/api.py`, merged from `dev`.
//
// **Mismatch found and fixed reconciling against the real route:** the page
// envelope has no `matched` field (`apps/domain/api.py`'s `read_raw_items`
// returns `returned` only, unlike `platform_core.api.app`'s `GET /jobs`,
// which does). Pagination below can no longer disable "Next" against a known
// total; it disables when `returned < limit`, the only signal a caller
// without `matched` has for "this was the last page."

import {
  Alert,
  Box,
  Button,
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

import { useRawItemsQuery, useSourcesQuery } from "../api/queries";

const LIMIT = 50;

function preview(payload: string, maxLength = 80): string {
  return payload.length > maxLength ? `${payload.slice(0, maxLength)}…` : payload;
}

export function DataBrowserScreen(): JSX.Element {
  const sourcesQuery = useSourcesQuery();
  const sources = sourcesQuery.data?.sources ?? [];

  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const sourceId = selectedSourceId ?? sources[0]?.source_id ?? "";
  const [offset, setOffset] = useState(0);
  const [selectedItemKey, setSelectedItemKey] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useRawItemsQuery(sourceId, offset, LIMIT);
  const selectedItem = data?.items.find((item) => item.item_key === selectedItemKey) ?? null;

  function onSourceChange(next: string): void {
    setSelectedSourceId(next);
    setOffset(0);
    setSelectedItemKey(null);
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Data Browser
      </Typography>

      {sourcesQuery.isError ? (
        <Alert severity="error">
          {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : String(sourcesQuery.error)}
        </Alert>
      ) : null}
      {sourcesQuery.data && sources.length === 0 ? (
        <Alert severity="info">No source is registered yet.</Alert>
      ) : null}

      {sources.length > 0 ? (
        <TextField
          select
          size="small"
          label="source"
          value={sourceId}
          onChange={(event) => onSourceChange(event.target.value)}
          sx={{ mb: 2, minWidth: 220 }}
        >
          {sources.map((option) => (
            <MenuItem key={option.source_id} value={option.source_id}>
              {option.source_id} ({option.kind})
            </MenuItem>
          ))}
        </TextField>
      ) : null}

      {isLoading ? <CircularProgress size={24} /> : null}
      {isError ? (
        <Alert severity="error">{error instanceof Error ? error.message : String(error)}</Alert>
      ) : null}

      {data ? (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            showing {data.returned} item{data.returned === 1 ? "" : "s"}, starting at offset{" "}
            {data.offset}
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>item key</TableCell>
                  <TableCell>seq</TableCell>
                  <TableCell>emitted at</TableCell>
                  <TableCell>content type</TableCell>
                  <TableCell>payload preview</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5}>No item collected for this source yet.</TableCell>
                  </TableRow>
                ) : (
                  data.items.map((item) => (
                    <TableRow
                      key={item.item_key}
                      hover
                      selected={item.item_key === selectedItemKey}
                      onClick={() => setSelectedItemKey(item.item_key)}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell>{item.item_key}</TableCell>
                      <TableCell>{item.seq}</TableCell>
                      <TableCell>{item.emitted_at}</TableCell>
                      <TableCell>{item.content_type}</TableCell>
                      {/* A preview substring of the same plain-text value the
                          detail pane below renders in full — sliced, never
                          parsed, so a tag in the payload still reads as text
                          here too. */}
                      <TableCell>{preview(item.payload)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
            <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
              Previous
            </Button>
            <Button disabled={data.returned < LIMIT} onClick={() => setOffset(offset + LIMIT)}>
              Next
            </Button>
          </Stack>
        </>
      ) : null}

      {selectedItem ? (
        <Paper sx={{ p: 2, mt: 2 }} data-testid="payload-detail">
          <Typography variant="subtitle1" gutterBottom>
            payload — {selectedItem.item_key}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Rendered as plain text only (DP-033 D2) — never interpreted as HTML or Markdown.
          </Typography>
          <Box
            component="pre"
            data-testid="payload-text"
            sx={{ fontSize: 12, m: 0, whiteSpace: "pre-wrap", overflowX: "auto" }}
          >
            {selectedItem.payload}
          </Box>
        </Paper>
      ) : null}
    </Box>
  );
}
