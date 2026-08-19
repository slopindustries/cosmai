// Render the domain screen under Node and print the markup and the visible text.
//
// The same mechanism `detail-text.tsx` uses, for the same reason and with the same
// two forms: what a browser is handed is markup, and the text is that markup with
// every tag removed. A value carried in an attribute is in the markup and gone from
// the text, and it has still been delivered — so an assertion searches the markup and
// a person reads the text.
//
// **What this one is for.** The operator loop is four acts across three tables, and
// the claim "the dashboard actually works" is only checkable if the screen can be
// produced from real API responses and read. This takes the four responses a real run
// produces and prints the screen they make, so a pytest assertion reads the same
// screen a browser would paint rather than a description of it.
//
// **Contract.** One JSON document on standard input:
//
//     {"sources": <GET /sources>,
//      "raw": {<source_id>: <GET /sources/{id}/raw>},
//      "snapshots": <GET /snapshots>,
//      "results": <GET /snapshots/{id}/results>,
//      "open_source": <source_id> | null,
//      "open_snapshot": <snapshot_id> | null}
//
// Out, on standard output, the same two delimited sections `detail-text.tsx` prints.

import type { JSX } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { NormalizedResult, RawSummary, Snapshot, Source } from "./api";
import { ResultTable, SnapshotTable, SourceDetail, SourceTable } from "./domain-view";
import { MARKUP_SECTION, VISIBLE_SECTION, visibleText } from "./screen-text";

interface Input {
  sources: { sources: Source[] };
  raw: Record<string, RawSummary>;
  snapshots: { snapshots: Snapshot[] };
  results: { results: NormalizedResult[] };
  open_source?: string | null;
  open_snapshot?: string | null;
}

/**
 * The screen, with every control inert.
 *
 * The handlers are no-ops because this renders once and is never clicked. What the
 * assertions care about is that the controls are *present and in the right state* —
 * a `seal snapshot` button that is disabled for a disabled source, a normalize button
 * that is disabled for a snapshot that no longer verifies — and that is in the markup
 * whether or not anything could click it.
 */
function screen(input: Input): JSX.Element {
  const sources = input.sources.sources;
  const openSource = input.open_source ?? null;
  const open = sources.find((source) => source.source_id === openSource) ?? null;
  const nothing = (): void => undefined;
  return (
    <div className="app">
      <SourceTable
        sources={sources}
        raw={input.raw}
        selectedId={openSource}
        onSelect={nothing}
        onCollect={nothing}
        onImport={nothing}
        onSeal={nothing}
      />
      {open === null ? null : <SourceDetail source={open} />}
      <SnapshotTable
        snapshots={input.snapshots.snapshots}
        normalizers={sources.filter((source) => source.kind === "normalizer")}
        selectedId={input.open_snapshot ?? null}
        onSelect={nothing}
        onNormalize={nothing}
      />
      <ResultTable results={input.results.results} />
    </div>
  );
}

export function renderDomainMarkup(input: Input): string {
  return renderToStaticMarkup(screen(input));
}

export function renderDomain(input: Input): string {
  return visibleText(renderDomainMarkup(input));
}

async function readStdin(): Promise<string> {
  const decoder = new TextDecoder();
  let text = "";
  for await (const chunk of process.stdin) {
    text += decoder.decode(chunk, { stream: true });
  }
  return text + decoder.decode();
}

async function main(): Promise<void> {
  const given: unknown = JSON.parse(await readStdin());
  if (typeof given !== "object" || given === null) {
    throw new Error("expected a JSON object with sources, raw, snapshots, and results");
  }
  const markup = renderDomainMarkup(given as Input);
  console.log(VISIBLE_SECTION);
  console.log(visibleText(markup));
  console.log(MARKUP_SECTION);
  console.log(markup);
}

main().catch((problem: unknown) => {
  console.error(problem);
  process.exit(1);
});
