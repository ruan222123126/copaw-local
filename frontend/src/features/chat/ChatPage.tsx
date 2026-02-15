import { useCallback, useEffect, useMemo, useState } from "react";
import {
  apiClient,
  createSessionId,
  createUserTextContent,
  type CreateChatRequest,
} from "../../api/client";
import type { ChatSpec, RuntimeMessage } from "../../api/types";
import { usePushMessages } from "../../hooks/usePushMessages";
import { useConsoleStore } from "../../store/app-store";
import { runtimeMessageToText } from "../../utils/messages";
import "./chat.css";

const sortChats = (items: ChatSpec[]): ChatSpec[] =>
  [...items].sort(
    (a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

export function ChatPage() {
  const userId = useConsoleStore((s) => s.userId);
  const channel = useConsoleStore((s) => s.channel);
  const activeChatId = useConsoleStore((s) => s.activeChatId);
  const setActiveChatId = useConsoleStore((s) => s.setActiveChatId);

  const [chats, setChats] = useState<ChatSpec[]>([]);
  const [history, setHistory] = useState<RuntimeMessage[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? null,
    [chats, activeChatId],
  );

  const { messages: pushMessages, clear: clearPushMessages } = usePushMessages(
    activeChat?.session_id,
  );

  const loadChats = useCallback(async () => {
    setLoadingChats(true);
    setError(null);
    try {
      const list = await apiClient.listChats({ user_id: userId, channel });
      const sorted = sortChats(list);
      setChats(sorted);
      if (!sorted.length) {
        setActiveChatId(null);
        return;
      }
      if (!activeChatId || !sorted.some((chat) => chat.id === activeChatId)) {
        setActiveChatId(sorted[0].id);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载会话失败";
      setError(message);
    } finally {
      setLoadingChats(false);
    }
  }, [userId, channel, activeChatId, setActiveChatId]);

  const loadHistory = useCallback(
    async (chatId: string, silent = false) => {
      if (!silent) {
        setLoadingHistory(true);
      }
      try {
        const detail = await apiClient.getChatHistory(chatId);
        setHistory(detail.messages ?? []);
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载消息失败";
        setError(message);
      } finally {
        if (!silent) {
          setLoadingHistory(false);
        }
      }
    },
    [],
  );

  const createNewChat = useCallback(async (): Promise<ChatSpec | null> => {
    const payload: CreateChatRequest = {
      name: "New Chat",
      session_id: createSessionId(channel, userId),
      user_id: userId,
      channel,
      meta: {},
    };
    try {
      const created = await apiClient.createChat(payload);
      setChats((prev) => sortChats([created, ...prev]));
      setActiveChatId(created.id);
      return created;
    } catch (err) {
      const message = err instanceof Error ? err.message : "创建会话失败";
      setError(message);
      return null;
    }
  }, [channel, userId, setActiveChatId]);

  const ensureActiveChat = useCallback(async (): Promise<ChatSpec | null> => {
    if (activeChat) {
      return activeChat;
    }
    return createNewChat();
  }, [activeChat, createNewChat]);

  const deleteChat = useCallback(
    async (chat: ChatSpec) => {
      if (!window.confirm(`确认删除会话：${chat.name}？`)) {
        return;
      }
      try {
        await apiClient.deleteChat(chat.id);
        setChats((prev) => prev.filter((item) => item.id !== chat.id));
        if (activeChatId === chat.id) {
          setActiveChatId(null);
          setHistory([]);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除会话失败";
        setError(message);
      }
    },
    [activeChatId, setActiveChatId],
  );

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending) {
      return;
    }

    const chat = await ensureActiveChat();
    if (!chat) {
      return;
    }

    setDraft("");
    setError(null);
    setSending(true);

    const optimisticMessage: RuntimeMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: [createUserTextContent(text)],
    };
    setHistory((prev) => [...prev, optimisticMessage]);

    const pollTimer = window.setInterval(() => {
      void loadHistory(chat.id, true);
    }, 1500);
    const streamAssistantId = `stream-assistant-${Date.now()}`;
    let hasStreamChunk = false;
    let streamedText = "";

    try {
      await apiClient.sendAgentMessage({
        input: [
          {
            role: "user",
            type: "message",
            content: [createUserTextContent(text)],
          },
        ],
        session_id: chat.session_id,
        user_id: userId,
        channel,
        stream: true,
      }, (chunk) => {
        if (!chunk) {
          return;
        }
        streamedText += chunk;
        if (!hasStreamChunk) {
          hasStreamChunk = true;
          window.clearInterval(pollTimer);
        }
        setHistory((prev) => {
          const assistantDraft: RuntimeMessage = {
            id: streamAssistantId,
            role: "assistant",
            content: [createUserTextContent(streamedText)],
          };
          const index = prev.findIndex(
            (message) => message.id === streamAssistantId,
          );
          if (index === -1) {
            return [...prev, assistantDraft];
          }
          const next = [...prev];
          next[index] = assistantDraft;
          return next;
        });
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "发送失败";
      setError(message);
    } finally {
      window.clearInterval(pollTimer);
      setSending(false);
      await loadChats();
      await loadHistory(chat.id);
    }
  }, [
    draft,
    sending,
    ensureActiveChat,
    loadChats,
    loadHistory,
    userId,
    channel,
  ]);

  useEffect(() => {
    void loadChats();
  }, [loadChats]);

  useEffect(() => {
    if (!activeChatId) {
      setHistory([]);
      return;
    }
    void loadHistory(activeChatId);
  }, [activeChatId, loadHistory]);

  return (
    <section className="chat-grid">
      <aside className="chat-sessions">
        <div className="chat-sessions-header">
          <h2>会话</h2>
          <button type="button" onClick={() => void createNewChat()}>
            新建
          </button>
        </div>
        {loadingChats ? <p className="chat-hint">会话加载中...</p> : null}
        <ul className="chat-session-list">
          {chats.map((chat) => {
            const selected = chat.id === activeChatId;
            return (
              <li key={chat.id} className={selected ? "is-active" : ""}>
                <button
                  type="button"
                  className="chat-session-main"
                  onClick={() => setActiveChatId(chat.id)}
                >
                  <strong>{chat.name || "未命名会话"}</strong>
                  <span>{new Date(chat.updated_at).toLocaleString()}</span>
                </button>
                <button
                  type="button"
                  className="chat-session-delete"
                  onClick={() => void deleteChat(chat)}
                  aria-label={`删除会话 ${chat.name}`}
                >
                  删除
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      <div className="chat-main">
        <header className="chat-main-header">
          <div>
            <h2>{activeChat?.name ?? "未选择会话"}</h2>
            <p>
              session_id: <code>{activeChat?.session_id ?? "-"}</code>
            </p>
          </div>
          {sending ? <span className="chat-status">正在生成回复...</span> : null}
        </header>

        {pushMessages.length > 0 ? (
          <section className="push-panel" aria-live="polite">
            <div className="push-header">
              <strong>实时推送</strong>
              <button type="button" onClick={clearPushMessages}>
                清空
              </button>
            </div>
            <ul>
              {pushMessages.slice(0, 5).map((message, index) => (
                <li key={`push-${index}`}>
                  <code>{JSON.stringify(message)}</code>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <div className="chat-timeline">
          {loadingHistory ? <p className="chat-hint">消息加载中...</p> : null}
          {!loadingHistory && history.length === 0 ? (
            <p className="chat-hint">发送第一条消息开始对话。</p>
          ) : null}
          {history.map((message, index) => {
            const role = message.role ?? "assistant";
            const text = runtimeMessageToText(message) || "[空消息]";
            return (
              <article key={message.id ?? `${role}-${index}`} className={`msg msg-${role}`}>
                <header>{role}</header>
                <pre>{text}</pre>
              </article>
            );
          })}
        </div>

        <footer className="chat-composer">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="输入消息，按 Enter 发送，Shift+Enter 换行"
            disabled={sending}
          />
          <button
            type="button"
            onClick={() => void sendMessage()}
            disabled={sending || !draft.trim()}
          >
            发送
          </button>
        </footer>

        {error ? <p className="chat-error">{error}</p> : null}
      </div>
    </section>
  );
}
