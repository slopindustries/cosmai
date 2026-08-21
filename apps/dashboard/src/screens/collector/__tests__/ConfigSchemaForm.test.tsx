import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConfigField } from "../ConfigSchemaForm";
import { ConfigSchemaForm } from "../ConfigSchemaForm";

const FIELDS: readonly ConfigField[] = [
  { name: "query", type: "string", required: true, label: "Search query" },
  { name: "display", type: "integer", required: false, label: "Results per page" },
];

describe("ConfigSchemaForm", () => {
  it("renders a required string field and an optional integer field with the right input types", () => {
    render(<ConfigSchemaForm fields={FIELDS} onSubmit={vi.fn()} />);

    const queryInput = screen.getByLabelText(/Search query/) as HTMLInputElement;
    expect(queryInput).toBeRequired();
    expect(queryInput.type).toBe("text");

    const displayInput = screen.getByLabelText(/Results per page/) as HTMLInputElement;
    expect(displayInput).not.toBeRequired();
    expect(displayInput.type).toBe("number");
  });

  it("blocks submission and shows a message when a required field is empty", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ConfigSchemaForm fields={FIELDS} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /save config/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/Search query is required/)).toBeInTheDocument();
  });

  it("calls onSubmit with the entered values once the required field is filled", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ConfigSchemaForm fields={FIELDS} onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/Search query/), "seoul cafe");
    await user.click(screen.getByRole("button", { name: /save config/i }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ query: "seoul cafe" }));
  });
});
