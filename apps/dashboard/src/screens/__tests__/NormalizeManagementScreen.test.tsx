import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { NormalizeManagementScreen } from "../NormalizeManagementScreen";

const SEEDED_SNAPSHOT_SHORT_ID = "22222222";

async function selectSeededSnapshot(): Promise<void> {
  const user = userEvent.setup();
  render(<NormalizeManagementScreen />);
  await user.click(screen.getByText(SEEDED_SNAPSHOT_SHORT_ID));
}

describe("NormalizeManagementScreen", () => {
  it("keeps seal and normalize as distinct buttons in distinct sections", async () => {
    await selectSeededSnapshot();

    const snapshotsPane = screen.getByTestId("snapshots-pane");
    const createRunPane = screen.getByTestId("create-run-pane");

    const sealButton = within(snapshotsPane).getByTestId("seal-button");
    const createRunButton = within(createRunPane).getByTestId("create-run-button");

    // Distinct DOM nodes, and neither pane's button is nested inside the other's.
    expect(sealButton).not.toBe(createRunButton);
    expect(within(snapshotsPane).queryByTestId("create-run-button")).toBeNull();
    expect(within(createRunPane).queryByTestId("seal-button")).toBeNull();
  });

  it("sealing creates a new, separate snapshot row without touching the normalize pane", async () => {
    const user = userEvent.setup();
    render(<NormalizeManagementScreen />);

    const before = screen.getAllByRole("row").length;
    await user.click(screen.getByTestId("seal-button"));

    expect(screen.getAllByRole("row").length).toBeGreaterThan(before);
    expect(screen.getByText(/Sealed snapshot/)).toBeInTheDocument();
    // Sealing alone must not have created or selected a run.
    expect(screen.queryByTestId("create-run-button")).toBeNull();
  });

  it("renders two result versions side by side for the selected snapshot (version coexistence)", async () => {
    await selectSeededSnapshot();

    const groups = screen.getAllByTestId("result-version-group");
    expect(groups).toHaveLength(2);
    expect(within(groups[0] as HTMLElement).getByText(/0\.1\.0/)).toBeInTheDocument();
    expect(within(groups[1] as HTMLElement).getByText(/0\.2\.0/)).toBeInTheDocument();
  });

  it("shows the error badge only on the flagged record, and the run summary counts it", async () => {
    await selectSeededSnapshot();

    const groups = screen.getAllByTestId("result-version-group");
    const v1 = groups[0] as HTMLElement;
    const v2 = groups[1] as HTMLElement;

    // v0.1.0 has one flagged record.
    expect(within(v1).getAllByTestId("normalize-error-badge")).toHaveLength(1);
    expect(within(v1).getByTestId("result-group-summary").textContent).toContain("1 error");

    // v0.2.0 has none.
    expect(within(v2).queryByTestId("normalize-error-badge")).toBeNull();
    expect(within(v2).getByTestId("result-group-summary").textContent).toContain("0 errors");
  });
});
