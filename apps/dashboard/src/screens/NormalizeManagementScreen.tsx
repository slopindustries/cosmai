import type { JSX } from "react";

import { PlaceholderScreen } from "./PlaceholderScreen";

/** DP-033 D1/D5: select snapshot, select normalizer/version, create run — management frame only. */
export function NormalizeManagementScreen(): JSX.Element {
  return (
    <PlaceholderScreen
      title="Normalization"
      note="Built against M2's snapshot/normalize routes in batch 5d: select a sealed snapshot, select a normalizer and version, create a run, and browse the version-coexisting results. Normalization stays operator-triggered (DP-033 D5)."
    />
  );
}
