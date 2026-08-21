import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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

  it("switches the path and forces format=csv for normalized results, regardless of the requested format", () => {
    const url = buildExportUrl(BASE, { ...RAW_FILTERS, kind: "results", format: "jsonl" });

    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/export/results");
    expect(parsed.searchParams.get("format")).toBe("csv");
  });
});

describe("DownloadScreen", () => {
  it("defaults to a raw/jsonl URL with only source_id and format set", () => {
    render(<DownloadScreen />);

    const shown = screen.getByTestId("export-url").textContent ?? "";
    const parsed = new URL(shown);
    expect(parsed.pathname).toBe("/export/raw");
    expect(parsed.searchParams.get("format")).toBe("jsonl");
    expect(parsed.searchParams.has("from")).toBe(false);
    expect(parsed.searchParams.has("to")).toBe(false);
    expect(parsed.searchParams.has("key_prefix")).toBe(false);
  });

  it("reflects typed from/to/prefix filters in the export URL", async () => {
    const user = userEvent.setup();
    render(<DownloadScreen />);

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
    render(<DownloadScreen />);

    await user.click(screen.getByRole("radio", { name: "CSV" }));

    const parsed = new URL(screen.getByTestId("export-url").textContent ?? "");
    expect(parsed.searchParams.get("format")).toBe("csv");
  });

  it("switching to normalized results changes the path and forces CSV", async () => {
    const user = userEvent.setup();
    render(<DownloadScreen />);

    await user.click(screen.getByRole("radio", { name: "Normalized results" }));

    const parsed = new URL(screen.getByTestId("export-url").textContent ?? "");
    expect(parsed.pathname).toBe("/export/results");
    expect(parsed.searchParams.get("format")).toBe("csv");
    expect(screen.getByRole("radio", { name: "JSONL" })).toBeDisabled();
  });

  it("the download link and the curl line both carry the same URL", () => {
    render(<DownloadScreen />);

    const shown = screen.getByTestId("export-url").textContent ?? "";
    expect(screen.getByTestId("download-link")).toHaveAttribute("href", shown);
    expect(screen.getByTestId("export-curl").textContent ?? "").toContain(shown);
  });
});
