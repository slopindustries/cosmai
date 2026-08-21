// DP-033 D3: pure export-URL construction, kept out of DownloadScreen.tsx so
// that file exports components only (oxlint's react/only-export-components —
// mixing a component export with plain function/constant exports in one file
// breaks Fast Refresh).
//
// Real as of batch 5-final: reconciled against `apps/domain/api.py`'s actual
// `export_raw`/`export_results` route signatures (merged from `dev`), not
// the plan's prose summary.
//
// **Mismatch found and fixed.** The plan's own text ("정규화 결과는 CSV
// 평탄화") and batch 5d's first version both read `/export/results` as
// CSV-only and forced `format=csv` whenever `kind: "results"` was selected.
// Reading `apps/domain/api.py`'s `export_results` directly shows the *real*
// signature is identical to `export_raw`'s:
// `format: Annotated[Literal["jsonl", "csv"], _FORMAT_QUERY] = "jsonl"` —
// both routes accept `jsonl` or `csv`, defaulting to `jsonl`, with no
// kind-specific restriction anywhere in `domain.api` or `domain.export`
// (`stream_results` takes the same `fmt: str` `stream_raw` does and branches
// on it identically). Fixed by matching the backend: `kind: "results"` no
// longer forces a format: any operator format choice reaches the URL alongside
// any kind choice.

export type ExportKind = "raw" | "results";
export type ExportFormat = "jsonl" | "csv";

export interface ExportFilters {
  sourceId: string;
  from: string;
  to: string;
  keyPrefix: string;
  format: ExportFormat;
  kind: ExportKind;
}

/**
 * Builds the export URL. An empty filter (`""`) is omitted from the query
 * string entirely rather than sent as an empty param — "empty range omits
 * params" is a property of this function, not of what the operator typed.
 * `format` passes straight through regardless of `kind` — both
 * `/export/raw` and `/export/results` accept `jsonl` or `csv` identically
 * (see this file's header note on the mismatch this corrects).
 */
export function buildExportUrl(base: string, filters: ExportFilters): string {
  const path = filters.kind === "raw" ? "/export/raw" : "/export/results";
  const query = new URLSearchParams();
  if (filters.sourceId !== "") {
    query.set("source_id", filters.sourceId);
  }
  if (filters.from !== "") {
    query.set("from", filters.from);
  }
  if (filters.to !== "") {
    query.set("to", filters.to);
  }
  if (filters.keyPrefix !== "") {
    query.set("key_prefix", filters.keyPrefix);
  }
  query.set("format", filters.format);
  return `${base}${path}?${query.toString()}`;
}

export function curlLine(url: string): string {
  return `curl -o export.download '${url}'`;
}
