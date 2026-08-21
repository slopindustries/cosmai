// A hand-rolled `fetch` stand-in for component tests. No msw: the API surface
// under test is small (a handful of GET/POST paths) and a hand mock keeps the
// request the test made — method, URL, query string — directly inspectable from
// `vi.fn()`'s own call log, which is what several assertions below read.

export function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}
