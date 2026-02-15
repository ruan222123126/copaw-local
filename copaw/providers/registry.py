# -*- coding: utf-8 -*-
"""Built-in provider definitions and registry."""

from __future__ import annotations

from typing import List, Optional

from .models import ModelInfo, ProviderDefinition

# ---------------------------------------------------------------------------
# Built-in LLM model lists
# ---------------------------------------------------------------------------

MODELSCOPE_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="Qwen/Qwen3-235B-A22B-Instruct-2507",
        name="Qwen3-235B-A22B-Instruct-2507",
    ),
    ModelInfo(id="deepseek-ai/DeepSeek-V3.2", name="DeepSeek-V3.2"),
]

DASHSCOPE_MODELS: List[ModelInfo] = [
    ModelInfo(id="qwen3-max", name="Qwen3 Max"),
    ModelInfo(
        id="qwen3-235b-a22b-thinking-2507",
        name="Qwen3 235B A22B Thinking",
    ),
    ModelInfo(id="deepseek-v3.2", name="DeepSeek-V3.2"),
]

# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

PROVIDER_MODELSCOPE = ProviderDefinition(
    id="modelscope",
    name="ModelScope",
    default_base_url="https://api-inference.modelscope.cn/v1",
    api_key_prefix="ms",
    models=MODELSCOPE_MODELS,
)

PROVIDER_DASHSCOPE = ProviderDefinition(
    id="dashscope",
    name="DashScope",
    default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key_prefix="sk",
    models=DASHSCOPE_MODELS,
)

PROVIDER_CUSTOM = ProviderDefinition(
    id="custom",
    name="Custom",
    default_base_url="",
    api_key_prefix="",
    models=[],
    allow_custom_base_url=True,
)

# Registry: provider_id -> ProviderDefinition
PROVIDERS: dict[str, ProviderDefinition] = {
    PROVIDER_MODELSCOPE.id: PROVIDER_MODELSCOPE,
    PROVIDER_DASHSCOPE.id: PROVIDER_DASHSCOPE,
    PROVIDER_CUSTOM.id: PROVIDER_CUSTOM,
}


def get_provider(provider_id: str) -> Optional[ProviderDefinition]:
    """Return a provider definition by id, or None if not found."""
    return PROVIDERS.get(provider_id)


def list_providers() -> List[ProviderDefinition]:
    """Return all registered provider definitions."""
    return list(PROVIDERS.values())
