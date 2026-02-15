import { useCallback, useEffect, useMemo, useState } from "react";
import {
  apiClient,
  createSessionId,
  type CreateChatRequest,
} from "../../api/client";
import type { ChatSpec, RuntimeMessage } from "../../api/types";
import { useConsoleStore } from "../../store/app-store";
import { runtimeMessageToText } from "../../utils/messages";
import "./sessions.css";

const sortChats = (items: ChatSpec[]): ChatSpec[] =>
  [...items].sort(
    (a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

const normalizeKeyword = (value: string): string => value.trim().toLowerCase();

export function SessionsPage() {
  const storeUserId = useConsoleStore((state) => state.userId);
  const storeChannel = useConsoleStore((state) => state.channel);

  const [filterUserId, setFilterUserId] = useState(storeUserId);
  const [filterChannel, setFilterChannel] = useState(storeChannel);
  const [keyword, setKeyword] = useState("");
  const [newSessionName, setNewSessionName] = useState("");

  const [sessions, setSessions] = useState<ChatSpec[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const [history, setHistory] = useState<RuntimeMessage[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadSessions = useCallback(
    async (preferredId?: string) => {
      setLoading(true);
      setError(null);
      setNotice(null);
      try {
        const list = await apiClient.listChats({
          user_id: filterUserId.trim() || undefined,
          channel: filterChannel.trim() || undefined,
        });
        const sorted = sortChats(list);
        setSessions(sorted);

        const nextSelected =
          preferredId && sorted.some((item) => item.id === preferredId)
            ? preferredId
            : sorted[0]?.id ?? "";

        setSelectedSessionId(nextSelected);
        setCheckedIds((prev) => prev.filter((id) => sorted.some((item) => item.id === id)));
        if (!nextSelected) {
          setHistory([]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载会话失败");
      } finally {
        setLoading(false);
      }
    },
    [filterChannel, filterUserId],
  );

  const loadHistory = useCallback(async (chatId: string) => {
    setLoadingHistory(true);
    setError(null);
    try {
      const detail = await apiClient.getChatHistory(chatId);
      setHistory(detail.messages ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载会话历史失败");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      setHistory([]);
      return;
    }
    void loadHistory(selectedSessionId);
  }, [loadHistory, selectedSessionId]);

  const visibleSessions = useMemo(() => {
    const normalized = normalizeKeyword(keyword);
    if (!normalized) {
      return sessions;
    }
    return sessions.filter((session) => {
      const target = `${session.name} ${session.id} ${session.session_id}`.toLowerCase();
      return target.includes(normalized);
    });
  }, [keyword, sessions]);

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );

  const toggleChecked = useCallback((chatId: string, checked: boolean) => {
    setCheckedIds((prev) => {
      if (checked) {
        if (prev.includes(chatId)) {
          return prev;
        }
        return [...prev, chatId];
      }
      return prev.filter((id) => id !== chatId);
    });
  }, []);

  const toggleSelectAllVisible = useCallback(() => {
    const visibleIds = visibleSessions.map((session) => session.id);
    const allVisibleChecked =
      visibleIds.length > 0 && visibleIds.every((id) => checkedIds.includes(id));

    if (allVisibleChecked) {
      setCheckedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
      return;
    }

    setCheckedIds((prev) => {
      const merged = new Set(prev);
      for (const id of visibleIds) {
        merged.add(id);
      }
      return Array.from(merged);
    });
  }, [checkedIds, visibleSessions]);

  const createSession = useCallback(async () => {
    const userId = filterUserId.trim() || storeUserId || "default";
    const channel = filterChannel.trim() || storeChannel || "console";
    const payload: CreateChatRequest = {
      name: newSessionName.trim() || "New Chat",
      session_id: createSessionId(channel, userId),
      user_id: userId,
      channel,
      meta: {},
    };

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await apiClient.createChat(payload);
      setNewSessionName("");
      setNotice(`会话「${created.name}」创建成功。`);
      await loadSessions(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建会话失败");
    } finally {
      setSaving(false);
    }
  }, [filterChannel, filterUserId, loadSessions, newSessionName, storeChannel, storeUserId]);

  const deleteOneSession = useCallback(
    async (session: ChatSpec) => {
      if (!window.confirm(`确认删除会话「${session.name}」？`)) {
        return;
      }
      setSaving(true);
      setError(null);
      setNotice(null);
      try {
        await apiClient.deleteChat(session.id);
        setNotice(`会话「${session.name}」已删除。`);
        await loadSessions();
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除会话失败");
      } finally {
        setSaving(false);
      }
    },
    [loadSessions],
  );

  const batchDelete = useCallback(async () => {
    if (checkedIds.length === 0) {
      setError("请先勾选需要删除的会话。");
      return;
    }
    if (!window.confirm(`确认删除选中的 ${checkedIds.length} 个会话？`)) {
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.batchDeleteChats(checkedIds);
      if (!result.deleted) {
        setError("批量删除返回失败。请重试。");
        return;
      }
      setCheckedIds([]);
      setNotice(`已删除 ${checkedIds.length} 个会话。`);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量删除会话失败");
    } finally {
      setSaving(false);
    }
  }, [checkedIds, loadSessions]);

  const allVisibleChecked =
    visibleSessions.length > 0 &&
    visibleSessions.every((session) => checkedIds.includes(session.id));

  if (loading) {
    return <p className="sessions-muted">Sessions 加载中...</p>;
  }

  return (
    <section className="sessions-page">
      <header className="sessions-header">
        <div>
          <h2>Sessions</h2>
          <p>管理会话列表、筛选条件与历史记录预览。</p>
        </div>
        <div className="sessions-header-actions">
          <button type="button" onClick={() => void loadSessions(selectedSessionId)}>
            刷新
          </button>
          <button type="button" onClick={() => void batchDelete()} disabled={saving}>
            批量删除
          </button>
        </div>
      </header>

      {error ? <p className="sessions-error">{error}</p> : null}
      {notice ? <p className="sessions-note">{notice}</p> : null}

      <section className="sessions-filters-card">
        <label>
          user_id
          <input
            value={filterUserId}
            onChange={(event) => setFilterUserId(event.target.value)}
            placeholder="default"
          />
        </label>
        <label>
          channel
          <input
            value={filterChannel}
            onChange={(event) => setFilterChannel(event.target.value)}
            placeholder="console"
          />
        </label>
        <label>
          关键字
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="按名称 / id / session_id 搜索"
          />
        </label>
        <button type="button" onClick={() => void loadSessions()}>
          应用筛选
        </button>
      </section>

      <section className="sessions-create-card">
        <label>
          新会话名称
          <input
            value={newSessionName}
            onChange={(event) => setNewSessionName(event.target.value)}
            placeholder="可留空，默认 New Chat"
          />
        </label>
        <button type="button" onClick={() => void createSession()} disabled={saving}>
          {saving ? "处理中..." : "创建会话"}
        </button>
      </section>

      <div className="sessions-grid">
        <aside className="sessions-list-card">
          <header>
            <h3>会话列表</h3>
            <button type="button" onClick={toggleSelectAllVisible}>
              {allVisibleChecked ? "取消全选" : "全选当前筛选"}
            </button>
          </header>
          <ul>
            {visibleSessions.map((session) => {
              const checked = checkedIds.includes(session.id);
              const selected = session.id === selectedSessionId;
              return (
                <li key={session.id} className={selected ? "active" : ""}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      toggleChecked(session.id, event.target.checked)
                    }
                    aria-label={`勾选会话 ${session.name}`}
                  />
                  <button
                    type="button"
                    className="session-main"
                    onClick={() => setSelectedSessionId(session.id)}
                  >
                    <strong>{session.name || "未命名会话"}</strong>
                    <span>{new Date(session.updated_at).toLocaleString()}</span>
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => void deleteOneSession(session)}
                  >
                    删除
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="sessions-history-card">
          <header>
            <h3>{selectedSession?.name ?? "未选择会话"}</h3>
            <p>
              chat_id: <code>{selectedSession?.id ?? "-"}</code>
            </p>
            <p>
              session_id: <code>{selectedSession?.session_id ?? "-"}</code>
            </p>
          </header>

          <div className="sessions-history-body">
            {loadingHistory ? <p className="sessions-muted">历史加载中...</p> : null}
            {!loadingHistory && history.length === 0 ? (
              <p className="sessions-muted">该会话暂无历史消息。</p>
            ) : null}
            {history.map((message, index) => {
              const role = message.role ?? "assistant";
              const text = runtimeMessageToText(message) || "[空消息]";
              return (
                <article key={message.id ?? `${role}-${index}`} className={`record ${role}`}>
                  <header>{role}</header>
                  <pre>{text}</pre>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </section>
  );
}
