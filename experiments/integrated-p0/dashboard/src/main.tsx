// The browser entrypoint. Everything else in this directory is renderable without
// a DOM, which is what `src/detail-text.tsx` depends on.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const mount = document.getElementById("app");
if (mount === null) {
  throw new Error("index.html has no #app element to mount into");
}

createRoot(mount).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
