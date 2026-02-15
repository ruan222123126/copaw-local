import { useCallback, useMemo, useState } from "react";
import { apiClient } from "../../api/client";
import type { JsonObject } from "../../api/types";
import "./agents.css";

type AgentSnapshotKey = "root" | "health" | "status" | "shutdown";

const formatPayload = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

export function AgentsPage() {
  const [snapshots, setSnapshots] = useState<Record<AgentSnapshotKey, JsonObject | null>>({
    root: null,
    health: null,
    status: null,
    shutdown: null,
  });
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const runAction = useCallback(
    async (
      actionName: string,
      snapshotKey: AgentSnapshotKey,
      action: () => Promise<JsonObject>,
      successMessage: string,
    ) => {
      setRunningAction(actionName);
      setError(null);
      setNotice(null);
      try {
        const result = await action();
        setSnapshots((prev) => ({
          ...prev,
          [snapshotKey]: result,
        }));
        setNotice(successMessage);
      } catch (err) {
        setError(err instanceof Error ? err.message : `${actionName} 执行失败`);
      } finally {
        setRunningAction(null);
      }
    },
    [],
  );

  const inspectRoot = useCallback(async () => {
    await runAction("root", "root", apiClient.agentRoot, "已获取 /agent/ 返回。");
  }, [runAction]);

  const inspectHealth = useCallback(async () => {
    await runAction(
      "health",
      "health",
      apiClient.agentHealthCheck,
      "已获取 /agent/health 返回。",
    );
  }, [runAction]);

  const inspectStatus = useCallback(async () => {
    await runAction(
      "status",
      "status",
      apiClient.getAgentProcessStatus,
      "已获取 /agent/admin/status 返回。",
    );
  }, [runAction]);

  const shutdownSimple = useCallback(async () => {
    if (!window.confirm("确认调用 /agent/shutdown 吗？该操作可能终止当前服务。")) {
      return;
    }
    await runAction(
      "shutdown-simple",
      "shutdown",
      apiClient.shutdownAgentSimple,
      "已发送 shutdown 请求。",
    );
  }, [runAction]);

  const shutdownAdmin = useCallback(async () => {
    if (!window.confirm("确认调用 /agent/admin/shutdown 吗？该操作可能终止当前服务。")) {
      return;
    }
    await runAction(
      "shutdown-admin",
      "shutdown",
      apiClient.shutdownAgentAdmin,
      "已发送 admin shutdown 请求。",
    );
  }, [runAction]);

  const panels = useMemo(
    () => [
      {
        title: "Agent Root",
        description: "检查 /agent/ 基础信息",
        key: "root" as AgentSnapshotKey,
      },
      {
        title: "Health",
        description: "检查 /agent/health",
        key: "health" as AgentSnapshotKey,
      },
      {
        title: "Process Status",
        description: "检查 /agent/admin/status",
        key: "status" as AgentSnapshotKey,
      },
      {
        title: "Shutdown Result",
        description: "最近一次 shutdown 调用响应",
        key: "shutdown" as AgentSnapshotKey,
      },
    ],
    [],
  );

  return (
    <section className="agents-page">
      <header className="agents-header">
        <div>
          <h2>Agents</h2>
          <p>检查 Agent 运行状态，并提供受确认保护的 shutdown 操作。</p>
        </div>
        <div className="agents-actions">
          <button
            type="button"
            onClick={() => void inspectRoot()}
            disabled={runningAction !== null}
          >
            检查 Root
          </button>
          <button
            type="button"
            onClick={() => void inspectHealth()}
            disabled={runningAction !== null}
          >
            检查 Health
          </button>
          <button
            type="button"
            onClick={() => void inspectStatus()}
            disabled={runningAction !== null}
          >
            检查 Status
          </button>
        </div>
      </header>

      {error ? <p className="agents-error">{error}</p> : null}
      {notice ? <p className="agents-note">{notice}</p> : null}

      <section className="agents-shutdown-card">
        <h3>危险操作</h3>
        <p>这两个操作会尝试关闭当前 Agent 服务，执行前会二次确认。</p>
        <div>
          <button
            type="button"
            className="danger"
            onClick={() => void shutdownSimple()}
            disabled={runningAction !== null}
          >
            POST /agent/shutdown
          </button>
          <button
            type="button"
            className="danger"
            onClick={() => void shutdownAdmin()}
            disabled={runningAction !== null}
          >
            POST /agent/admin/shutdown
          </button>
        </div>
      </section>

      <div className="agents-grid">
        {panels.map((panel) => (
          <article key={panel.key} className="agents-card">
            <header>
              <h3>{panel.title}</h3>
              <p>{panel.description}</p>
            </header>
            <pre>{snapshots[panel.key] ? formatPayload(snapshots[panel.key]) : "暂无数据"}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}
