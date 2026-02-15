import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";

export const usePushMessages = (sessionId?: string) => {
  const [messages, setMessages] = useState<Array<Record<string, unknown>>>([]);

  const load = useCallback(async () => {
    try {
      const response = await apiClient.getPushMessages(sessionId);
      if (response.messages.length === 0) {
        return;
      }
      setMessages((prev) => {
        const merged = [...response.messages, ...prev];
        return merged.slice(0, 20);
      });
    } catch {
      // Push 是辅助能力，不中断主流程。
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [load]);

  return {
    messages,
    clear: () => setMessages([]),
  };
};
