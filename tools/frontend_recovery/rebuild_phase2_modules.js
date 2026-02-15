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

function applyIdentifierRenameMap(raw, entries) {
  let output = raw;
  for (const [from, to] of entries) {
    const pattern = new RegExp(`\\b${from}\\b`, "g");
    output = output.replace(pattern, to);
  }
  return output;
}

const i18nIdentifierRenameEntries = [
  ["B0n", "commonEn"],
  ["F0n", "navEn"],
  ["U0n", "workspaceEn"],
  ["j0n", "skillsEn"],
  ["X0n", "cronJobsEn"],
  ["Y0n", "channelsEn"],
  ["V0n", "sessionsEn"],
  ["q0n", "environmentsEn"],
  ["G0n", "modelsEn"],
  ["W0n", "translationEn"],
  ["H0n", "commonZh"],
  ["Z0n", "navZh"],
  ["K0n", "workspaceZh"],
  ["J0n", "skillsZh"],
  ["ebn", "cronJobsZh"],
  ["tbn", "channelsZh"],
  ["nbn", "sessionsZh"],
  ["rbn", "environmentsZh"],
  ["abn", "modelsZh"],
  ["ibn", "translationZh"],
  ["obn", "i18nResources"],
];

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
    .replace(/\$\{O2\}/g, "${API_BASE_URL}")
    .replace(/\bencodeURIComponent\(/g, "encodePathSegment(")
    .replace(/\bJSON\.stringify\(/g, "toJsonBody(")
    .replace(/new URLSearchParams;/g, "new URLSearchParams();");
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

/**
 * @typedef {{ user_id?: string, channel?: string }} SessionFilter
 */

const encodePathSegment = (value) => encodeURIComponent(value);

const buildSessionQuery = (filter) => {
  const query = new URLSearchParams();
  if (filter?.user_id) {
    query.append("user_id", filter.user_id);
  }
  if (filter?.channel) {
    query.append("channel", filter.channel);
  }
  const queryString = query.toString();
  return queryString ? \`?\${queryString}\` : "";
};

const toJsonBody = (value) => JSON.stringify(value);

/**
 * @template T
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<T>}
 */
export async function requestJson(path, options) {
  const response = await fetch(\`\${API_BASE_URL}\${path}\`, options);
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      \`Request failed: \${response.status} \${response.statusText}\${message ? \` - \${message}\` : ""}\`,
    );
  }
  if (response.status === 204) {
    return /** @type {T} */ (null);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return /** @type {Promise<T>} */ (response.json());
  }
  return /** @type {Promise<T>} */ (response.text());
}

${blockContent}

if (chatsApi?.listChats) {
  chatsApi.listChats = /** @param {SessionFilter} [filter] */ (filter) =>
    requestJson(\`/chats\${buildSessionQuery(filter)}\`);
}
if (sessionsApi?.listSessions) {
  sessionsApi.listSessions = /** @param {SessionFilter} [filter] */ (filter) =>
    requestJson(\`/chats\${buildSessionQuery(filter)}\`);
}

export const xrApi = {
${mergedSpread}
};

export const xrApiGroups = [${exportsList}];
`;
}

function renderSessionStoreModule(_sessionSnippet) {
  return `// Recovered from copaw/console_decompiled/snippets/session-store-block.js
// NOTE: Ut/Phn/Rhn 在打包后已匿名化，这里使用安全兜底实现，供后续手工重命名。

import { xrApi } from "../api/xr";

const mapSessionSummary = (value) => value;
const normalizeMessages = (value) => value;
const SESSION_STORAGE_KEY = "agent-scope-runtime-webui-sessions";
const DEFAULT_USER_ID = "default";
const DEFAULT_CHANNEL = "console";
const NEW_CHAT_NAME = "New Chat";

class SessionStore {
  constructor() {
    this.lsKey = SESSION_STORAGE_KEY;
    this.sessionList = [];
    this.fetchPromise = null;
    this.lastFetchTime = 0;
    this.cacheTimeout = 5e3;
    this.sessionCache = new Map();
    this.sessionFetchPromises = new Map();
    this.sessionCacheTimeout = 5e3;
  }

  persistSessionList() {
    localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList));
  }

  createEmptySession(sessionId) {
    window.currentSessionId = sessionId;
    window.currentUserId = DEFAULT_USER_ID;
    window.currentChannel = DEFAULT_CHANNEL;
    return {
      id: sessionId,
      name: NEW_CHAT_NAME,
      sessionId,
      userId: DEFAULT_USER_ID,
      channel: DEFAULT_CHANNEL,
      messages: [],
      meta: {},
    };
  }

  updateWindowVariables(session) {
    window.currentSessionId = session.sessionId || "";
    window.currentUserId = session.userId || DEFAULT_USER_ID;
    window.currentChannel = session.channel || DEFAULT_CHANNEL;
  }

  getLocalSession(sessionId) {
    const existing = this.sessionList.find((session) => session.id === sessionId);
    if (!existing) {
      return this.createEmptySession(sessionId);
    }
    this.updateWindowVariables(existing);
    return existing;
  }

  async getSessionList() {
    if (this.fetchPromise) {
      return this.fetchPromise;
    }

    const now = Date.now();
    if (this.sessionList.length > 0 && now - this.lastFetchTime < this.cacheTimeout) {
      return [...this.sessionList];
    }

    this.fetchPromise = this.fetchSessionListFromBackend();
    try {
      return await this.fetchPromise;
    } finally {
      this.fetchPromise = null;
    }
  }

  async fetchSessionListFromBackend() {
    try {
      const sessions = (await xrApi.listChats()).filter(
        (session) => session.id && session.id !== "undefined" && session.id !== "null",
      );
      this.sessionList = sessions.map(mapSessionSummary).reverse();
      this.persistSessionList();
      this.lastFetchTime = Date.now();
      return [...this.sessionList];
    } catch {
      this.sessionList = JSON.parse(localStorage.getItem(this.lsKey) || "[]");
      return [...this.sessionList];
    }
  }

  async getSession(sessionId) {
    try {
      if (!sessionId || sessionId === "undefined" || sessionId === "null") {
        return this.createEmptySession(\`temp-\${Date.now()}\`);
      }
      if (/^\\d+$/.test(sessionId)) {
        return this.getLocalSession(sessionId);
      }

      const cacheEntry = this.sessionCache.get(sessionId);
      const now = Date.now();
      if (cacheEntry && now - cacheEntry.timestamp < this.sessionCacheTimeout) {
        this.updateWindowVariables(cacheEntry.session);
        return cacheEntry.session;
      }

      const inFlightRequest = this.sessionFetchPromises.get(sessionId);
      if (inFlightRequest) {
        return inFlightRequest;
      }

      const request = this.fetchSessionFromBackend(sessionId);
      this.sessionFetchPromises.set(sessionId, request);
      try {
        return await request;
      } finally {
        this.sessionFetchPromises.delete(sessionId);
      }
    } catch {
      const cachedSession = this.sessionList.find((session) => session.id === sessionId);
      return cachedSession || this.createEmptySession(sessionId);
    }
  }

  async fetchSessionFromBackend(sessionId) {
    const remoteSession = await xrApi.getChat(sessionId);
    const localSession = this.sessionList.find((session) => session.id === sessionId);
    const mergedSession = {
      id: sessionId,
      name: localSession?.name || sessionId,
      sessionId: localSession?.sessionId || sessionId,
      userId: localSession?.userId || DEFAULT_USER_ID,
      channel: localSession?.channel || DEFAULT_CHANNEL,
      messages: normalizeMessages(remoteSession.messages || []),
      meta: localSession?.meta || {},
    };
    this.updateWindowVariables(mergedSession);
    this.sessionCache.set(sessionId, {
      session: mergedSession,
      timestamp: Date.now(),
    });
    return mergedSession;
  }

  async updateSession(patch) {
    const index = this.sessionList.findIndex((session) => session.id === patch.id);
    if (index > -1) {
      this.sessionList[index] = {
        ...this.sessionList[index],
        ...patch,
      };
      this.persistSessionList();
    }
    return [...this.sessionList];
  }

  async createSession(session) {
    session.id = Date.now().toString();
    this.sessionList.unshift(session);
    this.persistSessionList();
    this.lastFetchTime = Date.now();
    return [...this.sessionList];
  }

  async removeSession(session) {
    try {
      if (!session.id) {
        return [...this.sessionList];
      }
      const sessionId = session.id;
      await xrApi.deleteChat(sessionId);
      this.sessionList = this.sessionList.filter((item) => item.id !== sessionId);
      this.persistSessionList();
      this.lastFetchTime = Date.now();
      return [...this.sessionList];
    } catch {
      if (session.id) {
        this.sessionList = this.sessionList.filter((item) => item.id !== session.id);
        this.persistSessionList();
        this.lastFetchTime = Date.now();
      }
      return [...this.sessionList];
    }
  }
}

export const sessionStore = new SessionStore();
`;
}

function renderRouterRoutes(routeMap, routeComponents) {
  return `// Recovered from copaw/console_decompiled/snippets/router-block.js

export const navKeyByPath = ${JSON.stringify(routeMap, null, 2)};

export const DEFAULT_ROUTE_PATH = "/chat";

/**
 * Resolve nav menu key by pathname and fallback to default chat page.
 * @param {string} pathname
 * @returns {string}
 */
export const getNavKeyForPath = (pathname) =>
  navKeyByPath[pathname] || navKeyByPath[DEFAULT_ROUTE_PATH];

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
  const sanitized = sanitizeI18nSnippet(i18nSnippet);
  const renamed = applyIdentifierRenameMap(sanitized, i18nIdentifierRenameEntries);
  return `${renamed}
export const recoveredI18nResources = i18nResources;
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
      "phase2 为语义重建 + 可运行化命名整理，不等价于原始 TS/Vue 源码",
      "无 source map 条件下，变量命名和模块边界存在近似误差",
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
