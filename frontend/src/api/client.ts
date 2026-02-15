import { requestJson, requestStream } from "./http";
import type {
  ActiveModelsInfo,
  AgentProcessRequest,
  ChannelConfigMap,
  ChannelType,
  ChatHistory,
  ChatSpec,
  CronJobSpec,
  CronJobState,
  CronJobView,
  EnvVar,
  JsonObject,
  MdFileInfo,
  ModelSlotConfig,
  ProviderInfo,
  PushMessageResponse,
  SkillSpec,
  RuntimeContent,
} from "./types";

export interface ChatFilter {
  user_id?: string;
  channel?: string;
}

export interface CreateChatRequest {
  name?: string;
  session_id: string;
  user_id: string;
  channel: string;
  meta?: Record<string, unknown>;
}

type StreamTextHandler = (text: string) => void;

const extractDeltaText = (payload: unknown): string => {
  if (!payload || typeof payload !== "object") {
    return "";
  }
  const record = payload as Record<string, unknown>;

  if (typeof record.delta === "string") {
    return record.delta;
  }
  if (record.delta && typeof record.delta === "object") {
    const delta = record.delta as Record<string, unknown>;
    if (typeof delta.text === "string") {
      return delta.text;
    }
    if (typeof delta.content === "string") {
      return delta.content;
    }
  }
  if (typeof record.text_delta === "string") {
    return record.text_delta;
  }
  if (typeof record.token === "string") {
    return record.token;
  }
  if (Array.isArray(record.choices)) {
    let text = "";
    for (const choice of record.choices) {
      if (!choice || typeof choice !== "object") {
        continue;
      }
      const delta = (choice as Record<string, unknown>).delta;
      if (delta && typeof delta === "object") {
        const content = (delta as Record<string, unknown>).content;
        if (typeof content === "string") {
          text += content;
        }
      }
    }
    return text;
  }

  return "";
};

const parseStreamLine = (
  line: string,
  onTextChunk?: StreamTextHandler,
): void => {
  if (!onTextChunk) {
    return;
  }
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("event:")) {
    return;
  }

  const rawPayload = trimmed.startsWith("data:")
    ? trimmed.slice(5).trim()
    : trimmed;

  if (!rawPayload || rawPayload === "[DONE]") {
    return;
  }

  try {
    const parsed = JSON.parse(rawPayload) as unknown;
    const delta = extractDeltaText(parsed);
    if (delta) {
      onTextChunk(delta);
    }
  } catch {
    // Ignore non-JSON chunks and fall back to poll-based history refresh.
  }
};

export const apiClient = {
  getVersion: () => requestJson<{ version: string }>("/version"),
  listChats: (filter: ChatFilter) => {
    const query = new URLSearchParams();
    if (filter.user_id) {
      query.append("user_id", filter.user_id);
    }
    if (filter.channel) {
      query.append("channel", filter.channel);
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return requestJson<ChatSpec[]>(`/chats${suffix}`);
  },
  createChat: (payload: CreateChatRequest) =>
    requestJson<ChatSpec>("/chats", {
      method: "POST",
      body: JSON.stringify({
        name: payload.name ?? "New Chat",
        session_id: payload.session_id,
        user_id: payload.user_id,
        channel: payload.channel,
        meta: payload.meta ?? {},
      }),
    }),
  deleteChat: (chatId: string) =>
    requestJson<{ deleted: boolean }>(`/chats/${encodeURIComponent(chatId)}`, {
      method: "DELETE",
    }),
  batchDeleteChats: (chatIds: string[]) =>
    requestJson<{ deleted: boolean }>("/chats/batch-delete", {
      method: "POST",
      body: JSON.stringify(chatIds),
    }),
  getChatHistory: (chatId: string) =>
    requestJson<ChatHistory>(`/chats/${encodeURIComponent(chatId)}`),
  listChannelTypes: () => requestJson<ChannelType[]>("/config/channels/types"),
  listChannels: () => requestJson<ChannelConfigMap>("/config/channels"),
  updateChannels: (payload: ChannelConfigMap) =>
    requestJson<ChannelConfigMap>("/config/channels", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getChannelConfig: (name: string) =>
    requestJson<JsonObject>(`/config/channels/${encodeURIComponent(name)}`),
  updateChannelConfig: (name: string, payload: JsonObject) =>
    requestJson<JsonObject>(`/config/channels/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  listCronJobs: () => requestJson<CronJobSpec[]>("/cron/jobs"),
  getCronJob: (jobId: string) =>
    requestJson<CronJobView>(`/cron/jobs/${encodeURIComponent(jobId)}`),
  createCronJob: (payload: CronJobSpec) =>
    requestJson<CronJobSpec>("/cron/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  replaceCronJob: (jobId: string, payload: CronJobSpec) =>
    requestJson<CronJobSpec>(`/cron/jobs/${encodeURIComponent(jobId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteCronJob: (jobId: string) =>
    requestJson<{ deleted: boolean }>(`/cron/jobs/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
    }),
  pauseCronJob: (jobId: string) =>
    requestJson<{ paused: boolean }>(`/cron/jobs/${encodeURIComponent(jobId)}/pause`, {
      method: "POST",
    }),
  resumeCronJob: (jobId: string) =>
    requestJson<{ resumed: boolean }>(`/cron/jobs/${encodeURIComponent(jobId)}/resume`, {
      method: "POST",
    }),
  runCronJob: (jobId: string) =>
    requestJson<{ started: boolean }>(`/cron/jobs/${encodeURIComponent(jobId)}/run`, {
      method: "POST",
    }),
  getCronJobState: (jobId: string) =>
    requestJson<CronJobState>(`/cron/jobs/${encodeURIComponent(jobId)}/state`),
  agentRoot: () => requestJson<JsonObject>("/agent/"),
  agentHealthCheck: () => requestJson<JsonObject>("/agent/health"),
  getAgentProcessStatus: () =>
    requestJson<JsonObject>("/agent/admin/status"),
  shutdownAgentSimple: () =>
    requestJson<JsonObject>("/agent/shutdown", {
      method: "POST",
    }),
  shutdownAgentAdmin: () =>
    requestJson<JsonObject>("/agent/admin/shutdown", {
      method: "POST",
    }),
  getPushMessages: (sessionId?: string) => {
    const suffix = sessionId
      ? `?session_id=${encodeURIComponent(sessionId)}`
      : "";
    return requestJson<PushMessageResponse>(`/console/push-messages${suffix}`);
  },
  listProviders: () => requestJson<ProviderInfo[]>("/models"),
  configureProvider: (
    providerId: string,
    payload: { api_key?: string; base_url?: string },
  ) =>
    requestJson<ProviderInfo>(
      `/models/${encodeURIComponent(providerId)}/config`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),
  getActiveModels: () => requestJson<ActiveModelsInfo>("/models/active"),
  setActiveLlm: (payload: ModelSlotConfig) =>
    requestJson<ActiveModelsInfo>("/models/active", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  listEnvs: () => requestJson<EnvVar[]>("/envs"),
  saveEnvs: (payload: Record<string, string>) =>
    requestJson<EnvVar[]>("/envs", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteEnv: (key: string) =>
    requestJson<EnvVar[]>(`/envs/${encodeURIComponent(key)}`, {
      method: "DELETE",
    }),
  listSkills: () => requestJson<SkillSpec[]>("/skills"),
  createSkill: (payload: { name: string; content: string }) =>
    requestJson<{ created: boolean }>("/skills", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  enableSkill: (name: string) =>
    requestJson<{ enabled: boolean }>(`/skills/${encodeURIComponent(name)}/enable`, {
      method: "POST",
    }),
  disableSkill: (name: string) =>
    requestJson<{ disabled: boolean }>(`/skills/${encodeURIComponent(name)}/disable`, {
      method: "POST",
    }),
  deleteSkill: (name: string) =>
    requestJson<{ deleted: boolean }>(`/skills/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  listWorkingFiles: () => requestJson<MdFileInfo[]>("/agent/files"),
  loadWorkingFile: (name: string) =>
    requestJson<{ content: string }>(`/agent/files/${encodeURIComponent(name)}`),
  saveWorkingFile: (name: string, content: string) =>
    requestJson<{ written: boolean }>(`/agent/files/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  listMemoryFiles: () => requestJson<MdFileInfo[]>("/agent/memory"),
  loadMemoryFile: (name: string) =>
    requestJson<{ content: string }>(
      `/agent/memory/${encodeURIComponent(name)}`,
    ),
  saveMemoryFile: (name: string, content: string) =>
    requestJson<{ written: boolean }>(
      `/agent/memory/${encodeURIComponent(name)}`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),
  sendAgentMessage: async (
    payload: AgentProcessRequest,
    onTextChunk?: StreamTextHandler,
  ): Promise<void> => {
    const response = await requestStream("/agent/process", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!response.body) {
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          parseStreamLine(line, onTextChunk);
        }
      }
      if (buffer) {
        parseStreamLine(buffer, onTextChunk);
      }
    } finally {
      reader.releaseLock();
    }
  },
};

export const createSessionId = (channel: string, userId: string): string => {
  const nonce = Math.random().toString(36).slice(2, 8);
  return `${channel}:${userId}:${Date.now()}:${nonce}`;
};

export const createUserTextContent = (text: string): RuntimeContent => ({
  type: "text",
  text,
  status: "created",
});
