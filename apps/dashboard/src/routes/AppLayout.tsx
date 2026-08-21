// The shell every screen renders inside: a top bar naming the six DP-033 D1
// screens, and an `<Outlet />` for whichever route matched.

import { AppBar, Box, Tab, Tabs, Toolbar, Typography } from "@mui/material";
import type { JSX } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

interface NavItem {
  path: string;
  label: string;
}

/** DP-033 D1's six screens, in the order the decision names them. */
const NAV_ITEMS: readonly NavItem[] = [
  { path: "/collectors", label: "Collectors" },
  { path: "/browser", label: "Data Browser" },
  { path: "/downloads", label: "Downloads" },
  { path: "/normalize", label: "Normalization" },
  { path: "/jobs", label: "Jobs" },
  { path: "/health", label: "Health" },
];

function currentNavPath(pathname: string): string | false {
  const match = NAV_ITEMS.find(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  );
  return match?.path ?? false;
}

export function AppLayout(): JSX.Element {
  const location = useLocation();
  const current = currentNavPath(location.pathname);

  return (
    <Box>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar sx={{ flexWrap: "wrap", gap: 2 }}>
          <Typography variant="h6" component="div">
            Cosmai operator
          </Typography>
          <Tabs value={current} textColor="primary" indicatorColor="primary">
            {NAV_ITEMS.map((item) => (
              <Tab key={item.path} label={item.label} value={item.path} component={Link} to={item.path} />
            ))}
          </Tabs>
        </Toolbar>
      </AppBar>
      <Outlet />
    </Box>
  );
}
