import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JobPage, RawSummary, Schedule, Source, SourceList } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { CollectorDomainScreen } from "../CollectorDomainScreen";

const COLLECTOR: Source = {
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

const SOURCES: SourceList = { sources: [COLLECTOR] };

const RAW_SUMMARY: RawSummary = {
  source_id: "naver-blog-main",
  envelope_count: 3,
  item_count: 12,
  last_retrieved_at: "2026-08-20T09:00:00Z",
};

const UNSET_SCHEDULE: Schedule = {
  source_id: "naver-blog-main",
  interval_seconds: null,
  enabled: false,
  next_run_at: null,
  last_run_at: null,
};

const EMPTY_JOB_PAGE: JobPage = {
  state: null,
  limit: 100,
  offset: 0,
  returned: 0,
  matched: 0,
  jobs: [],
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CollectorDomainScreen />
    </QueryClientProvider>,
  );
}

function installFetchMock(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/raw")) {
        return Promise.resolve(jsonResponse(200, RAW_SUMMARY));
      }
      if (url.includes("/schedule")) {
        return Promise.resolve(jsonResponse(200, UNSET_SCHEDULE));
      }
      if (url.includes("/jobs")) {
        return Promise.resolve(jsonResponse(200, EMPTY_JOB_PAGE));
      }
      return Promise.resolve(jsonResponse(200, SOURCES));
    }),
  );
}

describe("CollectorDomainScreen", () => {
  beforeEach(() => {
    installFetchMock();
  });

  it("renders the status header, config form, credential section, job history, and schedule pane for the selected collector", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByTestId("status-header")).toBeInTheDocument());
    expect(screen.getByText("enabled")).toBeInTheDocument();
    expect(screen.getByLabelText(/Search query/)).toBeInTheDocument();
    expect(screen.getByLabelText("purpose")).toBeInTheDocument();
    expect(screen.getByLabelText("value")).toBeInTheDocument();
    expect(screen.getByTestId("schedule-pane")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/No job history/)).toBeInTheDocument());
  });

  it("shows a disabled 'Collect now' action with the M3-pending note, per the controller ruling", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByTestId("collect-now-button")).toBeInTheDocument());
    expect(screen.getByTestId("collect-now-button")).toBeDisabled();
    expect(screen.getByTestId("collect-disabled-note").textContent).toMatch(/add-on host/);
  });
});
