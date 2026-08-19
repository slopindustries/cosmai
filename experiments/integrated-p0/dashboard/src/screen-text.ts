// Turning rendered markup into the text a reader sees, and the two section names the
// render entries print.
//
// **Why this is its own module.** `detail-text.tsx` and `domain-text.tsx` are both
// *entries*: each reads standard input and prints, so importing either for its
// helpers runs its `main`. Extracted here on 2026-08-19 when the second entry was
// added and did exactly that — the domain screen printed a job-detail traceback,
// because importing the module to reuse `visibleText` also started its reader.
//
// Nothing in this file imports React or touches a screen, so both entries can share
// it and a test can import it without either entry running.

/** The two section delimiters, so a caller which splits the output reads them here. */
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
