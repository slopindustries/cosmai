// vitest setup: jest-dom matchers, and per-test cleanup so a stubbed `fetch` or a
// mounted component from one test never leaks into the next.

import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
