// Recovered from copaw/console_decompiled/snippets/session-store-block.js
// NOTE: Ut/Phn/Rhn 在打包后已匿名化，这里使用安全兜底实现，供后续手工重命名。

import { xrApi } from "../api/xr";

const mapSessionSummary = (value) => value;
const normalizeMessages = (value) => value;
const SESSION_STORAGE_KEY = "agent-scope-runtime-webui-sessions";
const DEFAULT_USER_ID = "default";
const DEFAULT_CHANNEL = "console";
const NEW_CHAT_NAME = "New Chat";

class SessionStore {
  constructor() {
    this.lsKey = SESSION_STORAGE_KEY;
    this.sessionList = [];
    this.fetchPromise = null;
    this.lastFetchTime = 0;
    this.cacheTimeout = 5e3;
    this.sessionCache = new Map();
    this.sessionFetchPromises = new Map();
    this.sessionCacheTimeout = 5e3;
  }

  persistSessionList() {
    localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList));
  }

  createEmptySession(sessionId) {
    window.currentSessionId = sessionId;
    window.currentUserId = DEFAULT_USER_ID;
    window.currentChannel = DEFAULT_CHANNEL;
    return {
      id: sessionId,
      name: NEW_CHAT_NAME,
      sessionId,
      userId: DEFAULT_USER_ID,
      channel: DEFAULT_CHANNEL,
      messages: [],
      meta: {},
    };
  }

  updateWindowVariables(session) {
    window.currentSessionId = session.sessionId || "";
    window.currentUserId = session.userId || DEFAULT_USER_ID;
    window.currentChannel = session.channel || DEFAULT_CHANNEL;
  }

  getLocalSession(sessionId) {
    const existing = this.sessionList.find((session) => session.id === sessionId);
    if (!existing) {
      return this.createEmptySession(sessionId);
    }
    this.updateWindowVariables(existing);
    return existing;
  }

  async getSessionList() {
    if (this.fetchPromise) {
      return this.fetchPromise;
    }

    const now = Date.now();
    if (this.sessionList.length > 0 && now - this.lastFetchTime < this.cacheTimeout) {
      return [...this.sessionList];
    }

    this.fetchPromise = this.fetchSessionListFromBackend();
    try {
      return await this.fetchPromise;
    } finally {
      this.fetchPromise = null;
    }
  }

  async fetchSessionListFromBackend() {
    try {
      const sessions = (await xrApi.listChats()).filter(
        (session) => session.id && session.id !== "undefined" && session.id !== "null",
      );
      this.sessionList = sessions.map(mapSessionSummary).reverse();
      this.persistSessionList();
      this.lastFetchTime = Date.now();
      return [...this.sessionList];
    } catch {
      this.sessionList = JSON.parse(localStorage.getItem(this.lsKey) || "[]");
      return [...this.sessionList];
    }
  }

  async getSession(sessionId) {
    try {
      if (!sessionId || sessionId === "undefined" || sessionId === "null") {
        return this.createEmptySession(`temp-${Date.now()}`);
      }
      if (/^\d+$/.test(sessionId)) {
        return this.getLocalSession(sessionId);
      }

      const cacheEntry = this.sessionCache.get(sessionId);
      const now = Date.now();
      if (cacheEntry && now - cacheEntry.timestamp < this.sessionCacheTimeout) {
        this.updateWindowVariables(cacheEntry.session);
        return cacheEntry.session;
      }

      const inFlightRequest = this.sessionFetchPromises.get(sessionId);
      if (inFlightRequest) {
        return inFlightRequest;
      }

      const request = this.fetchSessionFromBackend(sessionId);
      this.sessionFetchPromises.set(sessionId, request);
      try {
        return await request;
      } finally {
        this.sessionFetchPromises.delete(sessionId);
      }
    } catch {
      const cachedSession = this.sessionList.find((session) => session.id === sessionId);
      return cachedSession || this.createEmptySession(sessionId);
    }
  }

  async fetchSessionFromBackend(sessionId) {
    const remoteSession = await xrApi.getChat(sessionId);
    const localSession = this.sessionList.find((session) => session.id === sessionId);
    const mergedSession = {
      id: sessionId,
      name: localSession?.name || sessionId,
      sessionId: localSession?.sessionId || sessionId,
      userId: localSession?.userId || DEFAULT_USER_ID,
      channel: localSession?.channel || DEFAULT_CHANNEL,
      messages: normalizeMessages(remoteSession.messages || []),
      meta: localSession?.meta || {},
    };
    this.updateWindowVariables(mergedSession);
    this.sessionCache.set(sessionId, {
      session: mergedSession,
      timestamp: Date.now(),
    });
    return mergedSession;
  }

  async updateSession(patch) {
    const index = this.sessionList.findIndex((session) => session.id === patch.id);
    if (index > -1) {
      this.sessionList[index] = {
        ...this.sessionList[index],
        ...patch,
      };
      this.persistSessionList();
    }
    return [...this.sessionList];
  }

  async createSession(session) {
    session.id = Date.now().toString();
    this.sessionList.unshift(session);
    this.persistSessionList();
    this.lastFetchTime = Date.now();
    return [...this.sessionList];
  }

  async removeSession(session) {
    try {
      if (!session.id) {
        return [...this.sessionList];
      }
      const sessionId = session.id;
      await xrApi.deleteChat(sessionId);
      this.sessionList = this.sessionList.filter((item) => item.id !== sessionId);
      this.persistSessionList();
      this.lastFetchTime = Date.now();
      return [...this.sessionList];
    } catch {
      if (session.id) {
        this.sessionList = this.sessionList.filter((item) => item.id !== session.id);
        this.persistSessionList();
        this.lastFetchTime = Date.now();
      }
      return [...this.sessionList];
    }
  }
}

export const sessionStore = new SessionStore();
