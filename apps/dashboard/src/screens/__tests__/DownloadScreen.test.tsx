import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Source, SourceList } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { DownloadScreen } from "../DownloadScreen";
import type { ExportFilters } from "../download/buildExportUrl";
import { buildExportUrl } from "../download/buildExportUrl";

const BASE = "http://127.0.0.1:8000";

const RAW_FILTERS: ExportFilters = {
  sourceId: "naver-blog-main",
  from: "",
  to: "",
  keyPrefix: "",
  format: "jsonl",
  kind: "raw",
};

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

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DownloadScreen />
    </QueryClientProvider>,
  );
}

describe("buildExportUrl", () => {
  it("maps each filter to its query param", () => {
    const url = buildExportUrl(BASE, {
      sourceId: "naver-blog-main",
      from: "2026-01-01",
      to: "2026-02-01",
      keyPrefix: "post-",
      format: "csv",
      kind: "raw",
    });

    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/export/raw");
    expect(parsed.searchParams.get("source_id")).toBe("naver-blog-main");
    expect(parsed.searchParams.get("from")).toBe("2026-01-01");
    expect(parsed.searchParams.get("to")).toBe("2026-02-01");
    expect(parsed.searchParams.get("key_prefix")).toBe("post-");
    expect(parsed.searchParams.get("format")).toBe("csv");
  });

  it("omits from/to/key_prefix entirely when they are empty, rather than sending them empty", () => {
    const url = buildExportUrl(BASE, RAW_FILTERS);

    const parsed = new URL(url);
    expect(parsed.searchParams.has("from")).toBe(false);
    expect(parsed.searchParams.has("to")).toBe(false);
    expect(parsed.searchParams.has("key_prefix")).toBe(false);
    expect(parsed.searchParams.get("source_id")).toBe("naver-blog-main");
  });

  it("toggling format changes the format param", () => {
    const jsonl = buildExportUrl(BASE, { ...RAW_FILTERS, format: "jsonl" });
    const csv = buildExportUrl(BASE, { ...RAW_FILTERS, format: "csv" });

    expect(new URL(jsonl).searchParams.get("format")).toBe("jsonl");
    expect(new URL(csv).searchParams.get("format")).toBe("csv");
  });

  it("switches the path for normalized results without touching the requested format — /export/results accepts jsonl or csv identically to /export/raw", () => {
    const jsonl = buildExportUrl(BASE, { ...RAW_FILTERS, kind: "results", format: "jsonl" });
    const csv = buildExportUrl(BASE, { ...RAW_FILTERS, kind: "results", format: "csv" });

    expect(new URL(jsonl).pathname).toBe("/export/results");
    expect(new URL(jsonl).searchParams.get("format")).toBe("jsonl");
    expect(new URL(csv).searchParams.get("format")).toBe("csv");
  });
});

describe("DownloadScreen", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(200, SOURCES))),
    );
  });

  it("defaults to a raw/jsonl URL with only source_id and format set", async () => {
    renderScreen();

    await waitFor(() => {
      const shown = screen.getByTestId("export-url").textContent ?? "";
      const parsed = new URL(shown);
      expect(parsed.pathname).toBe("/export/raw");
      expect(parsed.searchParams.get("format")).toBe("jsonl");
      expect(parsed.searchParams.get("source_id")).toBe("naver-blog-main");
      expect(parsed.searchParams.has("from")).toBe(false);
      expect(parsed.searchParams.has("to")).toBe(false);
      expect(parsed.searchParams.has("key_prefix")).toBe(false);
    });
  });

  it("reflects typed from/to/prefix filters in the export URL", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByLabelText("from")).toBeInTheDocument());

    await user.type(screen.getByLabelText("from"), "2026-01-01");
    await user.type(screen.getByLabelText("to"), "2026-02-01");
    await user.type(screen.getByLabelText("item_key prefix"), "post-");

    const parsed = new URL(screen.getByTestId("export-url").textContent ?? "");
    expect(parsed.searchParams.get("from")).toBe("2026-01-01");
    expect(parsed.searchParams.get("to")).toBe("2026-02-01");
    expect(parsed.searchParams.get("key_prefix")).toBe("post-");
  });

  it("clicking the CSV radio toggles the format param for a raw export", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByRole("radio", { name: "CSV" })).toBeInTheDocument());

    await user.click(screen.getByRole("radio", { name: "CSV" }));

    const parsed = new URL(screen.getByTestId("export-url").textContent ?? "");
    expect(parsed.searchParams.get("format")).toBe("csv");
  });

  it("switching to normalized results changes the path but leaves the format choice (JSONL) untouched and enabled", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByRole("radio", { name: "Normalized results" })).toBeInTheDocument());

    await user.click(screen.getByRole("radio", { name: "Normalized results" }));

    const parsed = new URL(screen.getByTestId("export-url").textContent ?? "");
    expect(parsed.pathname).toBe("/export/results");
    expect(parsed.searchParams.get("format")).toBe("jsonl");
    expect(screen.getByRole("radio", { name: "JSONL" })).toBeEnabled();
  });

  it("the download link and the curl line both carry the same URL", async () => {
    renderScreen();

    await waitFor(() => {
      const shown = screen.getByTestId("export-url").textContent ?? "";
      expect(screen.getByTestId("download-link")).toHaveAttribute("href", shown);
      expect(screen.getByTestId("export-curl").textContent ?? "").toContain(shown);
    });
  });
});
