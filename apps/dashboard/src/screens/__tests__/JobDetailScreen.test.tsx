import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Attempt, AttemptPage, Job, RetryAccepted } from "../../api/types";
import { jsonResponse } from "../../test/fetchMock";
import { JobDetailScreen } from "../JobDetailScreen";

const JOB_ID = "22222222-2222-2222-2222-222222222222";
const PROTECTED_TOKEN = "top-secret-token-value";

const job: Job = {
  id: JOB_ID,
  handler: "demo.handler",
  payload: { note: "hi" },
  state: "FAILED",
  attempt_count: 2,
  max_attempts: 3,
  available_at: "2026-08-21T00:00:00Z",
  lease_owner: null,
  lease_expires_at: null,
  terminal_reason: "handler raised",
  correlation_id: "corr-2",
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:05:00Z",
  attempts_remaining: 1,
  attempt_budget_spent: false,
};

const attempt: Attempt = {
  id: "attempt-1",
  job_id: JOB_ID,
  attempt_no: 1,
  worker_id: "worker-1",
  started_at: "2026-08-21T00:00:00Z",
  finished_at: "2026-08-21T00:01:00Z",
  outcome: "RETRYABLE_FAILURE",
  error_class: "PLATFORM_TRANSIENT",
  error_summary: "connection reset",
  correlation_id: "corr-2",
  error_detail_present: true,
  error_class_retryable: true,
};

const defaultAttempts: AttemptPage = {
  job_id: JOB_ID,
  correlation_id: "corr-2",
  representation: "default",
  attempts: [attempt],
};

const protectedAttempts: AttemptPage = {
  ...defaultAttempts,
  representation: "protected",
  attempts: [{ ...attempt, error_detail: { hint: PROTECTED_TOKEN } }],
};

function renderScreen(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/jobs/${JOB_ID}`]}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetailScreen />} />
        </Routes>
      </MemoryRouter>
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
      if (method === "POST" && url.includes("/retry")) {
        const accepted: RetryAccepted = {
          accepted: true,
          job_id: JOB_ID,
          correlation_id: "corr-2",
          previous_state: "FAILED",
          current_state: "PENDING",
          job: { ...job, state: "PENDING" },
        };
        return Promise.resolve(jsonResponse(200, accepted));
      }
      if (url.includes("/attempts")) {
        const page = url.includes("debug=protected") ? protectedAttempts : defaultAttempts;
        return Promise.resolve(jsonResponse(200, page));
      }
      return Promise.resolve(jsonResponse(200, job));
    }),
  );
}

describe("JobDetailScreen", () => {
  beforeEach(() => {
    installFetchMock();
  });

  it("renders the attempt's error class", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText("PLATFORM_TRANSIENT")).toBeInTheDocument());
  });

  it("withholds the protected error detail until the toggle is used", async () => {
    renderScreen();

    await waitFor(() => expect(screen.getByText("present, withheld")).toBeInTheDocument());
    expect(screen.queryByText(new RegExp(PROTECTED_TOKEN))).not.toBeInTheDocument();
    expect(fetchMock().mock.calls.every((call) => !String(call[0]).includes("debug=protected"))).toBe(
      true,
    );
  });

  it("reveals the protected error detail only after the toggle is clicked", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByText("present, withheld")).toBeInTheDocument());

    await user.click(screen.getByText(/Show protected detail/));

    await waitFor(() => expect(screen.getByText(new RegExp(PROTECTED_TOKEN))).toBeInTheDocument());
    expect(fetchMock().mock.calls.some((call) => String(call[0]).includes("debug=protected"))).toBe(
      true,
    );
  });

  it("fires a POST to the retry endpoint when the retry button is clicked", async () => {
    const user = userEvent.setup();
    renderScreen();
    await waitFor(() => expect(screen.getByRole("button", { name: /request retry/i })).toBeEnabled());

    await user.click(screen.getByRole("button", { name: /request retry/i }));

    await waitFor(() => {
      const retryCall = fetchMock().mock.calls.find(
        (call) =>
          String(call[0]).includes("/retry") &&
          (call[1] as RequestInit | undefined)?.method === "POST",
      );
      expect(retryCall).toBeTruthy();
    });
    await waitFor(() => expect(screen.getByText(/Retry accepted/)).toBeInTheDocument());
  });
});
