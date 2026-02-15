// Recovered routing shell (pseudo-source for module reconstruction phase).

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { navKeyByPath } from "./routes";

export function useRecoveredSelectedKey() {
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = location.pathname;
  const selectedKey = navKeyByPath[pathname] || "chat";

  useEffect(() => {
    if (pathname === "/") {
      navigate("/chat", { replace: true });
    }
  }, [pathname, navigate]);

  return selectedKey;
}
