# -*- coding: utf-8 -*-
"""Provider management — models, registry + persistent store."""

from .models import (
    ActiveModelsInfo,
    ModelInfo,
    ModelSlotConfig,
    ProviderDefinition,
    ProviderInfo,
    ProviderSettings,
    ProvidersData,
    ResolvedModelConfig,
)
from .registry import (
    PROVIDERS,
    get_provider,
    list_providers,
)
from .store import (
    get_active_llm_config,
    load_providers_json,
    mask_api_key,
    save_providers_json,
    set_active_llm,
    update_provider_settings,
)

__all__ = [
    # models
    "ActiveModelsInfo",
    "ModelInfo",
    "ModelSlotConfig",
    "ProviderDefinition",
    "ProviderInfo",
    "ProviderSettings",
    "ProvidersData",
    "ResolvedModelConfig",
    # registry
    "PROVIDERS",
    "get_provider",
    "list_providers",
    # store
    "get_active_llm_config",
    "load_providers_json",
    "mask_api_key",
    "save_providers_json",
    "set_active_llm",
    "update_provider_settings",
]
