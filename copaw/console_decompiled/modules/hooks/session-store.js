// Recovered from copaw/console_decompiled/snippets/session-store-block.js
// NOTE: Ut/Phn/Rhn 在打包后已匿名化，这里使用安全兜底实现，供后续手工重命名。

import { xrApi } from "../api/xr";

const mapSessionSummary = (value) => value;
const normalizeMessages = (value) => value;

class SessionStore {
  constructor() {
    this.lsKey = undefined;
    this.sessionList = undefined;
    this.fetchPromise = null;
    this.lastFetchTime = 0;
    this.cacheTimeout = 5e3;
    this.sessionCache = new Map;
    this.sessionFetchPromises = new Map;
    this.sessionCacheTimeout = 5e3;
    this.lsKey = "agent-scope-runtime-webui-sessions";
    this.sessionList = []
  }
  createEmptySession(t) {
    return window.currentSessionId = t, window.currentUserId = "default", window.currentChannel = "console", {
      id: t,
      name: "New Chat",
      sessionId: t,
      userId: "default",
      channel: "console",
      messages: [],
      meta: {}
    }
  }
  updateWindowVariables(t) {
    window.currentSessionId = t.sessionId || "", window.currentUserId = t.userId || "default", window.currentChannel = t.channel || "console"
  }
  getLocalSession(t) {
    const n = this.sessionList.find(r => r.id === t);
    return n ? (this.updateWindowVariables(n), n) : this.createEmptySession(t)
  }
  async getSessionList() {
    if (this.fetchPromise) return this.fetchPromise;
    const t = Date.now();
    if (this.sessionList.length > 0 && t - this.lastFetchTime < this.cacheTimeout) return [...this.sessionList];
    this.fetchPromise = this.fetchSessionListFromBackend();
    try {
      return await this.fetchPromise
    } finally {
      this.fetchPromise = null
    }
  }
  async fetchSessionListFromBackend() {
    try {
      const n = (await xrApi.listChats()).filter(r => r.id && r.id !== "undefined" && r.id !== "null");
      return this.sessionList = n.map(mapSessionSummary).reverse(), localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList)), this.lastFetchTime = Date.now(), [...this.sessionList]
    } catch {
      return this.sessionList = JSON.parse(localStorage.getItem(this.lsKey) || "[]"), [...this.sessionList]
    }
  }
  async getSession(t) {
    try {
      if (!t || t === "undefined" || t === "null") return this.createEmptySession(`temp-${Date.now()}`);
      if (/^\d+$/.test(t)) return this.getLocalSession(t);
      const r = this.sessionCache.get(t),
        a = Date.now();
      if (r && a - r.timestamp < this.sessionCacheTimeout) return this.updateWindowVariables(r.session), r.session;
      const i = this.sessionFetchPromises.get(t);
      if (i) return i;
      const o = this.fetchSessionFromBackend(t);
      this.sessionFetchPromises.set(t, o);
      try {
        return await o
      } finally {
        this.sessionFetchPromises.delete(t)
      }
    } catch {
      const r = this.sessionList.find(a => a.id === t);
      return r || this.createEmptySession(t)
    }
  }
  async fetchSessionFromBackend(t) {
    const n = await xrApi.getChat(t),
      r = this.sessionList.find(i => i.id === t),
      a = {
        id: t,
        name: (r == null ? void 0 : r.name) || t,
        sessionId: (r == null ? void 0 : r.sessionId) || t,
        userId: (r == null ? void 0 : r.userId) || "default",
        channel: (r == null ? void 0 : r.channel) || "console",
        messages: normalizeMessages(n.messages || []),
        meta: (r == null ? void 0 : r.meta) || {}
      };
    return this.updateWindowVariables(a), this.sessionCache.set(t, {
      session: a,
      timestamp: Date.now()
    }), a
  }
  async updateSession(t) {
    const n = this.sessionList.findIndex(r => r.id === t.id);
    return n > -1 && (this.sessionList[n] = {
      ...this.sessionList[n],
      ...t
    }, localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList))), [...this.sessionList]
  }
  async createSession(t) {
    return t.id = Date.now().toString(), this.sessionList.unshift(t), localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList)), this.lastFetchTime = Date.now(), [...this.sessionList]
  }
  async removeSession(t) {
    try {
      if (!t.id) return [...this.sessionList];
      const n = t.id;
      return await xrApi.deleteChat(n), this.sessionList = this.sessionList.filter(r => r.id !== n), localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList)), this.lastFetchTime = Date.now(), [...this.sessionList]
    } catch {
      return t.id && (this.sessionList = this.sessionList.filter(r => r.id !== t.id), localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList)), this.lastFetchTime = Date.now()), [...this.sessionList]
    }
  }
}

export const sessionStore = new SessionStore();
