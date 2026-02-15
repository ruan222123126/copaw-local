// Recovered from copaw/console_decompiled/snippets/xr-api-block.js
// NOTE: 这是语义恢复版，变量命名和类型并非原始源码。

export const API_BASE_URL = "";

/**
 * @typedef {{ user_id?: string, channel?: string }} SessionFilter
 * @typedef {{ modified_time?: string | number, [key: string]: any }} WorkspaceFileRecord
 * @typedef {{ filename?: string, modified_time?: string | number, [key: string]: any }} MemoryFileRecord
 */

const encodePathSegment = (value) => encodeURIComponent(value);

const buildSessionQuery = (filter) => {
  const query = new URLSearchParams();
  if (filter?.user_id) {
    query.append("user_id", filter.user_id);
  }
  if (filter?.channel) {
    query.append("channel", filter.channel);
  }
  const queryString = query.toString();
  return queryString ? `?${queryString}` : "";
};

/**
 * @template T
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<T>}
 */
export async function requestJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      `Request failed: ${response.status} ${response.statusText}${message ? ` - ${message}` : ""}`,
    );
  }
  if (response.status === 204) {
    return /** @type {T} */ (null);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return /** @type {Promise<T>} */ (response.json());
  }
  return /** @type {Promise<T>} */ (response.text());
}

const toJsonBody = (value) => JSON.stringify(value);

export const rootApi = {
  readRoot: () => requestJson("/"),
  getVersion: () => requestJson("/version"),
};

export const channelsApi = {
  listChannelTypes: () => requestJson("/config/channels/types"),
  listChannels: () => requestJson("/config/channels"),
  updateChannels: (channels) =>
    requestJson("/config/channels", {
      method: "PUT",
      body: toJsonBody(channels),
    }),
  getChannelConfig: (channelId) => requestJson(`/config/channels/${encodePathSegment(channelId)}`),
  updateChannelConfig: (channelId, config) =>
    requestJson(`/config/channels/${encodePathSegment(channelId)}`, {
      method: "PUT",
      body: toJsonBody(config),
    }),
};

export const cronJobsApi = {
  listCronJobs: () => requestJson("/cron/jobs"),
  createCronJob: (payload) =>
    requestJson("/cron/jobs", {
      method: "POST",
      body: toJsonBody(payload),
    }),
  getCronJob: (jobId) => requestJson(`/cron/jobs/${encodePathSegment(jobId)}`),
  replaceCronJob: (jobId, payload) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}`, {
      method: "PUT",
      body: toJsonBody(payload),
    }),
  deleteCronJob: (jobId) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}`, {
      method: "DELETE",
    }),
  pauseCronJob: (jobId) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}/pause`, {
      method: "POST",
    }),
  resumeCronJob: (jobId) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}/resume`, {
      method: "POST",
    }),
  runCronJob: (jobId) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}/run`, {
      method: "POST",
    }),
  triggerCronJob: (jobId) =>
    requestJson(`/cron/jobs/${encodePathSegment(jobId)}/run`, {
      method: "POST",
    }),
  getCronJobState: (jobId) => requestJson(`/cron/jobs/${encodePathSegment(jobId)}/state`),
};

export const chatsApi = {
  /**
   * @param {SessionFilter} [filter]
   */
  listChats: (filter) => requestJson(`/chats${buildSessionQuery(filter)}`),
  createChat: (payload) =>
    requestJson("/chats", {
      method: "POST",
      body: toJsonBody(payload),
    }),
  getChat: (chatId) => requestJson(`/chats/${encodePathSegment(chatId)}`),
  updateChat: (chatId, payload) =>
    requestJson(`/chats/${encodePathSegment(chatId)}`, {
      method: "PUT",
      body: toJsonBody(payload),
    }),
  deleteChat: (chatId) =>
    requestJson(`/chats/${encodePathSegment(chatId)}`, {
      method: "DELETE",
    }),
  batchDeleteChats: (payload) =>
    requestJson("/chats/batch-delete", {
      method: "POST",
      body: toJsonBody(payload),
    }),
};

export const sessionsApi = {
  /**
   * @param {SessionFilter} [filter]
   */
  listSessions: (filter) => requestJson(`/chats${buildSessionQuery(filter)}`),
  getSession: (sessionId) => requestJson(`/chats/${encodePathSegment(sessionId)}`),
  deleteSession: (sessionId) =>
    requestJson(`/chats/${encodePathSegment(sessionId)}`, {
      method: "DELETE",
    }),
  createSession: (payload) =>
    requestJson("/chats", {
      method: "POST",
      body: toJsonBody(payload),
    }),
  updateSession: (sessionId, payload) =>
    requestJson(`/chats/${encodePathSegment(sessionId)}`, {
      method: "PUT",
      body: toJsonBody(payload),
    }),
  batchDeleteSessions: (payload) =>
    requestJson("/chats/batch-delete", {
      method: "POST",
      body: toJsonBody(payload),
    }),
};

export const envsApi = {
  listEnvs: () => requestJson("/envs"),
  saveEnvs: (payload) =>
    requestJson("/envs", {
      method: "PUT",
      body: toJsonBody(payload),
    }),
  deleteEnv: (envName) =>
    requestJson(`/envs/${encodePathSegment(envName)}`, {
      method: "DELETE",
    }),
};

export const modelsApi = {
  listProviders: () => requestJson("/models"),
  configureProvider: (providerName, config) =>
    requestJson(`/models/${encodePathSegment(providerName)}/config`, {
      method: "PUT",
      body: toJsonBody(config),
    }),
  getActiveModels: () => requestJson("/models/active"),
  setActiveLlm: (payload) =>
    requestJson("/models/active", {
      method: "PUT",
      body: toJsonBody(payload),
    }),
};

export const skillsApi = {
  listSkills: () => requestJson("/skills"),
  createSkill: (name, content) =>
    requestJson("/skills", {
      method: "POST",
      body: toJsonBody({
        name,
        content,
      }),
    }),
  enableSkill: (skillName) =>
    requestJson(`/skills/${encodePathSegment(skillName)}/enable`, {
      method: "POST",
    }),
  disableSkill: (skillName) =>
    requestJson(`/skills/${encodePathSegment(skillName)}/disable`, {
      method: "POST",
    }),
  batchEnableSkills: (payload) =>
    requestJson("/skills/batch-enable", {
      method: "POST",
      body: toJsonBody(payload),
    }),
  deleteSkill: (skillName) =>
    requestJson(`/skills/${encodePathSegment(skillName)}`, {
      method: "DELETE",
    }),
};

export const agentApi = {
  agentRoot: () => requestJson("/agent/"),
  healthCheck: () => requestJson("/agent/health"),
  agentApi: (payload) =>
    requestJson("/agent/process", {
      method: "POST",
      body: toJsonBody(payload),
    }),
  getProcessStatus: () => requestJson("/agent/admin/status"),
  shutdownSimple: () =>
    requestJson("/agent/shutdown", {
      method: "POST",
    }),
  shutdown: () =>
    requestJson("/agent/admin/shutdown", {
      method: "POST",
    }),
};

export const workspaceApi = {
  listFiles: () =>
    requestJson("/agent/files").then((records) =>
      (Array.isArray(records) ? records : []).map((record) => ({
        ...record,
        updated_at: new Date(record.modified_time).getTime(),
      })),
    ),
  loadFile: (filePath) => requestJson(`/agent/files/${encodePathSegment(filePath)}`),
  saveFile: (filePath, content) =>
    requestJson(`/agent/files/${encodePathSegment(filePath)}`, {
      method: "PUT",
      body: toJsonBody({
        content,
      }),
    }),
  downloadWorkspace: async () => {
    const response = await fetch(`${API_BASE_URL}/workspace/download`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`Workspace download failed: ${response.status} ${response.statusText}`);
    }
    return response.blob();
  },
  uploadFile: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/workspace/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload failed: ${response.status} ${response.statusText} - ${errorText}`);
    }
    return response.json();
  },
  listDailyMemory: () =>
    requestJson("/agent/memory").then((records) =>
      (Array.isArray(records) ? records : []).map((record) => {
        const filename = typeof record.filename === "string" ? record.filename : "";
        const date = filename.replace(".md", "");
        return {
          ...record,
          date,
          updated_at: new Date(record.modified_time).getTime(),
        };
      }),
    ),
  loadDailyMemory: (date) => requestJson(`/agent/memory/${encodePathSegment(date)}.md`),
  saveDailyMemory: (date, content) =>
    requestJson(`/agent/memory/${encodePathSegment(date)}.md`, {
      method: "PUT",
      body: toJsonBody({
        content,
      }),
    }),
};

export const xrApi = {
  ...rootApi,
  ...channelsApi,
  ...cronJobsApi,
  ...chatsApi,
  ...sessionsApi,
  ...envsApi,
  ...modelsApi,
  ...skillsApi,
  ...agentApi,
  ...workspaceApi,
};

export const xrApiGroups = [
  rootApi,
  channelsApi,
  cronJobsApi,
  chatsApi,
  sessionsApi,
  envsApi,
  modelsApi,
  skillsApi,
  agentApi,
  workspaceApi,
];
