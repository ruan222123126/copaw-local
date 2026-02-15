# -*- coding: utf-8 -*-
"""Pydantic data models for providers and models."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """A single model offered by a provider."""

    id: str = Field(..., description="Model identifier used in API calls")
    name: str = Field(..., description="Human-readable model name")


class ProviderDefinition(BaseModel):
    """Static definition of a provider (built-in or custom)."""

    id: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Human-readable provider name")
    default_base_url: str = Field(
        default="",
        description="Default API base URL",
    )
    api_key_prefix: str = Field(
        default="",
        description="Expected prefix for the API key",
    )
    models: List[ModelInfo] = Field(
        default_factory=list,
        description="Built-in LLM model list",
    )
    allow_custom_base_url: bool = Field(
        default=False,
        description="Whether the user can set a custom base_url",
    )


class ProviderSettings(BaseModel):
    """Per-provider settings stored in providers.json (URL + API key only)."""

    base_url: str = Field(default="", description="API base URL")
    api_key: str = Field(default="", description="API key")


class ModelSlotConfig(BaseModel):
    """Configuration for one active model slot (LLM)."""

    provider_id: str = Field(
        default="",
        description="ID of the chosen provider",
    )
    model: str = Field(default="", description="Selected model identifier")


class ProvidersData(BaseModel):
    """Top-level structure of providers.json."""

    providers: Dict[str, ProviderSettings] = Field(default_factory=dict)
    active_llm: ModelSlotConfig = Field(default_factory=ModelSlotConfig)


class ProviderInfo(BaseModel):
    """Provider info returned by API (definition + current config)."""

    id: str
    name: str
    api_key_prefix: str
    models: List[ModelInfo]
    allow_custom_base_url: bool = Field(default=False)
    has_api_key: bool = Field(
        default=False,
        description="Whether api_key is configured",
    )
    current_api_key: str = Field(
        default="",
        description="Currently configured API key (masked)",
    )
    current_base_url: str = Field(
        default="",
        description="Current base_url",
    )


class ActiveModelsInfo(BaseModel):
    """Response model for active LLM configuration."""

    active_llm: ModelSlotConfig


class ResolvedModelConfig(BaseModel):
    """Resolved config for a model slot (URL + key + model)."""

    model: str = Field(default="", description="Model identifier")
    base_url: str = Field(default="", description="API base URL")
    api_key: str = Field(default="", description="API key")
