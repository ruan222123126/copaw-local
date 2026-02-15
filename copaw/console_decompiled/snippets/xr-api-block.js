const QQt = {
    readRoot: () => Un("/"),
    getVersion: () => Un("/version")
  },
  DQt = {
    listChannelTypes: () => Un("/config/channels/types"),
    listChannels: () => Un("/config/channels"),
    updateChannels: e => Un("/config/channels", {
      method: "PUT",
      body: JSON.stringify(e)
    }),
    getChannelConfig: e => Un(`/config/channels/${encodeURIComponent(e)}`),
    updateChannelConfig: (e, t) => Un(`/config/channels/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    })
  },
  LQt = {
    listCronJobs: () => Un("/cron/jobs"),
    createCronJob: e => Un("/cron/jobs", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    getCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}`),
    replaceCronJob: (e, t) => Un(`/cron/jobs/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    deleteCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    pauseCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}/pause`, {
      method: "POST"
    }),
    resumeCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}/resume`, {
      method: "POST"
    }),
    runCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}/run`, {
      method: "POST"
    }),
    triggerCronJob: e => Un(`/cron/jobs/${encodeURIComponent(e)}/run`, {
      method: "POST"
    }),
    getCronJobState: e => Un(`/cron/jobs/${encodeURIComponent(e)}/state`)
  },
  zQt = {
    listChats: e => {
      const t = new URLSearchParams;
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return Un(`/chats${n?`?${n}`:""}`)
    },
    createChat: e => Un("/chats", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    getChat: e => Un(`/chats/${encodeURIComponent(e)}`),
    updateChat: (e, t) => Un(`/chats/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    deleteChat: e => Un(`/chats/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    batchDeleteChats: e => Un("/chats/batch-delete", {
      method: "POST",
      body: JSON.stringify(e)
    })
  },
  BQt = {
    listSessions: e => {
      const t = new URLSearchParams;
      e != null && e.user_id && t.append("user_id", e.user_id), e != null && e.channel && t.append("channel", e.channel);
      const n = t.toString();
      return Un(`/chats${n?`?${n}`:""}`)
    },
    getSession: e => Un(`/chats/${encodeURIComponent(e)}`),
    deleteSession: e => Un(`/chats/${encodeURIComponent(e)}`, {
      method: "DELETE"
    }),
    createSession: e => Un("/chats", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    updateSession: (e, t) => Un(`/chats/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    batchDeleteSessions: e => Un("/chats/batch-delete", {
      method: "POST",
      body: JSON.stringify(e)
    })
  },
  FQt = {
    listEnvs: () => Un("/envs"),
    saveEnvs: e => Un("/envs", {
      method: "PUT",
      body: JSON.stringify(e)
    }),
    deleteEnv: e => Un(`/envs/${encodeURIComponent(e)}`, {
      method: "DELETE"
    })
  },
  UQt = {
    listProviders: () => Un("/models"),
    configureProvider: (e, t) => Un(`/models/${encodeURIComponent(e)}/config`, {
      method: "PUT",
      body: JSON.stringify(t)
    }),
    getActiveModels: () => Un("/models/active"),
    setActiveLlm: e => Un("/models/active", {
      method: "PUT",
      body: JSON.stringify(e)
    })
  },
  jQt = {
    listSkills: () => Un("/skills"),
    createSkill: (e, t) => Un("/skills", {
      method: "POST",
      body: JSON.stringify({
        name: e,
        content: t
      })
    }),
    enableSkill: e => Un(`/skills/${encodeURIComponent(e)}/enable`, {
      method: "POST"
    }),
    disableSkill: e => Un(`/skills/${encodeURIComponent(e)}/disable`, {
      method: "POST"
    }),
    batchEnableSkills: e => Un("/skills/batch-enable", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    deleteSkill: e => Un(`/skills/${encodeURIComponent(e)}`, {
      method: "DELETE"
    })
  },
  XQt = {
    agentRoot: () => Un("/agent/"),
    healthCheck: () => Un("/agent/health"),
    agentApi: e => Un("/agent/process", {
      method: "POST",
      body: JSON.stringify(e)
    }),
    getProcessStatus: () => Un("/agent/admin/status"),
    shutdownSimple: () => Un("/agent/shutdown", {
      method: "POST"
    }),
    shutdown: () => Un("/agent/admin/shutdown", {
      method: "POST"
    })
  },
  T9 = {
    listFiles: () => Un("/agent/files").then(e => e.map(t => ({
      ...t,
      updated_at: new Date(t.modified_time).getTime()
    }))),
    loadFile: e => Un(`/agent/files/${encodeURIComponent(e)}`),
    saveFile: (e, t) => Un(`/agent/files/${encodeURIComponent(e)}`, {
      method: "PUT",
      body: JSON.stringify({
        content: t
      })
    }),
    downloadWorkspace: async () => {
      const e = await fetch(`${O2}/workspace/download`, {
        method: "GET"
      });
      if (!e.ok) throw new Error(`Workspace download failed: ${e.status} ${e.statusText}`);
      return await e.blob()
    },
    uploadFile: async e => {
      const t = new FormData;
      t.append("file", e);
      const n = await fetch(`${O2}/workspace/upload`, {
        method: "POST",
        body: t
      });
      if (!n.ok) {
        const r = await n.text();
        throw new Error(`Upload failed: ${n.status} ${n.statusText} - ${r}`)
      }
      return await n.json()
    },
    listDailyMemory: () => Un("/agent/memory").then(e => e.map(t => {
      const n = t.filename.replace(".md", "");
      return {
        ...t,
        date: n,
        updated_at: new Date(t.modified_time).getTime()
      }
    })),
    loadDailyMemory: e => Un(`/agent/memory/${encodeURIComponent(e)}.md`),
    saveDailyMemory: (e, t) => Un(`/agent/memory/${encodeURIComponent(e)}.md`, {
      method: "PUT",
      body: JSON.stringify({
        content: t
      })
    })
  },
  Xr = {
    ...QQt,
    ...DQt,
    ...LQt,
    ...zQt,
    ...BQt,
    ...FQt,
    ...UQt,
    ...XQt,
    ...jQt,
    ...T9
  };


// next block starts at: lucide-react license comment
