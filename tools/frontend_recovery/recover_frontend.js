#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..", "..");
const assetsDir = path.join(repoRoot, "copaw", "console", "assets");
const entryFile = path.join(assetsDir, "index-DR5NfigS.js");

const outputRoot = path.join(repoRoot, "copaw", "console_decompiled");
const originalDir = path.join(outputRoot, "original");
const prettyDir = path.join(outputRoot, "pretty");
const reportsDir = path.join(outputRoot, "reports");
const snippetsDir = path.join(outputRoot, "snippets");

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

function copyFile(src, dst) {
  ensureDir(path.dirname(dst));
  fs.copyFileSync(src, dst);
}

function beautifyFile(srcFile, dstFile) {
  execFileSync(
    "js-beautify",
    [
      "-f",
      srcFile,
      "-o",
      dstFile,
      "--type",
      "js",
      "-s",
      "2",
      "-n",
      "-p",
      "--max-preserve-newlines",
      "3",
    ],
    { stdio: "pipe" },
  );
}

function listAssetJsFiles() {
  const entries = fs.readdirSync(assetsDir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));
}

function parseMapDeps(raw) {
  const match = raw.match(/m\.f\|\|\(m\.f=\[([\s\S]*?)\]\)\)/);
  if (!match) {
    return [];
  }
  try {
    return JSON.parse(`[${match[1]}]`);
  } catch (_error) {
    return [];
  }
}

function parseDynamicImports(raw) {
  const imports = new Set();
  const pattern = /import\((["'`])([^"'`]+)\1\)/g;
  let match;
  while ((match = pattern.exec(raw)) !== null) {
    imports.add(match[2]);
  }
  return [...imports].sort((a, b) => a.localeCompare(b));
}

function parseExportAliases(raw) {
  const exportMatch = raw.match(/export\{([\s\S]*?)\};?\s*$/);
  if (!exportMatch) {
    return [];
  }
  const mapping = [];
  const pattern = /([A-Za-z0-9_$]+)\s+as\s+([A-Za-z0-9_$]+)/g;
  let match;
  while ((match = pattern.exec(exportMatch[1])) !== null) {
    mapping.push({
      local: match[1],
      exported: match[2],
    });
  }
  return mapping;
}

function parseXrMethods(raw) {
  const counter = new Map();
  const pattern = /Xr\.([A-Za-z0-9_$]+)\s*\(/g;
  let match;
  while ((match = pattern.exec(raw)) !== null) {
    const method = match[1];
    counter.set(method, (counter.get(method) || 0) + 1);
  }
  return [...counter.entries()]
    .map(([method, calls]) => ({ method, calls }))
    .sort((a, b) => b.calls - a.calls || a.method.localeCompare(b.method));
}

function parseRoutePaths(raw) {
  const paths = new Set();
  const pattern = /path:\s*(["'])([^"']+)\1/g;
  let match;
  while ((match = pattern.exec(raw)) !== null) {
    const routePath = match[2];
    if (routePath.startsWith("/")) {
      paths.add(routePath);
    }
  }
  return [...paths].sort((a, b) => a.localeCompare(b));
}

function parseBusinessI18nKeys(raw) {
  const keySet = new Set();
  const pattern =
    /(["'])(common|nav|workspace|skills|cronJobs|channels|sessions|environments|models)\.[^"']+\1/g;
  let match;
  while ((match = pattern.exec(raw)) !== null) {
    keySet.add(match[0].slice(1, -1));
  }
  return [...keySet].sort((a, b) => a.localeCompare(b));
}

function extractByAnchors(raw, begin, end) {
  const startIndex = raw.indexOf(begin);
  if (startIndex < 0) {
    return null;
  }
  const endIndex = raw.indexOf(end, startIndex);
  if (endIndex < 0) {
    return null;
  }
  return raw.slice(startIndex, endIndex);
}

function main() {
  if (!fs.existsSync(assetsDir)) {
    throw new Error(`assets 目录不存在: ${assetsDir}`);
  }
  if (!fs.existsSync(entryFile)) {
    throw new Error(`入口文件不存在: ${entryFile}`);
  }

  ensureDir(outputRoot);
  ensureDir(originalDir);
  ensureDir(prettyDir);
  ensureDir(reportsDir);
  ensureDir(snippetsDir);

  const jsFiles = listAssetJsFiles();

  for (const filename of jsFiles) {
    const src = path.join(assetsDir, filename);
    const dstOriginal = path.join(originalDir, filename);
    const dstPretty = path.join(prettyDir, filename);
    copyFile(src, dstOriginal);
    beautifyFile(src, dstPretty);
  }

  const rawEntry = readText(entryFile);
  const prettyEntryPath = path.join(prettyDir, path.basename(entryFile));
  const prettyEntry = readText(prettyEntryPath);

  const mapDeps = parseMapDeps(rawEntry);
  const dynamicImports = parseDynamicImports(rawEntry);
  const exportAliases = parseExportAliases(rawEntry);
  const xrMethods = parseXrMethods(prettyEntry);
  const routePaths = parseRoutePaths(prettyEntry);
  const i18nKeys = parseBusinessI18nKeys(prettyEntry);

  const summary = {
    generated_at: new Date().toISOString(),
    assets_js_count: jsFiles.length,
    map_deps_count: mapDeps.length,
    dynamic_import_count: dynamicImports.length,
    export_alias_count: exportAliases.length,
    xr_method_count: xrMethods.length,
    route_path_count: routePaths.length,
    business_i18n_key_count: i18nKeys.length,
    entry_file: path.relative(repoRoot, entryFile),
    pretty_entry_file: path.relative(repoRoot, prettyEntryPath),
  };

  writeText(
    path.join(reportsDir, "summary.json"),
    `${JSON.stringify(summary, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "map-deps.json"),
    `${JSON.stringify(mapDeps, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "dynamic-imports.json"),
    `${JSON.stringify(dynamicImports, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "export-aliases.json"),
    `${JSON.stringify(exportAliases, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "xr-methods.json"),
    `${JSON.stringify(xrMethods, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "route-paths.json"),
    `${JSON.stringify(routePaths, null, 2)}\n`,
  );
  writeText(
    path.join(reportsDir, "business-i18n-keys.json"),
    `${JSON.stringify(i18nKeys, null, 2)}\n`,
  );

  const i18nSnippet = extractByAnchors(
    prettyEntry,
    "const B0n = {",
    "Es.use(wQt).init({",
  );
  if (i18nSnippet) {
    writeText(
      path.join(snippetsDir, "i18n-block.js"),
      `${i18nSnippet}\n\n// init call starts at: Es.use(wQt).init({...})\n`,
    );
  }

  const runtimeConfigSnippet = extractByAnchors(
    prettyEntry,
    "const Ahn = new khn",
    "Qhn = nst",
  );
  if (runtimeConfigSnippet) {
    writeText(
      path.join(snippetsDir, "runtime-config-block.js"),
      `${runtimeConfigSnippet}\n\n// style block starts at: Qhn = nst(...)\n`,
    );
  }

  const xrApiSnippet = extractByAnchors(
    prettyEntry,
    "const QQt = {",
    "/**\n * @license lucide-react",
  );
  if (xrApiSnippet) {
    writeText(
      path.join(snippetsDir, "xr-api-block.js"),
      `${xrApiSnippet}\n\n// next block starts at: lucide-react license comment\n`,
    );
  }

  const sessionStoreSnippet = extractByAnchors(
    prettyEntry,
    "class khn {",
    "const Ahn = new khn",
  );
  if (sessionStoreSnippet) {
    writeText(
      path.join(snippetsDir, "session-store-block.js"),
      `${sessionStoreSnippet}\n\n// singleton init starts at: const Ahn = new khn\n`,
    );
  }

  const routerSnippet = extractByAnchors(
    prettyEntry,
    "const {\n  Content: M0n",
    "const L0n = Ba`",
  );
  if (routerSnippet) {
    writeText(
      path.join(snippetsDir, "router-block.js"),
      `${routerSnippet}\n\n// global style starts at: const L0n = Ba(templates)\n`,
    );
  }

  const markerReport = {
    i18n_block_extracted: Boolean(i18nSnippet),
    runtime_config_extracted: Boolean(runtimeConfigSnippet),
    xr_api_extracted: Boolean(xrApiSnippet),
    session_store_extracted: Boolean(sessionStoreSnippet),
    router_block_extracted: Boolean(routerSnippet),
  };
  writeText(
    path.join(reportsDir, "snippet-markers.json"),
    `${JSON.stringify(markerReport, null, 2)}\n`,
  );

  process.stdout.write(
    `Done. decompiled output: ${path.relative(repoRoot, outputRoot)}\n`,
  );
}

main();
