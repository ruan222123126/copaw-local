import { cp, mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const sourceDir = path.join(frontendRoot, "dist");

const targetDir = process.env.COPAW_NEW_CONSOLE_DIR
  ? path.resolve(process.env.COPAW_NEW_CONSOLE_DIR)
  : path.resolve(frontendRoot, "../console/dist");

const ensureSource = async () => {
  try {
    const sourceStat = await stat(sourceDir);
    if (!sourceStat.isDirectory()) {
      throw new Error(`构建产物不存在: ${sourceDir}`);
    }
  } catch (error) {
    throw new Error(
      `请先执行 npm run build，未找到 dist 目录: ${sourceDir}`,
      { cause: error },
    );
  }
};

await ensureSource();
await rm(targetDir, { recursive: true, force: true });
await mkdir(targetDir, { recursive: true });
await cp(sourceDir, targetDir, { recursive: true });

process.stdout.write(`已发布前端产物到: ${targetDir}\n`);
