import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  NormalizeRunCreated,
  NormalizedResult,
  ResultList,
  Snapshot,
  SnapshotList,
  Source,
  SourceList,
} from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { NormalizeManagementScreen } from "../NormalizeManagementScreen";

const SEEDED_SNAPSHOT_ID = "22222222-1111-1111-1111-111111111111";

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

const NORMALIZER: Source = {
  ...COLLECTOR,
  source_id: "naver-blog-normalizer",
  addon_id: "normalizer.naver.blog",
  kind: "normalizer",
};

const SOURCES: SourceList = { sources: [COLLECTOR, NORMALIZER] };

const SEEDED_SNAPSHOT: Snapshot = {
  snapshot_id: SEEDED_SNAPSHOT_ID,
  source_id: "naver-blog-main",
  item_count: 42,
  manifest_sha256: "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff",
  selection: {},
  sealed_at: "2026-08-20T10:00:00Z",
  created_at: "2026-08-20T10:00:00Z",
  verifies: true,
  problems: [],
};

const SNAPSHOTS: SnapshotList = { snapshots: [SEEDED_SNAPSHOT] };

function result(overrides: Partial<NormalizedResult>): NormalizedResult {
  return {
    id: "result-id",
    snapshot_id: SEEDED_SNAPSHOT_ID,
    source_id: "naver-blog-main",
    addon_id: "normalizer.naver.blog",
    addon_version: "0.1.0",
    output_contract_version: "0.2",
    source_item_key: "post-1",
    body: { title: "hello" },
    body_sha256: "deadbeef",
    notes: {},
    created_at: "2026-08-20T11:00:00Z",
    ...overrides,
  };
}

const RESULTS: ResultList = {
  results: [
    result({ id: "r1", source_item_key: "post-1" }),
    result({
      id: "r2",
      source_item_key: "post-2",
      notes: { normalize_error: { field: "published_at", reason: "unparseable date" } },
    }),
    result({
      id: "r3",
      source_item_key: "post-1",
      addon_version: "0.2.0",
      output_contract_version: "0.3",
      body: { title: "hello", record_type: "document" },
    }),
    result({
      id: "r4",
      source_item_key: "post-2",
      addon_version: "0.2.0",
      output_contract_version: "0.3",
      body: { title: "second post", record_type: "document" },
    }),
  ],
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <NormalizeManagementScreen />
    </QueryClientProvider>,
  );
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return fetch as unknown as ReturnType<typeof vi.fn>;
}

function installFetchMock(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method === "POST" && url.includes("/normalize")) {
        const created: NormalizeRunCreated = { job_id: "job-1", snapshot_id: SEEDED_SNAPSHOT_ID };
        return Promise.resolve(jsonResponse(201, created));
      }
      if (method === "POST" && url.includes("/snapshots")) {
        return Promise.resolve(jsonResponse(201, SEEDED_SNAPSHOT));
      }
      if (url.includes("/results")) {
        return Promise.resolve(jsonResponse(200, RESULTS));
      }
      if (url.includes("/snapshots")) {
        return Promise.resolve(jsonResponse(200, SNAPSHOTS));
      }
      return Promise.resolve(jsonResponse(200, SOURCES));
    }),
  );
}

async function selectSeededSnapshot(): Promise<void> {
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <NormalizeManagementScreen />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText(SEEDED_SNAPSHOT_ID.slice(0, 8))).toBeInTheDocument());
  await user.click(screen.getByText(SEEDED_SNAPSHOT_ID.slice(0, 8)));
}

describe("NormalizeManagementScreen", () => {
  beforeEach(() => {
    installFetchMock();
  });

  it("keeps seal and normalize as distinct buttons in distinct sections", async () => {
    await selectSeededSnapshot();
    await waitFor(() => expect(screen.getByTestId("create-run-button")).toBeInTheDocument());

    const snapshotsPane = screen.getByTestId("snapshots-pane");
    const createRunPane = screen.getByTestId("create-run-pane");

    const sealButton = within(snapshotsPane).getByTestId("seal-button");
    const createRunButton = within(createRunPane).getByTestId("create-run-button");

    expect(sealButton).not.toBe(createRunButton);
    expect(within(snapshotsPane).queryByTestId("create-run-button")).toBeNull();
    expect(within(createRunPane).queryByTestId("seal-button")).toBeNull();
  });

  it("sealing POSTs to /sources/{id}/snapshots and shows the accepted outcome", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByTestId("seal-button")).toBeInTheDocument());

    await user.click(screen.getByTestId("seal-button"));

    await waitFor(() => {
      const sealCall = fetchMock().mock.calls.find(
        (call) =>
          String(call[0]).includes("/sources/naver-blog-main/snapshots") &&
          (call[1] as RequestInit | undefined)?.method === "POST",
      );
      expect(sealCall).toBeTruthy();
    });
    await waitFor(() => expect(screen.getByText(/Sealed snapshot/)).toBeInTheDocument());
  });

  it("creating a run POSTs {source_id: <normalizer source id>} to /snapshots/{id}/normalize", async () => {
    const user = userEvent.setup();
    await selectSeededSnapshot();
    await waitFor(() => expect(screen.getByTestId("create-run-button")).toBeInTheDocument());

    await user.click(screen.getByTestId("create-run-button"));

    await waitFor(() => {
      const runCall = fetchMock().mock.calls.find((call) => String(call[0]).includes("/normalize"));
      expect(runCall).toBeTruthy();
      const [, init] = runCall as [string, RequestInit];
      expect(JSON.parse(init.body as string)).toEqual({ source_id: "naver-blog-normalizer" });
    });
    await waitFor(() => expect(screen.getByText(/Normalize run enqueued/)).toBeInTheDocument());
  });

  it("renders two result versions side by side for the selected snapshot (version coexistence)", async () => {
    await selectSeededSnapshot();

    await waitFor(() => expect(screen.getAllByTestId("result-version-group")).toHaveLength(2));
    const groups = screen.getAllByTestId("result-version-group");
    expect(within(groups[0] as HTMLElement).getByText(/0\.1\.0/)).toBeInTheDocument();
    expect(within(groups[1] as HTMLElement).getByText(/0\.2\.0/)).toBeInTheDocument();
  });

  it("shows the error badge only on the flagged record, and the run summary counts it", async () => {
    await selectSeededSnapshot();
    await waitFor(() => expect(screen.getAllByTestId("result-version-group")).toHaveLength(2));

    const groups = screen.getAllByTestId("result-version-group");
    const v1 = groups[0] as HTMLElement;
    const v2 = groups[1] as HTMLElement;

    expect(within(v1).getAllByTestId("normalize-error-badge")).toHaveLength(1);
    expect(within(v1).getByTestId("result-group-summary").textContent).toContain("1 error");

    expect(within(v2).queryByTestId("normalize-error-badge")).toBeNull();
    expect(within(v2).getByTestId("result-group-summary").textContent).toContain("0 errors");
  });
});
