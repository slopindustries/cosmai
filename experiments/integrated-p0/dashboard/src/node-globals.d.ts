// The one Node global this project uses, declared by hand.
//
// `@types/node` would supply it, and it is deliberately not a dependency: the only
// Node code here is `vite.config.ts` and `src/detail-text.tsx`, and between them
// they touch three members of `process`. Declaring those three keeps the
// dependency list at the floor DP-006 D6 fixes (Vite, React, TypeScript, `fetch`)
// plus the type packages for React itself. `console` needs nothing: the DOM
// library already declares it. If a third Node entry appears and needs more than
// this, adopt `@types/node` rather than extending the list indefinitely.

declare const process: {
  readonly env: Readonly<Record<string, string | undefined>>;
  readonly stdin: AsyncIterable<Uint8Array>;
  exit(code?: number): never;
};
