import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../../api/client";
import type { ChannelConfigMap, JsonObject } from "../../api/types";
import "./channels.css";

const formatJson = (value: unknown): string => JSON.stringify(value, null, 2);

const sortChannelNames = (channels: ChannelConfigMap): string[] =>
  Object.keys(channels).sort((a, b) => a.localeCompare(b));

const parseJsonObject = (source: string): JsonObject => {
  const parsed = JSON.parse(source) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("配置必须是 JSON 对象。比如 {\"enabled\": true}。");
  }
  return parsed as JsonObject;
};

export function ChannelsPage() {
  const [channelTypes, setChannelTypes] = useState<string[]>([]);
  const [channels, setChannels] = useState<ChannelConfigMap>({});
  const [selectedChannel, setSelectedChannel] = useState("");
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const channelNames = useMemo(() => sortChannelNames(channels), [channels]);

  const applySelectedDraft = useCallback(
    (name: string, nextChannels: ChannelConfigMap) => {
      if (!name) {
        setDraft("");
        setDirty(false);
        return;
      }
      const config = nextChannels[name] ?? {};
      setDraft(formatJson(config));
      setDirty(false);
    },
    [],
  );

  const loadChannels = useCallback(
    async (preferredChannel?: string) => {
      setLoading(true);
      setError(null);
      setNotice(null);
      try {
        const [types, channelMap] = await Promise.all([
          apiClient.listChannelTypes(),
          apiClient.listChannels(),
        ]);
        setChannelTypes(types);
        setChannels(channelMap);

        const sortedNames = sortChannelNames(channelMap);
        const nextSelected =
          preferredChannel && sortedNames.includes(preferredChannel)
            ? preferredChannel
            : sortedNames[0] ?? "";

        setSelectedChannel(nextSelected);
        applySelectedDraft(nextSelected, channelMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载渠道配置失败");
      } finally {
        setLoading(false);
      }
    },
    [applySelectedDraft],
  );

  useEffect(() => {
    void loadChannels();
  }, []);

  const selectChannel = useCallback(
    (name: string) => {
      if (name === selectedChannel) {
        return;
      }
      if (dirty) {
        const confirmed = window.confirm("当前配置有未保存改动，确认切换吗？");
        if (!confirmed) {
          return;
        }
      }
      setSelectedChannel(name);
      applySelectedDraft(name, channels);
      setError(null);
      setNotice(null);
    },
    [applySelectedDraft, channels, dirty, selectedChannel],
  );

  const saveSelectedChannel = useCallback(async () => {
    if (!selectedChannel) {
      setError("请先选择一个渠道。");
      return;
    }

    let payload: JsonObject;
    try {
      payload = parseJsonObject(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "配置 JSON 解析失败");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await apiClient.updateChannelConfig(selectedChannel, payload);
      setChannels((prev) => ({
        ...prev,
        [selectedChannel]: updated,
      }));
      setDraft(formatJson(updated));
      setDirty(false);
      setNotice(`渠道「${selectedChannel}」保存成功。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存渠道配置失败");
    } finally {
      setSaving(false);
    }
  }, [draft, selectedChannel]);

  const toggleEnabledInDraft = useCallback(() => {
    try {
      const config = parseJsonObject(draft);
      const current = config.enabled === true;
      const nextConfig: JsonObject = {
        ...config,
        enabled: !current,
      };
      setDraft(formatJson(nextConfig));
      setDirty(true);
      setNotice(`已在草稿中切换 enabled -> ${!current}`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "切换 enabled 失败");
    }
  }, [draft]);

  if (loading) {
    return <p className="channels-muted">Channels 加载中...</p>;
  }

  return (
    <section className="channels-page">
      <header className="channels-header">
        <div>
          <h2>Channels</h2>
          <p>编辑并保存 `config.json` 中的渠道配置（`/config/channels/*`）。</p>
        </div>
        <div className="channels-actions">
          <button type="button" onClick={() => void loadChannels(selectedChannel)}>
            刷新
          </button>
          <button
            type="button"
            onClick={toggleEnabledInDraft}
            disabled={!selectedChannel}
          >
            切换 enabled
          </button>
          <button
            type="button"
            onClick={() => void saveSelectedChannel()}
            disabled={!selectedChannel || saving}
          >
            {saving ? "保存中..." : "保存当前渠道"}
          </button>
        </div>
      </header>

      {error ? <p className="channels-error">{error}</p> : null}
      {notice ? <p className="channels-note">{notice}</p> : null}

      <section className="channels-meta-card">
        <strong>可用类型</strong>
        <div className="channels-type-list">
          {channelTypes.length === 0
            ? "未返回类型"
            : channelTypes.map((type) => <code key={type}>{type}</code>)}
        </div>
      </section>

      <div className="channels-grid">
        <aside className="channels-list-card">
          <h3>渠道列表</h3>
          <ul>
            {channelNames.map((name) => {
              const config = channels[name];
              const enabled = config?.enabled === true;
              return (
                <li key={name}>
                  <button
                    type="button"
                    className={selectedChannel === name ? "active" : ""}
                    onClick={() => selectChannel(name)}
                  >
                    <strong>{name}</strong>
                    <span className={enabled ? "enabled" : "disabled"}>
                      {enabled ? "enabled" : "disabled"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="channels-editor-card">
          <header>
            <h3>{selectedChannel || "未选择渠道"}</h3>
            <p>
              当前草稿{dirty ? "有" : "无"}
              未保存改动。
            </p>
          </header>
          <textarea
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setDirty(true);
            }}
            placeholder="请编辑 JSON 配置"
            disabled={!selectedChannel}
          />
        </section>
      </div>
    </section>
  );
}
