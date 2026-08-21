import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CredentialWriteRefusal } from "../../../api/types";
import { jsonResponse } from "../../../test/fetchMock";
import { CredentialForm } from "../CredentialForm";

const SOURCE_ID = "naver-blog-main";
const SECRET_VALUE = "super-secret-token-999";

function renderForm(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CredentialForm sourceId={SOURCE_ID} />
    </QueryClientProvider>,
  );
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return fetch as unknown as ReturnType<typeof vi.fn>;
}

async function fillAndSubmit(purpose: string, value: string): Promise<void> {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("purpose"), purpose);
  await user.type(screen.getByLabelText("value"), value);
  await user.click(screen.getByRole("button", { name: /save/i }));
}

describe("CredentialForm", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))),
    );
  });

  it("submits purpose and value as the POST body, then clears the field and never shows the value again", async () => {
    renderForm();

    await fillAndSubmit("client_id", SECRET_VALUE);

    await waitFor(() => {
      expect(fetchMock()).toHaveBeenCalledTimes(1);
    });
    const [url, init] = fetchMock().mock.calls[0] as [string, RequestInit];
    expect(String(url)).toBe(`http://127.0.0.1:8000/sources/${SOURCE_ID}/credentials`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ purpose: "client_id", value: SECRET_VALUE });

    const valueInput = screen.getByLabelText("value") as HTMLInputElement;
    await waitFor(() => expect(valueInput.value).toBe(""));
    expect(document.body.textContent ?? "").not.toContain(SECRET_VALUE);
  });

  it("shows the derived ref name and 'not written this session' before any submit", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("purpose"), "client_id");

    // `credentialRefName` sanitizes to an env-var-safe name: `-` becomes `_`.
    expect(screen.getByText("COSMA_SRC_NAVER_BLOG_MAIN_CLIENT_ID", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("not written this session")).toBeInTheDocument();
  });

  it("shows 'written this session' for the purpose just submitted, after a successful write", async () => {
    renderForm();

    await fillAndSubmit("client_id", SECRET_VALUE);

    await waitFor(() => expect(screen.getByText("written this session")).toBeInTheDocument());
  });

  it("shows the error class without echoing the submitted value on a refusal", async () => {
    const refusal: CredentialWriteRefusal = {
      error_class: "CONFIGURATION_INVALID",
      error_summary: "purpose must be a known credential part",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(422, refusal))),
    );
    renderForm();

    await fillAndSubmit("client_id", SECRET_VALUE);

    await waitFor(() => expect(screen.getByText(/CONFIGURATION_INVALID/)).toBeInTheDocument());
    expect(screen.getByText(/purpose must be a known credential part/)).toBeInTheDocument();
    const valueInput = screen.getByLabelText("value") as HTMLInputElement;
    expect(valueInput.value).toBe("");
    expect(document.body.textContent ?? "").not.toContain(SECRET_VALUE);
  });
});
