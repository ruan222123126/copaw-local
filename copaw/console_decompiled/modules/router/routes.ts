// Recovered from copaw/console_decompiled/snippets/router-block.js

export const navKeyByPath = {
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/skills": "skills",
  "/workspace": "workspace",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments"
};

export const DEFAULT_ROUTE_PATH = "/chat";

/**
 * Resolve nav menu key by pathname and fallback to default chat page.
 * @param {string} pathname
 * @returns {string}
 */
export const getNavKeyForPath = (pathname) =>
  navKeyByPath[pathname] || navKeyByPath[DEFAULT_ROUTE_PATH];

export const recoveredRouteComponents = [
  {
    "path": "/chat",
    "componentSymbol": "zve"
  },
  {
    "path": "/channels",
    "componentSymbol": "umn"
  },
  {
    "path": "/sessions",
    "componentSymbol": "xmn"
  },
  {
    "path": "/cron-jobs",
    "componentSymbol": "Qmn"
  },
  {
    "path": "/skills",
    "componentSymbol": "_gn"
  },
  {
    "path": "/workspace",
    "componentSymbol": "fOn"
  },
  {
    "path": "/models",
    "componentSymbol": "ZOn"
  },
  {
    "path": "/environments",
    "componentSymbol": "I0n"
  },
  {
    "path": "/",
    "componentSymbol": "zve"
  }
];
