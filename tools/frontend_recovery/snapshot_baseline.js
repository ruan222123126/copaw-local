#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readArgValue(args, name, defaultValue) {
  const index = args.indexOf(name);
  if (index === -1 || index + 1 >= args.length) {
    return defaultValue;
  }
  return args[index + 1];
}

function hasFlag(args, name) {
  return args.includes(name);
}

function copyWithGuard(src, dst, force) {
  if (!fs.existsSync(src)) {
    throw new Error(`报告文件不存在: ${path.relative(repoRoot, src)}`);
  }
  if (!force && fs.existsSync(dst)) {
    throw new Error(
      `基线文件已存在，若要覆盖请加 --force: ${path.relative(repoRoot, dst)}`,
    );
  }
  ensureDir(path.dirname(dst));
  fs.copyFileSync(src, dst);
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
  const force = hasFlag(args, "--force");

  const files = [
    "summary.json",
    "route-paths.json",
    "business-i18n-keys.json",
    "xr-methods.json",
  ];

  for (const fileName of files) {
    const src = path.join(reportsDir, fileName);
    const dst = path.join(baselineDir, fileName);
    copyWithGuard(src, dst, force);
  }

  process.stdout.write(
    `Done. baseline snapshot: ${path.relative(repoRoot, baselineDir)}\n`,
  );
}

main();
