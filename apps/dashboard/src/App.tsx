// The routing skeleton for DP-033 D1's six screens (collector-domain, data
// browser, downloads, normalization management, jobs monitor, health/metrics),
// wrapped in the two providers the stack DP-033 D4 adopted needs: a TanStack
// Query cache and an MUI theme.

import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { JSX } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./routes/AppLayout";
import { CollectorDomainScreen } from "./screens/CollectorDomainScreen";
import { DataBrowserScreen } from "./screens/DataBrowserScreen";
import { DownloadScreen } from "./screens/DownloadScreen";
import { HealthScreen } from "./screens/HealthScreen";
import { JobDetailScreen } from "./screens/JobDetailScreen";
import { JobsListScreen } from "./screens/JobsListScreen";
import { NormalizeManagementScreen } from "./screens/NormalizeManagementScreen";

const theme = createTheme();

// Queries are not retried by default: an operator screen that silently retried a
// failed request three times before showing the failure would be slower to tell
// the truth than one that shows it immediately, and `isError` is already how
// every screen here reports a failure.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function App(): JSX.Element {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<Navigate to="/jobs" replace />} />
              <Route path="collectors" element={<CollectorDomainScreen />} />
              <Route path="browser" element={<DataBrowserScreen />} />
              <Route path="downloads" element={<DownloadScreen />} />
              <Route path="normalize" element={<NormalizeManagementScreen />} />
              <Route path="jobs" element={<JobsListScreen />} />
              <Route path="jobs/:jobId" element={<JobDetailScreen />} />
              <Route path="health" element={<HealthScreen />} />
              <Route path="*" element={<Navigate to="/jobs" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
