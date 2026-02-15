import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ConsoleState {
  userId: string;
  channel: string;
  activeChatId: string | null;
  setUserId: (value: string) => void;
  setChannel: (value: string) => void;
  setActiveChatId: (value: string | null) => void;
}

export const useConsoleStore = create<ConsoleState>()(
  persist(
    (set) => ({
      userId: "default",
      channel: "console",
      activeChatId: null,
      setUserId: (value) => set({ userId: value }),
      setChannel: (value) => set({ channel: value }),
      setActiveChatId: (value) => set({ activeChatId: value }),
    }),
    {
      name: "copaw-console-v2",
    },
  ),
);
