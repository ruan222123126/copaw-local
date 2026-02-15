import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import type { EnvVar } from "../../api/types";
import "./environments.css";

interface EnvDraft {
  id: string;
  key: string;
  value: string;
}

let rowSeq = 0;
const createRowId = (): string => {
  rowSeq += 1;
  return `env-row-${Date.now()}-${rowSeq}`;
};

const toDrafts = (items: EnvVar[]): EnvDraft[] =>
  items.map((item) => ({
    id: createRowId(),
    key: item.key,
    value: item.value,
  }));

export function EnvironmentsPage() {
  const [rows, setRows] = useState<EnvDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadEnvs = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const envs = await apiClient.listEnvs();
      setRows(toDrafts(envs));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载环境变量失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadEnvs();
  }, [loadEnvs]);

  const updateRow = useCallback(
    (id: string, patch: Partial<Omit<EnvDraft, "id">>) => {
      setRows((prev) =>
        prev.map((row) => (row.id === id ? { ...row, ...patch } : row)),
      );
    },
    [],
  );

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, { id: createRowId(), key: "", value: "" }]);
  }, []);

  const removeRow = useCallback((id: string) => {
    setRows((prev) => prev.filter((row) => row.id !== id));
  }, []);

  const saveAll = useCallback(async () => {
    const payload: Record<string, string> = {};
    const duplicateCheck = new Set<string>();

    for (const row of rows) {
      const key = row.key.trim();
      const value = row.value;
      if (!key && !value.trim()) {
        continue;
      }
      if (!key) {
        setError("存在空 key 且 value 不为空的行，请修正后再保存。");
        return;
      }
      if (duplicateCheck.has(key)) {
        setError(`检测到重复 key：${key}`);
        return;
      }
      duplicateCheck.add(key);
      payload[key] = value;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await apiClient.saveEnvs(payload);
      setRows(toDrafts(saved));
      setNotice(`环境变量保存成功，共 ${saved.length} 项。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存环境变量失败");
    } finally {
      setSaving(false);
    }
  }, [rows]);

  if (loading) {
    return <p className="envs-muted">环境变量加载中...</p>;
  }

  return (
    <section className="envs-page">
      <header className="envs-header">
        <div>
          <h2>Environments</h2>
          <p>
            编辑后点击“保存全部”会覆盖服务端 <code>envs.json</code>。
          </p>
        </div>
        <div className="envs-actions">
          <button type="button" onClick={addRow}>
            新增一行
          </button>
          <button type="button" onClick={() => void loadEnvs()}>
            从服务端刷新
          </button>
          <button type="button" onClick={() => void saveAll()} disabled={saving}>
            {saving ? "保存中..." : "保存全部"}
          </button>
        </div>
      </header>

      {error ? <p className="envs-error">{error}</p> : null}
      {notice ? <p className="envs-note">{notice}</p> : null}

      <section className="envs-card">
        {rows.length === 0 ? (
          <p className="envs-muted">暂无环境变量，点“新增一行”开始配置。</p>
        ) : (
          <div className="envs-grid">
            <div className="envs-grid-head">Key</div>
            <div className="envs-grid-head">Value</div>
            <div className="envs-grid-head">操作</div>

            {rows.map((row) => (
              <div className="envs-grid-row" key={row.id}>
                <input
                  value={row.key}
                  onChange={(event) =>
                    updateRow(row.id, { key: event.target.value })
                  }
                  placeholder="如 OPENAI_API_KEY"
                />
                <input
                  value={row.value}
                  onChange={(event) =>
                    updateRow(row.id, { value: event.target.value })
                  }
                  placeholder="变量值"
                />
                <button
                  type="button"
                  className="danger"
                  onClick={() => removeRow(row.id)}
                >
                  移除
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
