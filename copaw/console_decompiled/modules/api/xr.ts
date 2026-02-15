// Recovered from copaw/console_decompiled/snippets/xr-api-block.js
// NOTE: 这是语义恢复版，变量命名和类型并非原始源码。

export const API_BASE_URL = "";

export async function requestJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      `Request failed: ${response.status} ${response.statusText}${message ? ` - ${message}` : ""}`,
    );
  }
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
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
      body: JSON.stringify(e)
    }),
    getChannelConfig: e => requestJson(`/config/channels/${encodeURIComponent(e)}`),
    updateChannelConfig: (e, t) => requestJson(`/config/channels/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    })
  };

export const cronJobsApi = {
    listCronJobs: () => requestJson("/cron/jobs"),
    createCronJob: e => requestJson("/cron/jobs", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    getCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}`),
    replaceCronJob: (e, t) => requestJson(`/cron/jobs/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    deleteCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    pauseCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}/pause`, {
      method: "POST"
    }),
    resumeCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}/resume`, {
      method: "POST"
    }),
    runCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}/run`, {
      method: "POST"
    }),
    triggerCronJob: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}/run`, {
      method: "POST"
    }),
    getCronJobState: e => requestJson(`/cron/jobs/${encodeURIComponent(e)}/state`)
  };

export const chatsApi = {
    listChats: e => {
      const t = new URLSearchParams;
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return requestJson(`/chats${n?`?${n}`:""}`)
    },
    createChat: e => requestJson("/chats", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    getChat: e => requestJson(`/chats/${encodeURIComponent(e)}`),
    updateChat: (e, t) => requestJson(`/chats/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    deleteChat: e => requestJson(`/chats/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    batchDeleteChats: e => requestJson("/chats/batch-delete", {
      method: "POST",
      body: JSON.stringify(e)
    })
  };

export const sessionsApi = {
    listSessions: e => {
      const t = new URLSearchParams;
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return requestJson(`/chats${n?`?${n}`:""}`)
    },
    getSession: e => requestJson(`/chats/${encodeURIComponent(e)}`),
    deleteSession: e => requestJson(`/chats/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    createSession: e => requestJson("/chats", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    updateSession: (e, t) => requestJson(`/chats/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    batchDeleteSessions: e => requestJson("/chats/batch-delete", {
      method: "POST",
      body: JSON.stringify(e)
    })
  };

export const envsApi = {
    listEnvs: () => requestJson("/envs"),
    saveEnvs: e => requestJson("/envs", {
      method: "PUT",
      body: JSON.stringify(e)
    }),
    deleteEnv: e => requestJson(`/envs/${encodeURIComponent(e)}`, {
      method: "DELETE"
    })
  };

export const modelsApi = {
    listProviders: () => requestJson("/models"),
    configureProvider: (e, t) => requestJson(`/models/${encodeURIComponent(e)}/config`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    getActiveModels: () => requestJson("/models/active"),
    setActiveLlm: e => requestJson("/models/active", {
      method: "PUT",
      body: JSON.stringify(e)
    })
  };

export const skillsApi = {
    listSkills: () => requestJson("/skills"),
    createSkill: (e, t) => requestJson("/skills", {
      method: "POST",
      body: JSON.stringify({
        name: e,
        content: t
      })
    }),
    enableSkill: e => requestJson(`/skills/${encodeURIComponent(e)}/enable`, {
      method: "POST"
    }),
    disableSkill: e => requestJson(`/skills/${encodeURIComponent(e)}/disable`, {
      method: "POST"
    }),
    batchEnableSkills: e => requestJson("/skills/batch-enable", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    deleteSkill: e => requestJson(`/skills/${encodeURIComponent(e)}`, {
      method: "DELETE"
    })
  };

export const agentApi = {
    agentRoot: () => requestJson("/agent/"),
    healthCheck: () => requestJson("/agent/health"),
    agentApi: e => requestJson("/agent/process", {
      method: "POST",
      body: JSON.stringify(e)
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
    loadFile: e => requestJson(`/agent/files/${encodeURIComponent(e)}`),
    saveFile: (e, t) => requestJson(`/agent/files/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify({
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
    loadDailyMemory: e => requestJson(`/agent/memory/${encodeURIComponent(e)}.md`),
    saveDailyMemory: (e, t) => requestJson(`/agent/memory/${encodeURIComponent(e)}.md`, {
      method: "PUT",
      body: JSON.stringify({
        content: t
      })
    })
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

export const xrApiGroups = [rootApi, channelsApi, cronJobsApi, chatsApi, sessionsApi, envsApi, modelsApi, skillsApi, agentApi, workspaceApi];
