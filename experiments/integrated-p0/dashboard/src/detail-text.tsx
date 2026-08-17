// Render the job-detail screen under Node and print both the markup a browser would
// be handed and the text a reader would see.
//
// **Why this exists.** SEC-004's Action step 3 requires the dashboard job-detail
// screen to be read and every marker searched for, and step 4 requires a screenshot.
// A screenshot needs a browser driver, and DP-006 D6 puts the dependency floor at
// Vite, React, TypeScript, and `fetch` — so a driver is not available and adopting
// one to satisfy a search is the wrong trade. What the search actually needs is the
// rendered screen, and `react-dom/server` already in the tree produces it from the
// same components the browser mounts.
//
// **Two forms, and the markup is the stronger one to search.** What a browser is
// handed is markup; the text is that markup with every tag removed. A value carried
// in an attribute, or inside an element CSS would hide, is in the markup and gone
// from the text — and it has still been delivered, which is the thing SEC-004
// forbids. So both are printed: the text is what a person reads in the captured
// evidence, and the markup is what an assertion should search.
//
// **What it is not.** Neither form is a screenshot. Now that the markup is searched,
// what stays uncovered is not attributes but images: a marker drawn into a canvas,
// a bitmap, or a font glyph is in the pixels and in no string here. A screenshot is
// the weaker of the two checks — it shows only what was painted, while the markup
// carries everything that was delivered, including what CSS hid and what only an
// attribute holds. The manual capture procedure in `README.md` is the part a human
// still performs, and SEC-004's Result section states which half was executed how.
//
// **Contract.** One JSON document on standard input:
//
//     {"job": <GET /jobs/{id}>,
//      "attempts": <GET /jobs/{id}/attempts[?debug=protected]>,
//      "retry": <POST /jobs/{id}/retry body> | null}
//
// Out, on standard output, two delimited sections of the screen those three produce:
//
//     --- VISIBLE ---
//     <the visible text>
//     --- MARKUP ---
//     <the markup, exactly as `react-dom/server` produced it>
//
// Nothing is fetched and nothing is assumed — the caller supplies real API responses.

import type { JSX } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AttemptPage, Job, RetryOutcome } from "./api";
import { JobDetailView } from "./view";

interface Input {
  job: Job;
  attempts: AttemptPage;
  retry?: RetryOutcome | null;
}

// The two section delimiters, exported so that a caller which splits the output
// reads them from here instead of restating them. A restated copy would go on
// looking for a delimiter this file had stopped printing.
export const VISIBLE_SECTION = "--- VISIBLE ---";
export const MARKUP_SECTION = "--- MARKUP ---";

/** Entities `renderToStaticMarkup` introduces, undone so a search sees the text. */
const ENTITIES: ReadonlyArray<readonly [RegExp, string]> = [
  [/&lt;/g, "<"],
  [/&gt;/g, ">"],
  [/&quot;/g, '"'],
  [/&#x27;/g, "'"],
  [/&#39;/g, "'"],
  [/&nbsp;/g, " "],
  [/&amp;/g, "&"],
];

/**
 * The markup reduced to what a reader sees.
 *
 * Each tag becomes a newline rather than nothing, so two neighbouring cells cannot
 * join into a third string that was never on screen. `&amp;` is undone last, so a
 * literal `&amp;lt;` in the data does not turn into `<`.
 */
export function visibleText(markup: string): string {
  let text = markup.replace(/<[^>]*>/g, "\n");
  for (const [pattern, character] of ENTITIES) {
    text = text.replace(pattern, character);
  }
  return text
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.trim() !== "")
    .join("\n");
}

function noop(): void {
  // The screen's two actions. This entry renders one state of the screen; it never
  // interacts with it, and a handler that did anything would be pretending to.
}

/** The one element tree both outputs are taken from, so the two cannot disagree. */
function screen(input: Input): JSX.Element {
  return (
    <JobDetailView
      job={input.job}
      attempts={input.attempts}
      retry={input.retry ?? null}
      onAskProtected={noop}
      onRetry={noop}
      busy={false}
    />
  );
}

/** The markup a browser would be handed, with nothing removed from it. */
export function renderJobDetailMarkup(input: Input): string {
  return renderToStaticMarkup(screen(input));
}

export function renderJobDetail(input: Input): string {
  return visibleText(renderJobDetailMarkup(input));
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
    throw new Error("expected a JSON object with job, attempts, and retry");
  }
  const markup = renderJobDetailMarkup(given as Input);
  console.log(VISIBLE_SECTION);
  console.log(visibleText(markup));
  console.log(MARKUP_SECTION);
  console.log(markup);
}

// Not a top-level `await`: the build target this project's browser bundle uses does
// not allow one, and there is no reason to configure a second target for one line.
main().catch((problem: unknown) => {
  console.error(problem);
  process.exit(1);
});
