import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JobPage } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { JobsListScreen } from "../JobsListScreen";

const PAGE: JobPage = {
  state: null,
  limit: 50,
  offset: 0,
  returned: 1,
  matched: 1,
  jobs: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      handler: "demo.handler",
      payload: {},
      state: "FAILED",
      attempt_count: 3,
      max_attempts: 3,
      available_at: "2026-08-21T00:00:00Z",
      lease_owner: null,
      lease_expires_at: null,
      terminal_reason: "handler raised",
      correlation_id: "corr-1",
      created_at: "2026-08-21T00:00:00Z",
      updated_at: "2026-08-21T00:00:00Z",
      attempts_remaining: 0,
      attempt_budget_spent: true,
    },
  ],
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/jobs"]}>
        <JobsListScreen />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return fetch as unknown as ReturnType<typeof vi.fn>;
}

describe("JobsListScreen", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(200, PAGE))),
    );
  });

  it("loads the default page with no state filter applied", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText("demo.handler")).toBeInTheDocument());

    const calledUrl = String(fetchMock().mock.calls[0]?.[0]);
    expect(calledUrl).toContain("/jobs?");
    expect(calledUrl).not.toContain("state=");
  });

  it("changing the state filter re-queries the API with the new state", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByText("demo.handler")).toBeInTheDocument());

    await user.click(screen.getByTestId("state-chip-FAILED"));

    await waitFor(() => {
      const lastCall = fetchMock().mock.calls.at(-1);
      expect(String(lastCall?.[0])).toContain("state=FAILED");
    });
  });

  it("returning to 'any' drops the state filter from the request", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByText("demo.handler")).toBeInTheDocument());

    await user.click(screen.getByTestId("state-chip-FAILED"));
    await waitFor(() => {
      expect(String(fetchMock().mock.calls.at(-1)?.[0])).toContain("state=FAILED");
    });

    await user.click(screen.getByTestId("state-chip-any"));
    await waitFor(() => {
      expect(String(fetchMock().mock.calls.at(-1)?.[0])).not.toContain("state=");
    });
  });
});
