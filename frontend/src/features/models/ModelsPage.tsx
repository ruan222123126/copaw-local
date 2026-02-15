import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../../api/client";
import type { ModelSlotConfig, ProviderInfo } from "../../api/types";
import "./models.css";

interface ProviderDraft {
  apiKey: string;
  baseUrl: string;
  model: string;
}

type ProviderDraftMap = Record<string, ProviderDraft>;

const createDrafts = (
  providers: ProviderInfo[],
  active: ModelSlotConfig,
): ProviderDraftMap => {
  const drafts: ProviderDraftMap = {};
  for (const provider of providers) {
    const defaultModel =
      active.provider_id === provider.id && active.model
        ? active.model
        : provider.models[0]?.id ?? "";
    drafts[provider.id] = {
      apiKey: "",
      baseUrl: provider.current_base_url,
      model: defaultModel,
    };
  }
  return drafts;
};

export function ModelsPage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeModel, setActiveModel] = useState<ModelSlotConfig>({
    provider_id: "",
    model: "",
  });
  const [drafts, setDrafts] = useState<ProviderDraftMap>({});
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingProviderId, setSavingProviderId] = useState<string | null>(null);
  const [savingActiveModel, setSavingActiveModel] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const [providerList, activeInfo] = await Promise.all([
        apiClient.listProviders(),
        apiClient.getActiveModels(),
      ]);
      setProviders(providerList);
      setActiveModel(activeInfo.active_llm);
      setDrafts(createDrafts(providerList, activeInfo.active_llm));

      const initialProviderId =
        activeInfo.active_llm.provider_id || providerList[0]?.id || "";
      setSelectedProviderId(initialProviderId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Models 配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  const selectedProviderDraft = selectedProvider
    ? drafts[selectedProvider.id]
    : undefined;

  const updateDraft = useCallback(
    (providerId: string, patch: Partial<ProviderDraft>) => {
      setDrafts((prev) => {
        const current = prev[providerId];
        if (!current) {
          return prev;
        }
        return {
          ...prev,
          [providerId]: {
            ...current,
            ...patch,
          },
        };
      });
    },
    [],
  );

  const ensureProviderDraft = useCallback(
    (providerId: string) => {
      setDrafts((prev) => {
        if (prev[providerId]) {
          return prev;
        }
        const provider = providers.find((item) => item.id === providerId);
        if (!provider) {
          return prev;
        }
        return {
          ...prev,
          [providerId]: {
            apiKey: "",
            baseUrl: provider.current_base_url,
            model: provider.models[0]?.id ?? "",
          },
        };
      });
    },
    [providers],
  );

  const saveProvider = useCallback(
    async (provider: ProviderInfo) => {
      const draft = drafts[provider.id];
      if (!draft) {
        return;
      }

      const payload: { api_key?: string; base_url?: string } = {};
      const apiKey = draft.apiKey.trim();
      if (apiKey) {
        payload.api_key = apiKey;
      }
      if (provider.allow_custom_base_url) {
        const nextBaseUrl = draft.baseUrl.trim();
        if (nextBaseUrl !== provider.current_base_url) {
          payload.base_url = nextBaseUrl;
        }
      }

      if (Object.keys(payload).length === 0) {
        setNotice("没有可提交的 provider 变更。API Key 留空表示保持不变。");
        return;
      }

      setSavingProviderId(provider.id);
      setError(null);
      setNotice(null);
      try {
        const updatedProvider = await apiClient.configureProvider(
          provider.id,
          payload,
        );
        setProviders((prev) =>
          prev.map((item) =>
            item.id === updatedProvider.id ? updatedProvider : item,
          ),
        );
        setDrafts((prev) => ({
          ...prev,
          [provider.id]: {
            ...prev[provider.id],
            apiKey: "",
            baseUrl: updatedProvider.current_base_url,
          },
        }));
        setNotice(`Provider「${updatedProvider.name}」保存成功。`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "保存 provider 失败");
      } finally {
        setSavingProviderId(null);
      }
    },
    [drafts],
  );

  const saveActiveModel = useCallback(async () => {
    if (!selectedProvider) {
      return;
    }
    const modelId = drafts[selectedProvider.id]?.model.trim() ?? "";
    if (!modelId) {
      setError("请先填写 Model。");
      return;
    }

    setSavingActiveModel(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.setActiveLlm({
        provider_id: selectedProvider.id,
        model: modelId,
      });
      setActiveModel(result.active_llm);
      setNotice("Active LLM 已更新。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "设置 active 模型失败");
    } finally {
      setSavingActiveModel(false);
    }
  }, [drafts, selectedProvider]);

  if (loading) {
    return <p className="models-muted">Models 配置加载中...</p>;
  }

  return (
    <section className="models-page">
      <header className="models-header">
        <div>
          <h2>Models</h2>
          <p>配置 Provider 凭据、Base URL，并指定当前 active_llm。</p>
        </div>
        <button type="button" onClick={() => void loadData()}>
          刷新
        </button>
      </header>

      {error ? <p className="models-error">{error}</p> : null}
      {notice ? <p className="models-note">{notice}</p> : null}

      <article className="models-card">
        <h3>当前生效模型</h3>
        <div className="models-status-grid">
          <div>
            <span>provider</span>
            <strong>{activeModel.provider_id || "-"}</strong>
          </div>
          <div>
            <span>model</span>
            <strong>{activeModel.model || "-"}</strong>
          </div>
        </div>

        <div className="models-active-form">
          <label className="form-field">
            Provider
            <select
              value={selectedProviderId}
              onChange={(event) => {
                const nextId = event.target.value;
                setSelectedProviderId(nextId);
                ensureProviderDraft(nextId);
              }}
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            Model
            {selectedProvider && selectedProvider.models.length > 0 ? (
              <select
                value={selectedProviderDraft?.model ?? ""}
                onChange={(event) =>
                  updateDraft(selectedProvider.id, {
                    model: event.target.value,
                  })
                }
              >
                {selectedProvider.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={selectedProviderDraft?.model ?? ""}
                onChange={(event) =>
                  selectedProvider
                    ? updateDraft(selectedProvider.id, {
                        model: event.target.value,
                      })
                    : undefined
                }
                placeholder="自定义模型 ID"
              />
            )}
          </label>

          <button
            type="button"
            onClick={() => void saveActiveModel()}
            disabled={savingActiveModel || !selectedProvider}
          >
            {savingActiveModel ? "提交中..." : "设为 Active"}
          </button>
        </div>
      </article>

      <div className="provider-list">
        {providers.map((provider) => {
          const draft = drafts[provider.id];
          if (!draft) {
            return null;
          }

          return (
            <article className="models-card" key={provider.id}>
              <div className="provider-card-head">
                <div>
                  <h3>{provider.name}</h3>
                  <p>
                    id: <code>{provider.id}</code>
                  </p>
                </div>
                <span className={provider.has_api_key ? "ok" : "warn"}>
                  {provider.has_api_key ? "已配置" : "未配置"}
                </span>
              </div>

              <div className="provider-form-grid">
                <label className="form-field">
                  API Key
                  <input
                    type="password"
                    value={draft.apiKey}
                    onChange={(event) =>
                      updateDraft(provider.id, {
                        apiKey: event.target.value,
                      })
                    }
                    placeholder={
                      provider.current_api_key
                        ? `当前：${provider.current_api_key}`
                        : provider.api_key_prefix
                          ? `示例：${provider.api_key_prefix}-...`
                          : "输入 API Key"
                    }
                  />
                </label>

                {provider.allow_custom_base_url ? (
                  <label className="form-field">
                    Base URL
                    <input
                      value={draft.baseUrl}
                      onChange={(event) =>
                        updateDraft(provider.id, {
                          baseUrl: event.target.value,
                        })
                      }
                      placeholder="https://your-endpoint/v1"
                    />
                  </label>
                ) : null}
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  onClick={() => void saveProvider(provider)}
                  disabled={savingProviderId === provider.id}
                >
                  {savingProviderId === provider.id ? "保存中..." : "保存 Provider"}
                </button>
                <span>API Key 留空时不会覆盖已保存值。</span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
