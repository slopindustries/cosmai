import type { JSX } from "react";

import { PlaceholderScreen } from "./PlaceholderScreen";

/** DP-033 D1/D2: paginated Raw items, payload rendered as plain text only. */
export function DataBrowserScreen(): JSX.Element {
  return (
    <PlaceholderScreen
      title="Data Browser"
      note="Built against M2's raw item pagination route in batch 5c. DP-033 D2 requires the payload preview to render as plain text only, never interpreted markup — a payload containing <script> must be shown as text, not executed."
    />
  );
}
