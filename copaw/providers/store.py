# -*- coding: utf-8 -*-
"""Reading and writing provider configuration (providers.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import (
    ModelSlotConfig,
    ProviderSettings,
    ProvidersData,
    ResolvedModelConfig,
)
from .registry import PROVIDERS

# ---------------------------------------------------------------------------
# JSON file path
# ---------------------------------------------------------------------------

_PROVIDERS_DIR = Path(__file__).resolve().parent
_PROVIDERS_JSON = _PROVIDERS_DIR / "providers.json"


def get_providers_json_path() -> Path:
    """Return the default providers.json path."""
    return _PROVIDERS_JSON


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_base_url(settings: ProviderSettings, defn) -> None:
    """Fill missing ``base_url`` from the provider definition."""
    if not settings.base_url and defn.default_base_url:
        settings.base_url = defn.default_base_url


def _parse_new_format(raw: dict):
    """Parse the new-format providers.json.

    Returns ``(providers, active_llm)``.
    """
    providers: dict[str, ProviderSettings] = {}
    for key, value in raw.get("providers", {}).items():
        if isinstance(value, dict):
            providers[key] = ProviderSettings.model_validate(
                value,
            )
    llm_raw = raw.get("active_llm")
    active_llm = (
        ModelSlotConfig.model_validate(llm_raw)
        if isinstance(llm_raw, dict)
        else ModelSlotConfig()
    )
    return providers, active_llm


def _parse_legacy_format(raw: dict):
    """Parse the legacy providers.json (flat keys).

    Returns ``(providers, active_llm)``.
    """
    providers: dict[str, ProviderSettings] = {}
    old_active = raw.get("active_provider", "")
    old_model = ""
    for key, value in raw.items():
        if key in ("active_provider", "active_llm"):
            continue
        if not isinstance(value, dict):
            continue
        model_val = value.pop("model", "")
        providers[key] = ProviderSettings.model_validate(value)
        if key == old_active and model_val:
            old_model = model_val
    active_llm = (
        ModelSlotConfig(provider_id=old_active, model=old_model)
        if old_active
        else ModelSlotConfig()
    )
    return providers, active_llm


def _validate_active_llm(
    active_llm: ModelSlotConfig,
    providers: dict[str, ProviderSettings],
) -> ModelSlotConfig:
    """Clear *active_llm* if its provider is not configured."""
    if not active_llm.provider_id:
        return active_llm
    defn = PROVIDERS.get(active_llm.provider_id)
    settings = providers.get(active_llm.provider_id)
    if settings is None:
        return ModelSlotConfig()
    if defn and not defn.allow_custom_base_url and not settings.api_key:
        return ModelSlotConfig()
    if defn and defn.allow_custom_base_url and not settings.base_url:
        return ModelSlotConfig()
    return active_llm


def _ensure_all_providers(
    providers: dict[str, ProviderSettings],
) -> None:
    """Ensure every registered provider has an entry."""
    for pid, defn in PROVIDERS.items():
        if pid not in providers:
            providers[pid] = ProviderSettings(
                base_url=defn.default_base_url,
            )
        else:
            _ensure_base_url(providers[pid], defn)


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------


def load_providers_json(
    path: Optional[Path] = None,
) -> ProvidersData:
    """Load providers.json, creating/repairing as needed."""
    if path is None:
        path = get_providers_json_path()

    providers: dict[str, ProviderSettings] = {}
    active_llm = ModelSlotConfig()

    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw: dict = json.load(fh)
            if "providers" in raw and isinstance(
                raw["providers"],
                dict,
            ):
                providers, active_llm = _parse_new_format(raw)
            else:
                providers, active_llm = _parse_legacy_format(raw)
        except (json.JSONDecodeError, ValueError):
            providers = {}

    _ensure_all_providers(providers)
    active_llm = _validate_active_llm(active_llm, providers)

    data = ProvidersData(
        providers=providers,
        active_llm=active_llm,
    )
    save_providers_json(data, path)
    return data


def save_providers_json(
    data: ProvidersData,
    path: Optional[Path] = None,
) -> None:
    """Write provider settings to providers.json."""
    if path is None:
        path = get_providers_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    out: dict = {
        "providers": {
            pid: settings.model_dump(mode="json")
            for pid, settings in data.providers.items()
        },
        "active_llm": data.active_llm.model_dump(mode="json"),
    }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Mutators (load → modify → save → return full state)
# ---------------------------------------------------------------------------


def update_provider_settings(
    provider_id: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> ProvidersData:
    """Partially update a provider's settings (api_key / base_url only).

    Returns the updated full state.
    """
    data = load_providers_json()
    settings = data.providers.get(provider_id, ProviderSettings())

    if api_key is not None:
        settings.api_key = api_key
    if base_url is not None:
        settings.base_url = base_url
    if not settings.base_url:
        defn = PROVIDERS.get(provider_id)
        if defn and defn.default_base_url:
            settings.base_url = defn.default_base_url

    data.providers[provider_id] = settings

    # If the API key was revoked (set to empty) and this provider is the
    # active LLM provider, clear the active LLM slot as well.
    if api_key == "" and data.active_llm.provider_id == provider_id:
        data.active_llm = ModelSlotConfig()

    save_providers_json(data)
    return data


def set_active_llm(provider_id: str, model: str) -> ProvidersData:
    """Set the active LLM model slot. Returns updated state."""
    data = load_providers_json()
    data.active_llm = ModelSlotConfig(provider_id=provider_id, model=model)
    save_providers_json(data)
    return data


# ---------------------------------------------------------------------------
# Query — resolved configs for agent use
# ---------------------------------------------------------------------------


def _resolve_slot(
    slot: ModelSlotConfig,
    data: ProvidersData,
) -> Optional[ResolvedModelConfig]:
    """Resolve a model slot to a full config (model + provider's URL + key)."""
    if not slot.provider_id or not slot.model:
        return None
    settings = data.providers.get(slot.provider_id)
    if settings is None:
        return None
    return ResolvedModelConfig(
        model=slot.model,
        base_url=settings.base_url,
        api_key=settings.api_key,
    )


def get_active_llm_config() -> Optional[ResolvedModelConfig]:
    """Return resolved config for the active LLM slot, or ``None``."""
    data = load_providers_json()
    return _resolve_slot(data.active_llm, data)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """Mask an API key for safe display.

    Example: ``"sk-abcdefghijk"`` → ``"sk-****hijk"``
    """
    if not api_key:
        return ""
    if len(api_key) <= visible_chars:
        return "*" * len(api_key)
    prefix = api_key[:3] if len(api_key) > 3 else ""
    suffix = api_key[-visible_chars:]
    hidden_len = len(api_key) - len(prefix) - visible_chars
    return f"{prefix}{'*' * max(hidden_len, 4)}{suffix}"
