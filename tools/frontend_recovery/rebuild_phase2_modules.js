#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const decompiledRoot = path.join(repoRoot, "copaw", "console_decompiled");
const snippetsDir = path.join(decompiledRoot, "snippets");
const reportsDir = path.join(decompiledRoot, "reports");
const modulesDir = path.join(decompiledRoot, "modules");

const xrGroups = [
  { varName: "QQt", exportName: "rootApi" },
  { varName: "DQt", exportName: "channelsApi" },
  { varName: "LQt", exportName: "cronJobsApi" },
  { varName: "zQt", exportName: "chatsApi" },
  { varName: "BQt", exportName: "sessionsApi" },
  { varName: "FQt", exportName: "envsApi" },
  { varName: "UQt", exportName: "modelsApi" },
  { varName: "jQt", exportName: "skillsApi" },
  { varName: "XQt", exportName: "agentApi" },
  { varName: "T9", exportName: "workspaceApi" },
];

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function writeText(filePath, content) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, content, "utf8");
}

function readJson(filePath) {
  return JSON.parse(readText(filePath));
}

function extractAssignedObject(raw, varName, nextVarName) {
  const startPattern = new RegExp(`\\b${varName}\\s*=\\s*\\{`);
  const startMatch = startPattern.exec(raw);
  if (!startMatch) {
    return null;
  }
  const startIndex = startMatch.index;
  const objectStart = raw.indexOf("{", startIndex);
  if (objectStart < 0) {
    return null;
  }

  let objectEnd = -1;
  if (nextVarName) {
    const nextPattern = new RegExp(`,\\s*${nextVarName}\\s*=\\s*\\{`);
    const nextMatch = nextPattern.exec(raw.slice(startIndex));
    if (!nextMatch) {
      return null;
    }
    const nextIndex = startIndex + nextMatch.index;
    objectEnd = raw.lastIndexOf("}", nextIndex);
  } else {
    const tailIndex = raw.indexOf("};", startIndex);
    if (tailIndex < 0) {
      return null;
    }
    objectEnd = raw.lastIndexOf("}", tailIndex);
  }

  if (objectEnd < objectStart) {
    return null;
  }
  return raw.slice(objectStart, objectEnd + 1).trim();
}

function sanitizeI18nSnippet(raw) {
  return raw
    .replace(/\n*\/\/ init call starts[\s\S]*$/m, "\n")
    .replace(/\s+$/, "\n");
}

function parseRouteMap(raw) {
  const mapMatch = raw.match(/\bQ0n\s*=\s*\{([\s\S]*?)\};/);
  if (!mapMatch) {
    return {};
  }
  const mapObj = {};
  const pairPattern = /["']([^"']+)["']\s*:\s*["']([^"']+)["']/g;
  let pair;
  while ((pair = pairPattern.exec(mapMatch[1])) !== null) {
    mapObj[pair[1]] = pair[2];
  }
  return mapObj;
}

function parseRouteComponents(raw) {
  const items = [];
  const pattern =
    /path:\s*"([^"]+)"[\s\S]{0,120}?element:\s*N\.jsx\(\s*([A-Za-z0-9_$]+)\s*,\s*\{\s*\}\s*\)/g;
  let match;
  while ((match = pattern.exec(raw)) !== null) {
    items.push({
      path: match[1],
      componentSymbol: match[2],
    });
  }
  return items;
}

function normalizeRecoveredSnippet(raw) {
  return raw
    .replace(/\bUn\(/g, "requestJson(")
    .replace(/\$\{O2\}/g, "${API_BASE_URL}");
}

function renderApiModule(xrSnippet) {
  const blocks = [];
  for (let i = 0; i < xrGroups.length; i += 1) {
    const current = xrGroups[i];
    const next = xrGroups[i + 1];
    const nextVarName = next ? next.varName : "Xr";
    const objectLiteral = extractAssignedObject(
      xrSnippet,
      current.varName,
      nextVarName,
    );
    if (!objectLiteral) {
      throw new Error(`无法提取 XR 片段对象: ${current.varName}`);
    }
    blocks.push({
      exportName: current.exportName,
      objectLiteral: normalizeRecoveredSnippet(objectLiteral),
    });
  }

  const exportsList = blocks.map((block) => block.exportName).join(", ");
  const mergedSpread = blocks
    .map((block) => `  ...${block.exportName},`)
    .join("\n");
  const blockContent = blocks
    .map(
      (block) => `export const ${block.exportName} = ${block.objectLiteral};`,
    )
    .join("\n\n");

  return `// Recovered from copaw/console_decompiled/snippets/xr-api-block.js
// NOTE: 这是语义恢复版，变量命名和类型并非原始源码。

export const API_BASE_URL = "";

export async function requestJson(path, options) {
  const response = await fetch(\`\${API_BASE_URL}\${path}\`, options);
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      \`Request failed: \${response.status} \${response.statusText}\${message ? \` - \${message}\` : ""}\`,
    );
  }
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

${blockContent}

export const xrApi = {
${mergedSpread}
};

export const xrApiGroups = [${exportsList}];
`;
}

function renderSessionStoreModule(sessionSnippet) {
  const classOnly = sessionSnippet
    .replace(/\n*\/\/ singleton init starts[\s\S]*$/m, "\n")
    .trimEnd();

  const transformed = classOnly
    .replace(/\bkhn\b/g, "SessionStore")
    .replace(/\bXr\./g, "xrApi.")
    .replace(/\bPhn\b/g, "mapSessionSummary")
    .replace(/\bRhn\b/g, "normalizeMessages")
    .replace(
      /^\s*Ut\(this,\s*"([^"]+)"(?:,\s*([^)]+))?\);\s*$/gm,
      (_line, key, defaultValue) =>
        `    this.${key} = ${defaultValue ? defaultValue.trim() : "undefined"};`,
    )
    .replace(
      /this\.lsKey\s*=\s*"agent-scope-runtime-webui-sessions"\s*,\s*this\.sessionList\s*=\s*\[\]/,
      'this.lsKey = "agent-scope-runtime-webui-sessions";\n    this.sessionList = []',
    );

  return `// Recovered from copaw/console_decompiled/snippets/session-store-block.js
// NOTE: Ut/Phn/Rhn 在打包后已匿名化，这里使用安全兜底实现，供后续手工重命名。

import { xrApi } from "../api/xr";

const mapSessionSummary = (value) => value;
const normalizeMessages = (value) => value;

${transformed}

export const sessionStore = new SessionStore();
`;
}

function renderRouterRoutes(routeMap, routeComponents) {
  return `// Recovered from copaw/console_decompiled/snippets/router-block.js

export const navKeyByPath = ${JSON.stringify(routeMap, null, 2)};

export const recoveredRouteComponents = ${JSON.stringify(
    routeComponents,
    null,
    2,
  )};
`;
}

function renderRouterShell() {
  return `// Recovered routing shell (pseudo-source for module reconstruction phase).

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
`;
}

function renderPagesIndex(routeComponents) {
  const lines = [
    "# Recovered Page Symbols",
    "",
    "| path | componentSymbol |",
    "| --- | --- |",
  ];
  for (const item of routeComponents) {
    lines.push(`| ${item.path} | ${item.componentSymbol} |`);
  }
  lines.push("");
  return `${lines.join("\n")}`;
}

function renderI18nModule(i18nSnippet) {
  return `${sanitizeI18nSnippet(i18nSnippet)}
export const recoveredI18nResources = obn;
`;
}

function main() {
  const xrSnippetPath = path.join(snippetsDir, "xr-api-block.js");
  const sessionSnippetPath = path.join(snippetsDir, "session-store-block.js");
  const routerSnippetPath = path.join(snippetsDir, "router-block.js");
  const i18nSnippetPath = path.join(snippetsDir, "i18n-block.js");

  for (const filePath of [
    xrSnippetPath,
    sessionSnippetPath,
    routerSnippetPath,
    i18nSnippetPath,
  ]) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`缺少必要片段文件: ${path.relative(repoRoot, filePath)}`);
    }
  }

  const xrSnippet = readText(xrSnippetPath);
  const sessionSnippet = readText(sessionSnippetPath);
  const routerSnippet = readText(routerSnippetPath);
  const i18nSnippet = readText(i18nSnippetPath);

  const routeMap = parseRouteMap(routerSnippet);
  const routeComponents = parseRouteComponents(routerSnippet);

  const summaryPath = path.join(reportsDir, "summary.json");
  const xrMethodsPath = path.join(reportsDir, "xr-methods.json");
  const routePathsPath = path.join(reportsDir, "route-paths.json");
  const i18nKeysPath = path.join(reportsDir, "business-i18n-keys.json");
  for (const filePath of [summaryPath, xrMethodsPath, routePathsPath, i18nKeysPath]) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`缺少必要报告文件: ${path.relative(repoRoot, filePath)}`);
    }
  }

  const summary = readJson(summaryPath);
  const xrMethods = readJson(xrMethodsPath);
  const routePaths = readJson(routePathsPath);
  const i18nKeys = readJson(i18nKeysPath);

  const apiDir = path.join(modulesDir, "api");
  const hooksDir = path.join(modulesDir, "hooks");
  const pagesDir = path.join(modulesDir, "pages");
  const i18nDir = path.join(modulesDir, "i18n");
  const routerDir = path.join(modulesDir, "router");
  for (const dirPath of [apiDir, hooksDir, pagesDir, i18nDir, routerDir]) {
    ensureDir(dirPath);
  }

  writeText(path.join(apiDir, "xr.ts"), renderApiModule(xrSnippet));
  writeText(path.join(hooksDir, "session-store.js"), renderSessionStoreModule(sessionSnippet));
  writeText(path.join(routerDir, "routes.ts"), renderRouterRoutes(routeMap, routeComponents));
  writeText(path.join(routerDir, "router-shell.tsx"), renderRouterShell());
  writeText(path.join(pagesDir, "route-components.md"), renderPagesIndex(routeComponents));
  writeText(path.join(i18nDir, "resources.js"), renderI18nModule(i18nSnippet));

  writeText(
    path.join(apiDir, "xr-methods.json"),
    `${JSON.stringify(xrMethods, null, 2)}\n`,
  );
  writeText(
    path.join(routerDir, "route-paths.json"),
    `${JSON.stringify(routePaths, null, 2)}\n`,
  );
  writeText(
    path.join(i18nDir, "business-i18n-keys.json"),
    `${JSON.stringify(i18nKeys, null, 2)}\n`,
  );

  const generatedFiles = [
    path.join(apiDir, "xr.ts"),
    path.join(apiDir, "xr-methods.json"),
    path.join(hooksDir, "session-store.js"),
    path.join(routerDir, "routes.ts"),
    path.join(routerDir, "router-shell.tsx"),
    path.join(routerDir, "route-paths.json"),
    path.join(pagesDir, "route-components.md"),
    path.join(i18nDir, "resources.js"),
    path.join(i18nDir, "business-i18n-keys.json"),
  ].map((p) => path.relative(repoRoot, p));

  const manifest = {
    generated_at: new Date().toISOString(),
    source_summary_generated_at: summary.generated_at,
    source_reports: {
      xr_method_count: summary.xr_method_count,
      route_path_count: summary.route_path_count,
      business_i18n_key_count: summary.business_i18n_key_count,
    },
    recovered_modules: {
      api_group_count: xrGroups.length,
      router_path_count: routeComponents.length,
      page_symbol_count: new Set(routeComponents.map((item) => item.componentSymbol))
        .size,
      i18n_key_count: i18nKeys.length,
    },
    generated_files: generatedFiles,
    notes: [
      "phase2 为语义重建，不等价于原始 TS/Vue 源码",
      "session-store 仍包含匿名化辅助符号的兜底逻辑",
    ],
  };
  writeText(
    path.join(modulesDir, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );

  process.stdout.write(
    `Done. phase2 modules output: ${path.relative(repoRoot, modulesDir)}\n`,
  );
}

main();
