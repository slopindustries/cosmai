import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RawItemPage } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { DataBrowserScreen } from "../DataBrowserScreen";

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

const PAGE: RawItemPage = {
  source_id: "naver-blog-main",
  offset: 0,
  limit: 50,
  returned: 2,
  matched: 2,
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

describe("DataBrowserScreen", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(200, PAGE))),
    );
  });

  it("loads the first page of raw items for the selected source with offset/limit in the request", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText("post-1")).toBeInTheDocument());

    const calledUrl = String(fetchMock().mock.calls[0]?.[0]);
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
