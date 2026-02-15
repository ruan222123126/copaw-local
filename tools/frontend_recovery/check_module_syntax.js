#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..", "..");

function readArgValue(args, name, defaultValue) {
  const index = args.indexOf(name);
  if (index === -1 || index + 1 >= args.length) {
    return defaultValue;
  }
  return args[index + 1];
}

function walkFiles(rootDir) {
  const files = [];
  const stack = [rootDir];
  while (stack.length > 0) {
    const current = stack.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
        continue;
      }
      files.push(fullPath);
    }
  }
  return files;
}

function main() {
  const args = process.argv.slice(2);
  const modulesDir = path.resolve(
    repoRoot,
    readArgValue(
      args,
      "--modules-dir",
      path.join("copaw", "console_decompiled", "modules"),
    ),
  );
  if (!fs.existsSync(modulesDir)) {
    throw new Error(`模块目录不存在: ${path.relative(repoRoot, modulesDir)}`);
  }

  const candidateFiles = walkFiles(modulesDir)
    .filter((filePath) => /\.(js|ts|tsx)$/.test(filePath))
    .sort();

  if (candidateFiles.length === 0) {
    throw new Error(`未找到可校验文件: ${path.relative(repoRoot, modulesDir)}`);
  }

  const tempOutDir = fs.mkdtempSync(
    path.join(os.tmpdir(), "copaw-frontend-syntax-"),
  );
  try {
    const commandArgs = [
      "-y",
      "-p",
      "esbuild",
      "esbuild",
      ...candidateFiles.map((filePath) => path.relative(repoRoot, filePath)),
      `--outdir=${tempOutDir}`,
      "--format=esm",
      "--log-level=error",
      "--loader:.js=js",
      "--loader:.ts=ts",
      "--loader:.tsx=tsx",
    ];

    const result = spawnSync("npx", commandArgs, {
      cwd: repoRoot,
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
    });

    if (result.status !== 0) {
      const message = (result.stderr || result.stdout || "").trim();
      throw new Error(
        `模块语法校验失败（esbuild）:\n${message || "无错误输出"}`,
      );
    }

    process.stdout.write(
      `Syntax check passed: ${candidateFiles.length} files in ${path.relative(repoRoot, modulesDir)}\n`,
    );
  } finally {
    fs.rmSync(tempOutDir, { recursive: true, force: true });
  }
}

main();
