import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, createSessionId } from "../../api/client";
import type { CronJobSpec, CronJobState } from "../../api/types";
import { useConsoleStore } from "../../store/app-store";
import "./cron-jobs.css";

const sortJobs = (items: CronJobSpec[]): CronJobSpec[] =>
  [...items].sort((a, b) => a.name.localeCompare(b.name));

const formatJson = (value: unknown): string => JSON.stringify(value, null, 2);

const parseCronJobDraft = (draft: string): CronJobSpec => {
  const parsed = JSON.parse(draft) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("任务草稿必须是 JSON 对象。");
  }
  const candidate = parsed as Partial<CronJobSpec>;
  if (typeof candidate.id !== "string") {
    throw new Error("任务草稿缺少 id 字段。");
  }
  if (typeof candidate.name !== "string" || !candidate.name.trim()) {
    throw new Error("任务草稿缺少有效 name 字段。");
  }
  return candidate as CronJobSpec;
};

const createTemplateJob = (channel: string, userId: string): CronJobSpec => ({
  id: "new-job",
  name: "daily-hello",
  enabled: true,
  schedule: {
    type: "cron",
    cron: "0 9 * * *",
    timezone: "UTC",
  },
  task_type: "text",
  text: "你好，这是来自 cron 的测试消息。",
  dispatch: {
    type: "channel",
    channel,
    target: {
      user_id: userId,
      session_id: createSessionId(channel, userId),
    },
    mode: "stream",
    meta: {},
  },
  runtime: {
    max_concurrency: 1,
    timeout_seconds: 120,
    misfire_grace_seconds: 60,
  },
  meta: {},
});

export function CronJobsPage() {
  const userId = useConsoleStore((state) => state.userId) || "default";
  const channel = useConsoleStore((state) => state.channel) || "console";

  const [jobs, setJobs] = useState<CronJobSpec[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [jobState, setJobState] = useState<CronJobState | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectJobFromList = useCallback((jobId: string, nextJobs: CronJobSpec[]) => {
    const target = nextJobs.find((job) => job.id === jobId) ?? null;
    setSelectedJobId(jobId);
    setDraft(target ? formatJson(target) : "");
    setDirty(false);
  }, []);

  const loadJobs = useCallback(
    async (preferredJobId?: string) => {
      setLoading(true);
      setError(null);
      setNotice(null);
      try {
        const list = await apiClient.listCronJobs();
        const sorted = sortJobs(list);
        setJobs(sorted);

        const nextSelected =
          preferredJobId && sorted.some((job) => job.id === preferredJobId)
            ? preferredJobId
            : sorted[0]?.id ?? "";

        if (nextSelected) {
          selectJobFromList(nextSelected, sorted);
        } else {
          setSelectedJobId("");
          setDraft("");
          setDirty(false);
          setJobState(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载定时任务失败");
      } finally {
        setLoading(false);
      }
    },
    [selectJobFromList],
  );

  const loadSelectedState = useCallback(async (jobId: string) => {
    try {
      const state = await apiClient.getCronJobState(jobId);
      setJobState(state);
    } catch (err) {
      setJobState(null);
      setError(err instanceof Error ? err.message : "获取任务状态失败");
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, []);

  useEffect(() => {
    if (!selectedJobId) {
      setJobState(null);
      return;
    }
    void loadSelectedState(selectedJobId);
  }, [loadSelectedState, selectedJobId]);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );

  const selectJob = useCallback(
    (jobId: string) => {
      if (jobId === selectedJobId) {
        return;
      }
      if (dirty) {
        const confirmed = window.confirm("当前任务草稿有未保存改动，确认切换吗？");
        if (!confirmed) {
          return;
        }
      }
      selectJobFromList(jobId, jobs);
      setError(null);
      setNotice(null);
    },
    [dirty, jobs, selectJobFromList, selectedJobId],
  );

  const startFromTemplate = useCallback(() => {
    if (dirty) {
      const confirmed = window.confirm("当前草稿有未保存改动，确认覆盖为模板吗？");
      if (!confirmed) {
        return;
      }
    }
    const template = createTemplateJob(channel, userId);
    setSelectedJobId("");
    setDraft(formatJson(template));
    setDirty(false);
    setJobState(null);
    setNotice("已载入新任务模板。可直接创建。");
    setError(null);
  }, [channel, dirty, userId]);

  const createJob = useCallback(async () => {
    let payload: CronJobSpec;
    try {
      payload = parseCronJobDraft(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "草稿解析失败");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await apiClient.createCronJob(payload);
      setNotice(`任务「${created.name}」创建成功。`);
      await loadJobs(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setSaving(false);
    }
  }, [draft, loadJobs]);

  const saveJob = useCallback(async () => {
    if (!selectedJobId) {
      setError("请先选择一个已有任务再保存。新任务请用“创建任务”。");
      return;
    }

    let payload: CronJobSpec;
    try {
      payload = parseCronJobDraft(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "草稿解析失败");
      return;
    }

    if (payload.id !== selectedJobId) {
      setError("草稿 id 与当前任务不一致，请保持一致后再保存。");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await apiClient.replaceCronJob(selectedJobId, payload);
      setNotice(`任务「${updated.name}」保存成功。`);
      setDirty(false);
      await loadJobs(updated.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存任务失败");
    } finally {
      setSaving(false);
    }
  }, [draft, loadJobs, selectedJobId]);

  const deleteJob = useCallback(async () => {
    if (!selectedJob) {
      setError("请先选择需要删除的任务。");
      return;
    }
    if (!window.confirm(`确认删除任务「${selectedJob.name}」？`)) {
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.deleteCronJob(selectedJob.id);
      if (!result.deleted) {
        setError("删除接口未返回成功状态。");
        return;
      }
      setNotice(`任务「${selectedJob.name}」已删除。`);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除任务失败");
    } finally {
      setSaving(false);
    }
  }, [loadJobs, selectedJob]);

  const runJobAction = useCallback(
    async (
      actionName: string,
      action: (jobId: string) => Promise<unknown>,
      successText: string,
    ) => {
      if (!selectedJobId) {
        setError("请先选择一个任务。");
        return;
      }

      setRunningAction(actionName);
      setError(null);
      setNotice(null);
      try {
        await action(selectedJobId);
        setNotice(successText);
        await loadSelectedState(selectedJobId);
      } catch (err) {
        setError(err instanceof Error ? err.message : `${actionName} 执行失败`);
      } finally {
        setRunningAction(null);
      }
    },
    [loadSelectedState, selectedJobId],
  );

  if (loading) {
    return <p className="cron-muted">Cron Jobs 加载中...</p>;
  }

  return (
    <section className="cron-page">
      <header className="cron-header">
        <div>
          <h2>Cron Jobs</h2>
          <p>管理 `/cron/jobs`，支持创建、编辑、删除、暂停、恢复与手动触发。</p>
        </div>
        <div className="cron-actions">
          <button type="button" onClick={() => void loadJobs(selectedJobId)}>
            刷新列表
          </button>
          <button type="button" onClick={startFromTemplate}>
            新建模板
          </button>
          <button type="button" onClick={() => void createJob()} disabled={saving}>
            创建任务
          </button>
          <button type="button" onClick={() => void saveJob()} disabled={saving}>
            保存任务
          </button>
          <button type="button" className="danger" onClick={() => void deleteJob()}>
            删除任务
          </button>
        </div>
      </header>

      {error ? <p className="cron-error">{error}</p> : null}
      {notice ? <p className="cron-note">{notice}</p> : null}

      <div className="cron-grid">
        <aside className="cron-list-card">
          <h3>任务列表</h3>
          <ul>
            {jobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  className={selectedJobId === job.id ? "active" : ""}
                  onClick={() => selectJob(job.id)}
                >
                  <strong>{job.name}</strong>
                  <span>{job.enabled ? "enabled" : "disabled"}</span>
                  <code>{job.schedule.cron}</code>
                </button>
              </li>
            ))}
          </ul>

          <div className="cron-job-ops">
            <button
              type="button"
              onClick={() =>
                void runJobAction("pause", apiClient.pauseCronJob, "任务已暂停。")
              }
              disabled={!selectedJobId || runningAction !== null}
            >
              暂停
            </button>
            <button
              type="button"
              onClick={() =>
                void runJobAction("resume", apiClient.resumeCronJob, "任务已恢复。")
              }
              disabled={!selectedJobId || runningAction !== null}
            >
              恢复
            </button>
            <button
              type="button"
              onClick={() =>
                void runJobAction("run", apiClient.runCronJob, "任务已触发执行。")
              }
              disabled={!selectedJobId || runningAction !== null}
            >
              立即执行
            </button>
          </div>
        </aside>

        <section className="cron-editor-card">
          <header>
            <h3>{selectedJob?.name ?? "新任务草稿"}</h3>
            <p>
              当前草稿{dirty ? "有" : "无"}
              未保存改动。
            </p>
          </header>

          <textarea
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setDirty(true);
            }}
            placeholder="编辑 CronJobSpec JSON"
          />

          <section className="cron-state-card">
            <header>
              <strong>任务状态</strong>
              <button
                type="button"
                onClick={() =>
                  selectedJobId ? void loadSelectedState(selectedJobId) : undefined
                }
                disabled={!selectedJobId}
              >
                刷新状态
              </button>
            </header>
            {jobState ? (
              <ul>
                <li>
                  next_run_at: <code>{jobState.next_run_at ?? "-"}</code>
                </li>
                <li>
                  last_run_at: <code>{jobState.last_run_at ?? "-"}</code>
                </li>
                <li>
                  last_status: <code>{jobState.last_status ?? "-"}</code>
                </li>
                <li>
                  last_error: <code>{jobState.last_error ?? "-"}</code>
                </li>
              </ul>
            ) : (
              <p className="cron-muted">暂无状态信息。</p>
            )}
          </section>
        </section>
      </div>
    </section>
  );
}
