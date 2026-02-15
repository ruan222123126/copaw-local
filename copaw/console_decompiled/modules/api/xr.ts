// Recovered from copaw/console_decompiled/snippets/xr-api-block.js
// NOTE: 这是语义恢复版，变量命名和类型并非原始源码。

export const API_BASE_URL = "";

/**
 * @typedef {{ user_id?: string, channel?: string }} SessionFilter
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

const toJsonBody = (value) => JSON.stringify(value);

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

export const rootApi = {
    readRoot: () => requestJson("/"),
    getVersion: () => requestJson("/version")
  };

export const channelsApi = {
    listChannelTypes: () => requestJson("/config/channels/types"),
    listChannels: () => requestJson("/config/channels"),
    updateChannels: e => requestJson("/config/channels", {
      method: "PUT",
      body: toJsonBody(e)
    }),
    getChannelConfig: e => requestJson(`/config/channels/${encodePathSegment(e)}`),
    updateChannelConfig: (e, t) => requestJson(`/config/channels/${encodePathSegment(e)}`, {
      method: "PUT",
      body: toJsonBody(t)
    })
  };

export const cronJobsApi = {
    listCronJobs: () => requestJson("/cron/jobs"),
    createCronJob: e => requestJson("/cron/jobs", {
      method: "POST",
      body: toJsonBody(e)
    }),
    getCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}`),
    replaceCronJob: (e, t) => requestJson(`/cron/jobs/${encodePathSegment(e)}`, {
      method: "PUT",
      body: toJsonBody(t)
    }),
    deleteCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}`, {
      method: "DELETE"
    }),
    pauseCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}/pause`, {
      method: "POST"
    }),
    resumeCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}/resume`, {
      method: "POST"
    }),
    runCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}/run`, {
      method: "POST"
    }),
    triggerCronJob: e => requestJson(`/cron/jobs/${encodePathSegment(e)}/run`, {
      method: "POST"
    }),
    getCronJobState: e => requestJson(`/cron/jobs/${encodePathSegment(e)}/state`)
  };

export const chatsApi = {
    listChats: e => {
      const t = new URLSearchParams();
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return requestJson(`/chats${n?`?${n}`:""}`)
    },
    createChat: e => requestJson("/chats", {
      method: "POST",
      body: toJsonBody(e)
    }),
    getChat: e => requestJson(`/chats/${encodePathSegment(e)}`),
    updateChat: (e, t) => requestJson(`/chats/${encodePathSegment(e)}`, {
      method: "PUT",
      body: toJsonBody(t)
    }),
    deleteChat: e => requestJson(`/chats/${encodePathSegment(e)}`, {
      method: "DELETE"
    }),
    batchDeleteChats: e => requestJson("/chats/batch-delete", {
      method: "POST",
      body: toJsonBody(e)
    })
  };

export const sessionsApi = {
    listSessions: e => {
      const t = new URLSearchParams();
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return requestJson(`/chats${n?`?${n}`:""}`)
    },
    getSession: e => requestJson(`/chats/${encodePathSegment(e)}`),
    deleteSession: e => requestJson(`/chats/${encodePathSegment(e)}`, {
      method: "DELETE"
    }),
    createSession: e => requestJson("/chats", {
      method: "POST",
      body: toJsonBody(e)
    }),
    updateSession: (e, t) => requestJson(`/chats/${encodePathSegment(e)}`, {
      method: "PUT",
      body: toJsonBody(t)
    }),
    batchDeleteSessions: e => requestJson("/chats/batch-delete", {
      method: "POST",
      body: toJsonBody(e)
    })
  };

export const envsApi = {
    listEnvs: () => requestJson("/envs"),
    saveEnvs: e => requestJson("/envs", {
      method: "PUT",
      body: toJsonBody(e)
    }),
    deleteEnv: e => requestJson(`/envs/${encodePathSegment(e)}`, {
      method: "DELETE"
    })
  };

export const modelsApi = {
    listProviders: () => requestJson("/models"),
    configureProvider: (e, t) => requestJson(`/models/${encodePathSegment(e)}/config`, {
      method: "PUT",
      body: toJsonBody(t)
    }),
    getActiveModels: () => requestJson("/models/active"),
    setActiveLlm: e => requestJson("/models/active", {
      method: "PUT",
      body: toJsonBody(e)
    })
  };

export const skillsApi = {
    listSkills: () => requestJson("/skills"),
    createSkill: (e, t) => requestJson("/skills", {
      method: "POST",
      body: toJsonBody({
        name: e,
        content: t
      })
    }),
    enableSkill: e => requestJson(`/skills/${encodePathSegment(e)}/enable`, {
      method: "POST"
    }),
    disableSkill: e => requestJson(`/skills/${encodePathSegment(e)}/disable`, {
      method: "POST"
    }),
    batchEnableSkills: e => requestJson("/skills/batch-enable", {
      method: "POST",
      body: toJsonBody(e)
    }),
    deleteSkill: e => requestJson(`/skills/${encodePathSegment(e)}`, {
      method: "DELETE"
    })
  };

export const agentApi = {
    agentRoot: () => requestJson("/agent/"),
    healthCheck: () => requestJson("/agent/health"),
    agentApi: e => requestJson("/agent/process", {
      method: "POST",
      body: toJsonBody(e)
    }),
    getProcessStatus: () => requestJson("/agent/admin/status"),
    shutdownSimple: () => requestJson("/agent/shutdown", {
      method: "POST"
    }),
    shutdown: () => requestJson("/agent/admin/shutdown", {
      method: "POST"
    })
  };

export const workspaceApi = {
    listFiles: () => requestJson("/agent/files").then(e => e.map(t => ({
      ...t,
      updated_at: new Date(t.modified_time).getTime()
    }))),
    loadFile: e => requestJson(`/agent/files/${encodePathSegment(e)}`),
    saveFile: (e, t) => requestJson(`/agent/files/${encodePathSegment(e)}`, {
      method: "PUT",
      body: toJsonBody({
        content: t
      })
    }),
    downloadWorkspace: async () => {
      const e = await fetch(`${API_BASE_URL}/workspace/download`, {
        method: "GET"
      });
      if (!e.ok) throw new Error(`Workspace download failed: ${e.status} ${e.statusText}`);
      return await e.blob()
    },
    uploadFile: async e => {
      const t = new FormData;
      t.append("file", e);
      const n = await fetch(`${API_BASE_URL}/workspace/upload`, {
        method: "POST",
        body: t
      });
      if (!n.ok) {
        const r = await n.text();
        throw new Error(`Upload failed: ${n.status} ${n.statusText} - ${r}`)
      }
      return await n.json()
    },
    listDailyMemory: () => requestJson("/agent/memory").then(e => e.map(t => {
      const n = t.filename.replace(".md", "");
      return {
        ...t,
        date: n,
        updated_at: new Date(t.modified_time).getTime()
      }
    })),
    loadDailyMemory: e => requestJson(`/agent/memory/${encodePathSegment(e)}.md`),
    saveDailyMemory: (e, t) => requestJson(`/agent/memory/${encodePathSegment(e)}.md`, {
      method: "PUT",
      body: toJsonBody({
        content: t
      })
    })
  };

if (chatsApi?.listChats) {
  chatsApi.listChats = /** @param {SessionFilter} [filter] */ (filter) =>
    requestJson(`/chats${buildSessionQuery(filter)}`);
}
if (sessionsApi?.listSessions) {
  sessionsApi.listSessions = /** @param {SessionFilter} [filter] */ (filter) =>
    requestJson(`/chats${buildSessionQuery(filter)}`);
}

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

export const xrApiGroups = [rootApi, channelsApi, cronJobsApi, chatsApi, sessionsApi, envsApi, modelsApi, skillsApi, agentApi, workspaceApi];
