// Shared shell for the four DP-033 D1 screens batch 5a routes to but does not
// implement (collector-domain, data browser, downloads, normalization
// management). Batch 5c/5d build these against M2's domain API; this batch only
// fixes the navigation destination so the six-screen set (DP-033 D1) exists from
// the start rather than growing one route at a time.

import { Box, Paper, Typography } from "@mui/material";
import type { JSX } from "react";

export interface PlaceholderScreenProps {
  title: string;
  note: string;
}

export function PlaceholderScreen({ title, note }: PlaceholderScreenProps): JSX.Element {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        {title}
      </Typography>
      <Paper variant="outlined" sx={{ p: 2 }} data-testid="placeholder-panel">
        <Typography variant="body2" color="text.secondary">
          {note}
        </Typography>
      </Paper>
    </Box>
  );
}
