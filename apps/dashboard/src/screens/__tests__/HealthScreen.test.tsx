import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HealthResponse, MetricsResponse } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { HealthScreen } from "../HealthScreen";

const health: HealthResponse = {
  status: "ok",
  database: "reachable",
  database_name: "cosmai",
  log_level: "INFO",
  jobs_by_state: { PENDING: 1, RUNNING: 0, SUCCEEDED: 4, FAILED: 1 },
};

const metrics: MetricsResponse = {
  scope: "this API process only",
  pid: 4242,
  metrics: {
    transitions: { PENDING: 1, RUNNING: 2, SUCCEEDED: 4, FAILED: 1 },
    claim_conflicts: 2,
    suppressed_duplicate_effects: 1,
    abandoned_attempts: 0,
    rejected_completions: 0,
    attempt_duration_ms: { count: 5, total_ms: 500, min_ms: 50, max_ms: 150, mean_ms: 100 },
    lease_recovery_latency_ms: { count: 0, total_ms: 0, min_ms: 0, max_ms: 0, mean_ms: 0 },
  },
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <HealthScreen />
    </QueryClientProvider>,
  );
}

describe("HealthScreen", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/health")) {
          return Promise.resolve(jsonResponse(200, health));
        }
        return Promise.resolve(jsonResponse(200, metrics));
      }),
    );
  });

  it("shows the platform health status", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText(/status: ok/)).toBeInTheDocument());
    expect(screen.getByText(/reachable/)).toBeInTheDocument();
  });

  it("shows the metrics counters", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText(/claim conflicts: 2/)).toBeInTheDocument());
    expect(screen.getByText(/abandoned attempts: 0/)).toBeInTheDocument();
  });

  it("shows a scheduler placeholder box", () => {
    renderScreen();

    expect(screen.getByTestId("scheduler-placeholder")).toBeInTheDocument();
  });
});
