// Recovered routing shell (pseudo-source for module reconstruction phase).

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { DEFAULT_ROUTE_PATH, getNavKeyForPath } from "./routes";

export function useRecoveredSelectedKey() {
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = location.pathname;
  const selectedKey = getNavKeyForPath(pathname);

  useEffect(() => {
    if (pathname === "/") {
      navigate(DEFAULT_ROUTE_PATH, { replace: true });
    }
  }, [pathname, navigate]);

  return selectedKey;
}
