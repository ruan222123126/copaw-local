#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");

function readArgValue(args, name, defaultValue) {
  const index = args.indexOf(name);
  if (index === -1 || index + 1 >= args.length) {
    return defaultValue;
  }
  return args[index + 1];
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function assertFile(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`缺少文件: ${path.relative(repoRoot, filePath)}`);
  }
}

function compareSetMetric(metricName, baselineItems, currentItems) {
  const baselineSet = new Set(baselineItems);
  const currentSet = new Set(currentItems);
  const missing = [];
  for (const item of baselineSet) {
    if (!currentSet.has(item)) {
      missing.push(item);
    }
  }
  const ok = missing.length === 0 && currentSet.size >= baselineSet.size;
  return {
    ok,
    currentCount: currentSet.size,
    baselineCount: baselineSet.size,
    missing,
    message: ok
      ? `PASS ${metricName}: ${currentSet.size} >= ${baselineSet.size}`
      : `FAIL ${metricName}: 缺失 ${missing.length} 项`,
  };
}

function compareXrMethods(baselineItems, currentItems) {
  const baselineMap = new Map(
    baselineItems.map((item) => [String(item.method), Number(item.calls) || 0]),
  );
  const currentMap = new Map(
    currentItems.map((item) => [String(item.method), Number(item.calls) || 0]),
  );

  const missingMethods = [];
  const reducedCalls = [];
  for (const [method, baselineCalls] of baselineMap.entries()) {
    if (!currentMap.has(method)) {
      missingMethods.push(method);
      continue;
    }
    const currentCalls = currentMap.get(method);
    if (currentCalls < baselineCalls) {
      reducedCalls.push({ method, baselineCalls, currentCalls });
    }
  }

  const ok = missingMethods.length === 0 && reducedCalls.length === 0;
  return {
    ok,
    baselineCount: baselineMap.size,
    currentCount: currentMap.size,
    missingMethods,
    reducedCalls,
    message: ok
      ? `PASS xr-methods: ${currentMap.size} methods`
      : `FAIL xr-methods: missing=${missingMethods.length}, reduced=${reducedCalls.length}`,
  };
}

function compareSummaryCount(metricName, baselineSummary, currentSummary, key) {
  const baselineValue = Number(baselineSummary[key]) || 0;
  const currentValue = Number(currentSummary[key]) || 0;
  const ok = currentValue >= baselineValue;
  return {
    ok,
    metricName,
    key,
    baselineValue,
    currentValue,
    message: ok
      ? `PASS ${metricName}: ${currentValue} >= ${baselineValue}`
      : `FAIL ${metricName}: ${currentValue} < ${baselineValue}`,
  };
}

function main() {
  const args = process.argv.slice(2);
  const reportsDir = path.resolve(
    repoRoot,
    readArgValue(
      args,
      "--reports-dir",
      path.join("copaw", "console_decompiled", "reports"),
    ),
  );
  const baselineDir = path.resolve(
    repoRoot,
    readArgValue(
      args,
      "--baseline-dir",
      path.join("copaw", "console_decompiled", "reports", "baseline"),
    ),
  );

  const requiredFiles = [
    "summary.json",
    "route-paths.json",
    "business-i18n-keys.json",
    "xr-methods.json",
  ];
  for (const fileName of requiredFiles) {
    assertFile(path.join(reportsDir, fileName));
    assertFile(path.join(baselineDir, fileName));
  }

  const currentSummary = readJson(path.join(reportsDir, "summary.json"));
  const baselineSummary = readJson(path.join(baselineDir, "summary.json"));
  const currentRoutes = readJson(path.join(reportsDir, "route-paths.json"));
  const baselineRoutes = readJson(path.join(baselineDir, "route-paths.json"));
  const currentI18nKeys = readJson(
    path.join(reportsDir, "business-i18n-keys.json"),
  );
  const baselineI18nKeys = readJson(
    path.join(baselineDir, "business-i18n-keys.json"),
  );
  const currentXrMethods = readJson(path.join(reportsDir, "xr-methods.json"));
  const baselineXrMethods = readJson(path.join(baselineDir, "xr-methods.json"));

  const checks = [
    compareSetMetric("route-paths", baselineRoutes, currentRoutes),
    compareSetMetric(
      "business-i18n-keys",
      baselineI18nKeys,
      currentI18nKeys,
    ),
    compareXrMethods(baselineXrMethods, currentXrMethods),
    compareSummaryCount(
      "summary.route_path_count",
      baselineSummary,
      currentSummary,
      "route_path_count",
    ),
    compareSummaryCount(
      "summary.business_i18n_key_count",
      baselineSummary,
      currentSummary,
      "business_i18n_key_count",
    ),
    compareSummaryCount(
      "summary.xr_method_count",
      baselineSummary,
      currentSummary,
      "xr_method_count",
    ),
  ];

  let hasFailure = false;
  for (const result of checks) {
    process.stdout.write(`${result.message}\n`);
    if (!result.ok) {
      hasFailure = true;
    }
  }

  const routeCheck = checks[0];
  const i18nCheck = checks[1];
  const xrCheck = checks[2];
  if (!routeCheck.ok && routeCheck.missing.length > 0) {
    process.stdout.write(
      `  missing routes: ${routeCheck.missing.join(", ")}\n`,
    );
  }
  if (!i18nCheck.ok && i18nCheck.missing.length > 0) {
    process.stdout.write(
      `  missing i18n keys (first 20): ${i18nCheck.missing.slice(0, 20).join(", ")}\n`,
    );
  }
  if (!xrCheck.ok) {
    if (xrCheck.missingMethods.length > 0) {
      process.stdout.write(
        `  missing xr methods: ${xrCheck.missingMethods.join(", ")}\n`,
      );
    }
    if (xrCheck.reducedCalls.length > 0) {
      const reduced = xrCheck.reducedCalls
        .map(
          (item) => `${item.method}:${item.baselineCalls}->${item.currentCalls}`,
        )
        .join(", ");
      process.stdout.write(`  reduced xr method calls: ${reduced}\n`);
    }
  }

  if (hasFailure) {
    process.exitCode = 1;
    return;
  }
  process.stdout.write("Coverage regression check passed.\n");
}

main();
