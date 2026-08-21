// DP-033 D1/D2: a source selector, a paginated Raw item table, and a payload
// detail pane. **DP-033 D2's control lives here**: the payload preview and
// the detail pane render as plain text only — a payload is a JSX text child,
// which React always escapes, never as `dangerouslySetInnerHTML` or any
// other path that would let a payload be parsed as markup. A payload
// containing `<script>` must show up as the literal characters `<script>`,
// never as an executed or even parsed element — see
// `__tests__/DataBrowserScreen.test.tsx`'s dedicated test.
//
// The read this screen makes (`GET /sources/{id}/raw/items?offset&limit`) is
// real, against the shape the M2-M7 batch plan's §신규 API fixes — no backend
// serves it yet, so this batch's tests mock it. The *source selector*'s
// options are still local mock data pending M2's `GET /sources`.

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

import { useRawItemsQuery } from "../api/queries";
import { MOCK_SOURCE_OPTIONS } from "../mocks/sources";

const LIMIT = 50;

function preview(payload: string, maxLength = 80): string {
  return payload.length > maxLength ? `${payload.slice(0, maxLength)}…` : payload;
}

export function DataBrowserScreen(): JSX.Element {
  const [sourceId, setSourceId] = useState(MOCK_SOURCE_OPTIONS[0]?.sourceId ?? "");
  const [offset, setOffset] = useState(0);
  const [selectedItemKey, setSelectedItemKey] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useRawItemsQuery(sourceId, offset, LIMIT);
  const selectedItem = data?.items.find((item) => item.item_key === selectedItemKey) ?? null;

  function onSourceChange(next: string): void {
    setSourceId(next);
    setOffset(0);
    setSelectedItemKey(null);
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Data Browser
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
            <Button disabled={offset + LIMIT >= data.matched} onClick={() => setOffset(offset + LIMIT)}>
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
