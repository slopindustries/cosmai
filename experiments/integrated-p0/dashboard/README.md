# P0-A operator dashboard

Three screens over the operator API. Disposable, like everything else under `experiments/integrated-p0/` — [DP-001](../../../docs/decisions/DP-001-p0-lifecycle.md) prohibits any of this becoming a P1 runtime or package dependency, and the P0-B artifact disposition register decides its fate.

This is instrumentation, not a preview of a product surface. [Project State](../../../docs/project-state.md) puts it that way: *"Dashboard control, logs, metrics, and debugging evidence are part of P0 instrumentation."*

## Running it

```sh
# 1. the database and the API, from the repository root
./scripts/with-database.sh uv run python -m platform_core.api

# 2. this dashboard, in another shell
cd experiments/integrated-p0/dashboard
npm install
npm run dev
```

The API must be up first; the dashboard has no data of its own. Requests go to the API through Vite's dev proxy, so the browser talks to the dev server and the dev server talks to loopback. Nothing here holds a remote address, which is what keeps `SEC-002`'s loopback boundary from being undone by a frontend default.

```sh
npm run build      # tsc --noEmit, then vite build
npm run typecheck  # types only
npm run text       # render the detail screen to text — see below
```

## Why the dependency list is this short

React, react-dom, TypeScript, Vite. That is the whole list, and [DP-006](../../../docs/decisions/DP-006-p0a-platform-foundation.md) D6 is why:

> DP-002's `[결정]` "Dashboard language and UI foundation: React with TypeScript" is unchanged and remains in force. MUI, TanStack Query, and React Router are not adopted in P0-A.

A component library, a fetching cache, and a router answer problems three screens do not have. They stay available for P0-B, where a real operator flow may need them.

## ⚠️ The boundary guard does not read this directory

`tests/environment/test_p0a_boundary_guard.py` parses `.py` with `ast` and `.sql` after stripping comments. **`.ts` and `.tsx` are checked by file and directory name only.** An identifier inside a component is invisible to it.

So the P0-A vocabulary boundary is held here by discipline, and the substitutions below are fixed rather than left to taste. `raw` in particular is the standard idiom of a debug view — "show raw payload" is what anyone would reach for — which is exactly why it is listed.

| Wanted | Use instead |
|---|---|
| `raw payload`, `RawPayload`, "Show raw" | `payload`, `PayloadPanel`, "Show payload" |
| `records`, `RecordsTable` | `rows`, `JobTable` |
| `source` meaning where data came from | `endpoint`, or leave it out |
| `observation`, `Observation` | there is no reason to need this |

Also forbidden, as everywhere in P0-A: `collector`, `importer`, `snapshot`, `manifest`, `normaliz*`, `provider`, `lineage`.

**Type names are derived from API response fields, never invented.** The API is Python and is guarded; its fields come from a SQL schema that is also guarded. Inheriting the names of data shapes leaves no route for domain vocabulary to enter, and only presentational names — `Badge`, `Table`, `Panel` — are free.

Check with:

```sh
grep -rniE 'raw|records|observation|snapshot|normaliz|collector|importer|lineage|provider' src/
```

Extending the guard to TypeScript was considered and deliberately not done. A Python-side regex scanner for TS would have to treat `//`, `/* */`, JSDoc, template literals, and JSX text as prose, and the SQL detector in that same guard already misfired once for exactly this reason — a docstring containing the English word "from" was parsed as a statement. Narrowing the exposure by fixing the vocabulary was the cheaper answer. The gap is recorded in the P0-A gate rather than hidden.

## The screens

| Screen | Reads | Serves |
|---|---|---|
| Job list | `GET /jobs`, with a state filter | finding the failure |
| Job detail | `GET /jobs/{id}`, `GET /jobs/{id}/attempts` | `OPS-001`'s six questions, and `SEC-004`'s redaction check |
| — retry, inside detail | `POST /jobs/{id}/retry` | `OPS-002`, including a refusal that names the current and the required state |

Three, fixed by DP-006 D6 and by the plan's descope ladder. A fourth screen is a decision, not an addition.

Protected debug detail is never on the default screen. When an attempt has some, the screen says so and offers the explicit action that asks for it — `?debug=protected` — and even there the redaction rules still apply, because `SEC-004` says protected does not mean unredacted.

## `npm run text`

Renders the detail screen to plain text through Vite's SSR build. It exists so that `SEC-004`'s screen assertions can run in `pytest` without adding a browser automation dependency to a project whose entire frontend is four packages. It is the same component tree the browser renders, so a marker absent from the text is absent from the screen — but it is text, not pixels, and the scenario's `Result` section records that distinction rather than glossing it.
