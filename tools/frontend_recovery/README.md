# Frontend Recovery

这个目录用于把 `copaw/console/assets` 的打包产物做分阶段恢复，不改动原始前端文件。

## 阶段一：可读化与结构报告

- 全量复制 `assets/*.js` 到 `copaw/console_decompiled/original/`
- 生成格式化版本到 `copaw/console_decompiled/pretty/`
- 生成结构报告到 `copaw/console_decompiled/reports/`
  - `summary.json`
  - `map-deps.json`
  - `dynamic-imports.json`
  - `export-aliases.json`
  - `xr-methods.json`
  - `route-paths.json`
  - `business-i18n-keys.json`
  - `snippet-markers.json`
- 尝试抽取可读片段到 `copaw/console_decompiled/snippets/`
  - `i18n-block.js`
  - `runtime-config-block.js`
  - `xr-api-block.js`
  - `session-store-block.js`
  - `router-block.js`

## 阶段二：模块化重建（语义恢复 + 可运行化命名整理）

根据阶段一的 `snippets` + `reports`，重建可维护目录：

- `copaw/console_decompiled/modules/api/`
- `copaw/console_decompiled/modules/hooks/`
- `copaw/console_decompiled/modules/pages/`
- `copaw/console_decompiled/modules/i18n/`
- `copaw/console_decompiled/modules/router/`

核心产物：

- `modules/api/xr.ts`（从 `xr-api-block.js` 拆分）
- `modules/hooks/session-store.js`
- `modules/router/routes.ts`
- `modules/i18n/resources.js`
- `modules/manifest.json`

## 一致性回归校验

- 基线快照：`copaw/console_decompiled/reports/baseline/*.json`
- 校验目标：`route-paths.json`、`business-i18n-keys.json`、`xr-methods.json` 不回退

## 使用方法

在仓库根目录执行：

```bash
node tools/frontend_recovery/recover_frontend.js
node tools/frontend_recovery/rebuild_phase2_modules.js
node tools/frontend_recovery/check_module_syntax.js
```

首次建立基线（已有基线会报错，覆盖请加 `--force`）：

```bash
node tools/frontend_recovery/snapshot_baseline.js
```

执行覆盖率不回退校验：

```bash
node tools/frontend_recovery/check_coverage_regression.js
```

更新基线（显式覆盖）：

```bash
node tools/frontend_recovery/snapshot_baseline.js --force
```

## 仓库策略

- `copaw/console_decompiled/original/` 与 `copaw/console_decompiled/pretty/` 已加入 `.gitignore`
- 仅建议提交 `reports/`、`snippets/`、`modules/` 及 `tools/frontend_recovery/*`

## 说明

- 当前目标是“语义可读恢复 + 可运行化命名整理 + 可重复生成”，不是直接恢复原始 TS/Vue 工程。
- 由于没有 source map，变量命名和模块边界存在近似误差，仍需要后续业务回归测试。
