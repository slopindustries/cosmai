// DP-033 D3: pure export-URL construction, kept out of DownloadScreen.tsx so
// that file exports components only (oxlint's react/only-export-components —
// mixing a component export with plain function/constant exports in one file
// breaks Fast Refresh). Against the shape the batch plan's §신규 API fixes:
// `GET /export/raw?source_id&from&to&key_prefix&format=jsonl|csv` and
// `GET /export/results?...&format=csv` (results is CSV-only — the plan's own
// text: "정규화 결과는 CSV 평탄화").

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
 * `kind: "results"` always forces `format=csv` in the URL, regardless of
 * `filters.format`, because the plan gives `/export/results` no JSONL option.
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
  query.set("format", filters.kind === "results" ? "csv" : filters.format);
  return `${base}${path}?${query.toString()}`;
}

export function curlLine(url: string): string {
  return `curl -o export.download '${url}'`;
}
