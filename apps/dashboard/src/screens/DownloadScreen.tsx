import type { JSX } from "react";

import { PlaceholderScreen } from "./PlaceholderScreen";

/** DP-033 D3: scope-filtered, streamed export links against `/export/*` (M6). */
export function DownloadScreen(): JSX.Element {
  return (
    <PlaceholderScreen
      title="Downloads"
      note="Built against M6's /export/raw and /export/results routes in batch 5d: a scope form (source, period, item_key prefix) that produces a streaming JSONL or CSV download link."
    />
  );
}
