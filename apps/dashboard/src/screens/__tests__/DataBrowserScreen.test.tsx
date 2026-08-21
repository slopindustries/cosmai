import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RawItemPage, Source, SourceList } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { DataBrowserScreen } from "../DataBrowserScreen";

const SOURCE: Source = {
  source_id: "naver-blog-main",
  addon_id: "collector.naver.blog",
  addon_version: "0.1.0",
  kind: "collector",
  config: {},
  config_schema_version: "1",
  credential_ref: null,
  outbound_profile: null,
  input_profile: null,
  data_class: "local",
  enabled: true,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

const SOURCES: SourceList = { sources: [SOURCE] };

const PLAIN_ITEM = {
  item_key: "post-1",
  seq: 1,
  emitted_at: "2026-08-21T00:00:00Z",
  content_type: "application/json",
  payload: '{"title": "hello"}',
};

const RAW_SCRIPT_PAYLOAD = "<script>alert(1)</script><b>x</b>";

const MARKUP_ITEM = {
  item_key: "post-2",
  seq: 2,
  emitted_at: "2026-08-21T00:05:00Z",
  content_type: "text/html",
  payload: RAW_SCRIPT_PAYLOAD,
};

// No `matched` field — `apps/domain/api.py`'s `read_raw_items` returns
// `returned` only. `returned: 2` with `limit: 50` means "Next" reads as the
// last page (`returned < limit`).
const PAGE: RawItemPage = {
  source_id: "naver-blog-main",
  offset: 0,
  limit: 50,
  returned: 2,
  items: [PLAIN_ITEM, MARKUP_ITEM],
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DataBrowserScreen />
    </QueryClientProvider>,
  );
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return fetch as unknown as ReturnType<typeof vi.fn>;
}

function installFetchMock(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/raw/items")) {
        return Promise.resolve(jsonResponse(200, PAGE));
      }
      return Promise.resolve(jsonResponse(200, SOURCES));
    }),
  );
}

describe("DataBrowserScreen", () => {
  beforeEach(() => {
    installFetchMock();
  });

  it("loads the first page of raw items for the selected source with offset/limit in the request", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText("post-1")).toBeInTheDocument());

    const rawItemsCall = fetchMock().mock.calls.find((call) => String(call[0]).includes("/raw/items"));
    const calledUrl = String(rawItemsCall?.[0]);
    expect(calledUrl).toContain("/sources/naver-blog-main/raw/items?");
    expect(calledUrl).toContain("offset=0");
    expect(calledUrl).toContain("limit=50");
  });

  it("selecting an item shows its payload in the detail pane", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByText("post-1")).toBeInTheDocument());

    await user.click(screen.getByText("post-1"));

    const detail = await screen.findByTestId("payload-detail");
    expect(within(detail).getByTestId("payload-text").textContent).toBe(PLAIN_ITEM.payload);
  });

  it("disables Next once a page returns fewer items than the limit (no `matched` field to compare against)", async () => {
    renderScreen();
    await waitFor(() => expect(screen.getByText("post-1")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("DP-033 D2: a payload containing markup renders as literal plain text, never as parsed HTML", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByText("post-2")).toBeInTheDocument());

    await user.click(screen.getByText("post-2"));

    const payloadElement = await screen.findByTestId("payload-text");

    // The exact raw string, with its angle brackets intact — proof nothing
    // stripped or transformed it.
    expect(payloadElement.textContent).toBe(RAW_SCRIPT_PAYLOAD);

    // And proof it was never parsed as markup: no <script> or <b> element
    // exists anywhere inside the payload element — React rendered the tags
    // as inert text characters, not as DOM elements.
    expect(payloadElement.querySelector("script")).toBeNull();
    expect(payloadElement.querySelector("b")).toBeNull();
    expect(payloadElement.children.length).toBe(0);
  });
});
