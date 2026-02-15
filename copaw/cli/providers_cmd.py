# -*- coding: utf-8 -*-
"""CLI commands for managing LLM providers."""
from __future__ import annotations

from typing import Optional

import click

from ..providers import (
    PROVIDERS,
    list_providers,
    load_providers_json,
    mask_api_key,
    set_active_llm,
    update_provider_settings,
)
from .utils import prompt_choice


# ---------------------------------------------------------------------------
# Reusable interactive helpers
# ---------------------------------------------------------------------------


def _select_provider_interactive(
    prompt_text: str = "Select provider:",
    *,
    default_pid: str = "",
) -> str:
    """Prompt user to pick a provider. Returns provider_id.

    Each option is annotated with ✓ (configured) or ✗ (not configured).
    """
    data = load_providers_json()
    all_providers = list_providers()

    labels: list[str] = []
    ids: list[str] = []
    for d in all_providers:
        s = data.providers.get(d.id)
        if d.allow_custom_base_url:
            configured = bool(s and s.base_url)
        else:
            configured = bool(s and s.api_key)
        mark = "✓" if configured else "✗"
        labels.append(f"{d.name} ({d.id}) [{mark}]")
        ids.append(d.id)

    default_label: Optional[str] = None
    if default_pid in ids:
        default_label = labels[ids.index(default_pid)]

    chosen_label = prompt_choice(
        prompt_text,
        options=labels,
        default=default_label,
    )
    return ids[labels.index(chosen_label)]


def configure_provider_api_key_interactive(
    provider_id: str | None = None,
) -> str:
    """Interactively configure a provider's API key.

    Returns the chosen provider_id.
    """
    data = load_providers_json()

    if provider_id is None:
        provider_id = _select_provider_interactive(
            "Select provider to configure API key:",
        )

    defn = PROVIDERS[provider_id]
    current = data.providers.get(provider_id)
    current_key = current.api_key if current else ""

    # Base URL (only for custom)
    base_url: Optional[str] = None
    if defn.allow_custom_base_url:
        current_url = current.base_url if current else ""
        base_url = click.prompt(
            "Base URL (OpenAI-compatible endpoint)",
            default=current_url or "",
            show_default=bool(current_url),
        ).strip()
        if not base_url:
            click.echo(
                click.style(
                    "Error: base_url is required for custom provider.",
                    fg="red",
                ),
            )
            raise SystemExit(1)

    # API key
    if defn.api_key_prefix:
        hint = f"prefix: {defn.api_key_prefix}"
    else:
        hint = "optional for self-hosted"

    api_key = click.prompt(
        f"API key ({hint})",
        default=current_key or "",
        hide_input=True,
        show_default=False,
        prompt_suffix=f" [{'set' if current_key else 'not set'}]: ",
    )

    update_provider_settings(
        provider_id,
        api_key=api_key if api_key else None,
        base_url=base_url,
    )

    click.echo(
        f"✓ {defn.name} — API Key: {mask_api_key(api_key) or '(not set)'}"
        + (f", Base URL: {base_url}" if base_url else ""),
    )
    return provider_id


def _pick_model_from_list(
    models: list,
    prompt_text: str,
    current_model: str = "",
) -> str:
    """Let user select from a built-in model list. Returns model id."""
    labels = [m.name for m in models]
    ids = [m.id for m in models]

    default_label: Optional[str] = None
    if current_model in ids:
        default_label = labels[ids.index(current_model)]

    chosen = prompt_choice(prompt_text, options=labels, default=default_label)
    return ids[labels.index(chosen)]


def _pick_model_free_text(prompt_text: str, current_model: str = "") -> str:
    """Free-text model input (for custom provider). Returns model id."""
    model = click.prompt(prompt_text, default=current_model or "").strip()
    if not model:
        click.echo(click.style("Error: model name is required.", fg="red"))
        raise SystemExit(1)
    return model


def _filter_eligible(data, all_providers):
    """Return providers that are already configured."""
    eligible = []
    for d in all_providers:
        s = data.providers.get(d.id)
        if d.allow_custom_base_url:
            if s and s.base_url:
                eligible.append(d)
        elif s and s.api_key:
            eligible.append(d)
    return eligible


def _select_llm_model(defn, pid, current_slot, *, use_defaults):
    """Pick a model for the given provider. Returns model id (may be empty)."""
    cur = current_slot.model if current_slot.provider_id == pid else ""
    if use_defaults:
        return cur or (defn.models[0].id if defn.models else "")

    if defn.models:
        return _pick_model_from_list(
            defn.models,
            "Select LLM model:",
            current_model=cur,
        )
    return _pick_model_free_text(
        "LLM model name (required):",
        current_model=cur,
    )


def configure_llm_slot_interactive(
    *,
    use_defaults: bool = False,
) -> None:
    """Interactively configure the active LLM model slot.

    Only providers that are already configured (api_key for built-in,
    base_url for custom) are shown.  When *use_defaults* is True no
    prompts are shown: first eligible provider and first model are used,
    or LLM config is skipped if no provider is configured.
    """
    data = load_providers_json()
    all_providers = list_providers()
    current_slot = data.active_llm

    eligible = _filter_eligible(data, all_providers)

    if not eligible:
        if use_defaults:
            click.echo(
                "No LLM provider configured. Run 'copaw providers config' "
                "to configure later.",
            )
            return
        msg = "No providers are configured yet. Let's configure one now."
        click.echo(click.style(msg, fg="yellow"))
        configure_provider_api_key_interactive()
        data = load_providers_json()
        current_slot = data.active_llm
        eligible = _filter_eligible(data, all_providers)
        if not eligible:
            click.echo(
                click.style(
                    "Error: provider configuration failed.",
                    fg="red",
                ),
            )
            raise SystemExit(1)

    ids = [d.id for d in eligible]
    if use_defaults:
        pid = (
            current_slot.provider_id
            if current_slot.provider_id in ids
            else ids[0]
        )
    else:
        labels = [f"{d.name} ({d.id})" for d in eligible]
        default_label = (
            labels[ids.index(current_slot.provider_id)]
            if current_slot.provider_id in ids
            else None
        )
        chosen_label = prompt_choice(
            "Select provider for LLM:",
            options=labels,
            default=default_label,
        )
        pid = ids[labels.index(chosen_label)]

    defn = PROVIDERS[pid]
    model = _select_llm_model(
        defn,
        pid,
        current_slot,
        use_defaults=use_defaults,
    )
    if not model and use_defaults:
        click.echo(
            f"No default model for {defn.name}. "
            "Run 'copaw providers config' to set one.",
        )
        return
    set_active_llm(pid, model)
    click.echo(f"✓ LLM: {defn.name} / {model}")


def configure_providers_interactive(
    *,
    use_defaults: bool = False,
) -> None:
    """Full interactive setup: configure provider API key + LLM.

    Used by ``init_cmd`` and ``providers config``.

    When *use_defaults* is True no prompts are shown: if a provider is
    already configured, its first model is set as active; otherwise
    LLM config is skipped.
    """
    if use_defaults:
        configure_llm_slot_interactive(use_defaults=True)
        return

    # Interactive: first configure provider API keys, then LLM model
    click.echo("\n--- Provider API Key Configuration ---")
    while True:
        configure_provider_api_key_interactive()
        if not click.confirm(
            "Configure another provider's API key?",
            default=False,
        ):
            break

    click.echo("\n--- Active LLM Model ---")
    configure_llm_slot_interactive()


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group("models")
def models_group() -> None:
    """Manage LLM models and provider configuration."""


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@models_group.command("list")
def list_cmd() -> None:
    """Show all providers and their current configuration."""
    data = load_providers_json()

    click.echo("\n=== Providers ===")
    for defn in list_providers():
        settings = data.providers.get(defn.id)

        click.echo(f"\n{'─' * 44}")
        click.echo(f"  {defn.name} ({defn.id})")
        click.echo(f"{'─' * 44}")
        if defn.allow_custom_base_url:
            url = settings.base_url or "(not set)" if settings else "(not set)"
            click.echo(f"  {'base_url':16s}: {url}")
        key = (
            mask_api_key(settings.api_key) or "(not set)"
            if settings
            else "(not set)"
        )
        click.echo(f"  {'api_key':16s}: {key}")
        if defn.api_key_prefix:
            click.echo(f"  {'api_key_prefix':16s}: {defn.api_key_prefix}")
    # Active model slot
    click.echo(f"\n{'═' * 44}")
    click.echo("  Active Model Slot")
    click.echo(f"{'═' * 44}")

    llm = data.active_llm
    if llm.provider_id and llm.model:
        click.echo(f"  {'LLM':16s}: {llm.provider_id} / {llm.model}")
    else:
        click.echo(f"  {'LLM':16s}: (not configured)")

    click.echo()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@models_group.command("config")
def config_cmd() -> None:
    """Interactively configure providers and active models."""
    configure_providers_interactive()


# ---------------------------------------------------------------------------
# config-key
# ---------------------------------------------------------------------------


@models_group.command("config-key")
@click.argument("provider_id", required=False, default=None)
def config_key_cmd(provider_id: str | None) -> None:
    """Configure a provider's API key."""
    if provider_id is not None and provider_id not in PROVIDERS:
        click.echo(click.style(f"Unknown provider: {provider_id}", fg="red"))
        raise SystemExit(1)
    configure_provider_api_key_interactive(provider_id)


# ---------------------------------------------------------------------------
# set-llm
# ---------------------------------------------------------------------------


@models_group.command("set-llm")
def set_llm_cmd() -> None:
    """Interactively set the active LLM model."""
    configure_llm_slot_interactive()
