import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JobPage } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { CollectorDomainScreen } from "../CollectorDomainScreen";

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

describe("CollectorDomainScreen", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(200, EMPTY_JOB_PAGE))),
    );
  });

  it("renders the status header, config form, credential section, job history, and schedule placeholder for the selected collector", async () => {
    renderScreen();

    expect(screen.getByTestId("status-header")).toBeInTheDocument();
    expect(screen.getByText("enabled")).toBeInTheDocument();
    expect(screen.getByLabelText(/Search query/)).toBeInTheDocument();
    expect(screen.getByLabelText("purpose")).toBeInTheDocument();
    expect(screen.getByLabelText("value")).toBeInTheDocument();
    expect(screen.getByTestId("schedule-placeholder")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/No job history/)).toBeInTheDocument());
  });
});
