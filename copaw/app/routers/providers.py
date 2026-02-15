# -*- coding: utf-8 -*-
"""API routes for LLM providers and models."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel, Field

from ...providers import (
    ActiveModelsInfo,
    ProviderDefinition,
    ProviderInfo,
    ProvidersData,
    get_provider,
    list_providers,
    load_providers_json,
    mask_api_key,
    set_active_llm,
    update_provider_settings,
)

router = APIRouter(prefix="/models", tags=["models"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProviderConfigRequest(BaseModel):
    """Request body for configuring a provider (api_key / base_url only)."""

    api_key: Optional[str] = Field(
        default=None,
        description="API key for the provider",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL "
        "(only for providers with allow_custom_base_url)",
    )


class ModelSlotRequest(BaseModel):
    """Request body for setting an active LLM model slot."""

    provider_id: str = Field(..., description="Provider to use")
    model: str = Field(..., description="Model identifier")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_provider_info(
    provider: ProviderDefinition,
    data: ProvidersData,
) -> ProviderInfo:
    """Build a ProviderInfo from a definition and the current stored state."""
    settings = data.providers.get(provider.id)

    # Custom providers are "configured" when base_url is set;
    # built-in providers are "configured" when api_key is set.
    if provider.allow_custom_base_url:
        configured = bool(settings and settings.base_url)
    else:
        configured = bool(settings and settings.api_key)

    return ProviderInfo(
        id=provider.id,
        name=provider.name,
        api_key_prefix=provider.api_key_prefix,
        models=provider.models,
        allow_custom_base_url=provider.allow_custom_base_url,
        has_api_key=configured,
        current_api_key=mask_api_key(settings.api_key) if settings else "",
        current_base_url=settings.base_url if settings else "",
    )


# ---------------------------------------------------------------------------
# Endpoints — provider CRUD
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[ProviderInfo],
    summary="List all providers",
    description="Return all available providers "
    "with their current configuration.",
)
async def list_all_providers() -> List[ProviderInfo]:
    """List all registered providers."""
    data = load_providers_json()
    return [_build_provider_info(p, data) for p in list_providers()]


@router.put(
    "/{provider_id}/config",
    response_model=ProviderInfo,
    summary="Configure a provider",
    description="Set api_key and/or base_url for a provider. "
    "Values are persisted to providers.json.",
)
async def configure_provider(
    provider_id: str = Path(..., description="Provider identifier"),
    body: ProviderConfigRequest = Body(
        ...,
        description="Provider configuration to update",
    ),
) -> ProviderInfo:
    """Configure (or update) a provider's api_key / base_url."""
    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_id}' not found",
        )

    base_url = body.base_url if provider.allow_custom_base_url else None

    data = update_provider_settings(
        provider_id,
        api_key=body.api_key,
        base_url=base_url,
    )
    return _build_provider_info(provider, data)


# ---------------------------------------------------------------------------
# Endpoints — active model slots
# ---------------------------------------------------------------------------


@router.get(
    "/active",
    response_model=ActiveModelsInfo,
    summary="Get active LLM model configuration",
)
async def get_active_models() -> ActiveModelsInfo:
    """Return current active_llm slot."""
    data = load_providers_json()
    return ActiveModelsInfo(
        active_llm=data.active_llm,
    )


@router.put(
    "/active",
    response_model=ActiveModelsInfo,
    summary="Set active LLM model",
    description="Choose a provider + model for the LLM slot. "
    "Provider must have api_key configured (except custom).",
)
async def set_active_model(
    body: ModelSlotRequest = Body(..., description="LLM model to activate"),
) -> ActiveModelsInfo:
    """Set the active LLM model slot."""
    provider = get_provider(body.provider_id)
    if provider is None:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{body.provider_id}' not found",
        )

    # Provider must be configured (api_key for built-in, base_url for custom)
    data = load_providers_json()
    settings = data.providers.get(body.provider_id)
    if not provider.allow_custom_base_url and (
        not settings or not settings.api_key
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider.name}' has no API key configured. "
            "Please configure the API key first.",
        )
    if provider.allow_custom_base_url and (
        not settings or not settings.base_url
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Custom provider '{provider.name}' "
            "has no base_url configured. "
            "Please configure the base URL first.",
        )

    if not body.model:
        raise HTTPException(
            status_code=400,
            detail="Model is required.",
        )

    data = set_active_llm(body.provider_id, body.model)

    return ActiveModelsInfo(
        active_llm=data.active_llm,
    )
