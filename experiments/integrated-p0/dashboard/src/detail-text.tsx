// Render the job-detail screen under Node and print the text a reader would see.
//
// **Why this exists.** SEC-004's Action step 3 requires the dashboard job-detail
// screen to be read and every marker searched for, and step 4 requires a screenshot.
// A screenshot needs a browser driver, and DP-006 D6 puts the dependency floor at
// Vite, React, TypeScript, and `fetch` — so a driver is not available and adopting
// one to satisfy a search is the wrong trade. What the search actually needs is the
// text of the rendered screen, and `react-dom/server` already in the tree produces
// exactly that from the same components the browser mounts.
//
// **What it is not.** It is not a screenshot and does not replace one. It cannot
// catch a value hidden by CSS, revealed on hover, or present in an attribute a
// reader never sees; the tag stripping below removes attributes deliberately, so a
// marker that leaked into a `title=` would not be found. The manual screenshot
// procedure in `README.md` is the part a human still performs, and SEC-004's Result
// section states which half was executed how.
//
// **Contract.** One JSON document on standard input:
//
//     {"job": <GET /jobs/{id}>,
//      "attempts": <GET /jobs/{id}/attempts[?debug=protected]>,
//      "retry": <POST /jobs/{id}/retry body> | null}
//
// Out: the visible text of the screen those three would produce, on standard output.
// Nothing is fetched and nothing is assumed — the caller supplies real API responses.

import { renderToStaticMarkup } from "react-dom/server";
import type { AttemptPage, Job, RetryOutcome } from "./api";
import { JobDetailView } from "./view";

interface Input {
  job: Job;
  attempts: AttemptPage;
  retry?: RetryOutcome | null;
}

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

export function renderJobDetail(input: Input): string {
  return visibleText(
    renderToStaticMarkup(
      <JobDetailView
        job={input.job}
        attempts={input.attempts}
        retry={input.retry ?? null}
        onAskProtected={noop}
        onRetry={noop}
        busy={false}
      />,
    ),
  );
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
  console.log(renderJobDetail(given as Input));
}

// Not a top-level `await`: the build target this project's browser bundle uses does
// not allow one, and there is no reason to configure a second target for one line.
main().catch((problem: unknown) => {
  console.error(problem);
  process.exit(1);
});
