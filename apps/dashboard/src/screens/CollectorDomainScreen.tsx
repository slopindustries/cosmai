import type { JSX } from "react";

import { PlaceholderScreen } from "./PlaceholderScreen";

/** DP-033 D1: one collector per domain — status, schedule, config, job history. */
export function CollectorDomainScreen(): JSX.Element {
  return (
    <PlaceholderScreen
      title="Collectors"
      note="Built against M2's domain API in batch 5c: one screen per domain with status, a config form generated from the add-on manifest's config schema, credential entry (batch 5b), job history, and last successful collection."
    />
  );
}
