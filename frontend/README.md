# CoPaw 新前端（React + Vite）

## 目标

该目录提供可维护的新前端工程，用于替换当前 `copaw/console` 的静态产物模式。

## 本地开发

```bash
cd frontend
npm install
npm run dev
```

默认同源请求 API。若前端和后端端口不同，可设置：

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

## 构建

```bash
cd frontend
npm run build
```

构建结果在 `frontend/dist`。

## 灰度切换

后端支持通过 `COPAW_CONSOLE_STATIC_DIR` 指向新前端目录：

```bash
export COPAW_CONSOLE_STATIC_DIR=/绝对路径/copaw-local/frontend/dist
```

启动后端后，`/` 会直接加载新前端。

## 发布到 `console/dist`

```bash
cd frontend
npm run build
npm run deploy:console
```

默认发布到仓库根目录的 `console/dist`。可用 `COPAW_NEW_CONSOLE_DIR` 覆盖目标目录。
