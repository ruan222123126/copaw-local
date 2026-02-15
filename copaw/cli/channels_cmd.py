# -*- coding: utf-8 -*-
"""CLI channel: list and interactively configure channels in config.json."""
from __future__ import annotations

import click

from ..config import (
    get_config_path,
    load_config,
    save_config,
)
from ..config.config import (
    Config,
    ConsoleConfig,
    DiscordConfig,
    DingTalkConfig,
    FeishuConfig,
    IMessageChannelConfig,
    QQConfig,
)
from .utils import prompt_confirm, prompt_path, prompt_select
from ..constant import get_available_channels

# Fields that contain secrets — display masked in ``list``
_SECRET_FIELDS = {"bot_token", "client_secret", "app_secret", "http_proxy_auth"}

_ALL_CHANNEL_NAMES = {
    "imessage": "iMessage",
    "discord": "Discord",
    "dingtalk": "DingTalk",
    "feishu": "Feishu",
    "qq": "QQ",
    "console": "Console",
}
# Public alias for tests and external use.
CHANNEL_NAMES = _ALL_CHANNEL_NAMES


def _get_channel_names() -> dict[str, str]:
    """Return channel names filtered by COPAW_ENABLED_CHANNELS."""
    available = get_available_channels()
    return {k: v for k, v in _ALL_CHANNEL_NAMES.items() if k in available}


def _mask(value: str) -> str:
    """Mask a secret value, keeping first 4 chars visible."""
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"


# ── per-channel interactive configurators ──────────────────────────


def configure_imessage(
    current_config: IMessageChannelConfig,
) -> IMessageChannelConfig:
    """Configure iMessage channel interactively."""
    click.echo("\n=== Configure iMessage Channel ===")

    enabled = prompt_confirm(
        "Enable iMessage channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., @bot)",
        default=current_config.bot_prefix or "[BOT]",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    db_path = prompt_path(
        "iMessage database path",
        default=current_config.db_path or "~/Library/Messages/chat.db",
    )
    current_config.db_path = db_path

    poll_sec = click.prompt(
        "Poll interval (seconds)",
        default=current_config.poll_sec,
        type=float,
    )
    current_config.poll_sec = poll_sec

    return current_config


def configure_discord(current_config: DiscordConfig) -> DiscordConfig:
    """Configure Discord channel interactively."""
    click.echo("\n=== Configure Discord Channel ===")

    enabled = prompt_confirm(
        "Enable Discord channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., @bot)",
        default=current_config.bot_prefix or "[BOT]",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    bot_token = click.prompt(
        "Discord Bot Token",
        default=current_config.bot_token or "",
        hide_input=True,
        type=str,
    )
    current_config.bot_token = bot_token

    use_proxy = prompt_confirm(
        "Use HTTP proxy?",
        default=bool(current_config.http_proxy),
    )

    if use_proxy:
        http_proxy = click.prompt(
            "HTTP proxy address (e.g., http://127.0.0.1:7890)",
            default=current_config.http_proxy or "",
            type=str,
        )
        current_config.http_proxy = http_proxy

        use_proxy_auth = prompt_confirm(
            "Does proxy require authentication?",
            default=bool(current_config.http_proxy_auth),
        )

        if use_proxy_auth:
            http_proxy_auth = click.prompt(
                "Proxy authentication (format: username:password)",
                default=current_config.http_proxy_auth or "",
                hide_input=True,
                type=str,
            )
            current_config.http_proxy_auth = http_proxy_auth
        else:
            current_config.http_proxy_auth = ""
    else:
        current_config.http_proxy = ""
        current_config.http_proxy_auth = ""

    return current_config


def configure_dingtalk(current_config: DingTalkConfig) -> DingTalkConfig:
    """Configure DingTalk channel interactively."""
    click.echo("\n=== Configure DingTalk Channel ===")

    enabled = prompt_confirm(
        "Enable DingTalk channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., @bot)",
        default=current_config.bot_prefix or "[BOT]",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    client_id = click.prompt(
        "DingTalk Client ID",
        default=current_config.client_id or "",
        type=str,
    )
    current_config.client_id = client_id

    client_secret = click.prompt(
        "DingTalk Client Secret",
        default=current_config.client_secret or "",
        hide_input=True,
        type=str,
    )
    current_config.client_secret = client_secret

    return current_config


def configure_feishu(current_config: FeishuConfig) -> FeishuConfig:
    """Configure Feishu channel interactively."""
    click.echo("\n=== Configure Feishu Channel ===")

    enabled = prompt_confirm(
        "Enable Feishu channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., @bot)",
        default=current_config.bot_prefix or "[BOT]",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    app_id = click.prompt(
        "Feishu App ID",
        default=current_config.app_id or "",
        type=str,
    )
    current_config.app_id = app_id

    app_secret = click.prompt(
        "Feishu App Secret",
        default=current_config.app_secret or "",
        hide_input=True,
        type=str,
    )
    current_config.app_secret = app_secret

    return current_config


def configure_qq(current_config: QQConfig) -> QQConfig:
    """Configure QQ channel interactively."""
    click.echo("\n=== Configure QQ Channel ===")

    enabled = prompt_confirm(
        "Enable QQ channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., @bot)",
        default=current_config.bot_prefix or "[BOT]",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    app_id = click.prompt(
        "QQ App ID",
        default=current_config.app_id or "",
        type=str,
    )
    current_config.app_id = app_id

    client_secret = click.prompt(
        "QQ Client Secret",
        default=current_config.client_secret or "",
        hide_input=True,
        type=str,
    )
    current_config.client_secret = client_secret

    return current_config


def configure_console(current_config: ConsoleConfig) -> ConsoleConfig:
    """Configure Console channel interactively."""
    click.echo("\n=== Configure Console Channel ===")

    enabled = prompt_confirm(
        "Enable Console channel?",
        default=current_config.enabled,
    )

    if not enabled:
        current_config.enabled = False
        return current_config

    current_config.enabled = True

    bot_prefix = click.prompt(
        "Bot prefix (e.g., [BOT])",
        default=current_config.bot_prefix or "[BOT] ",
        type=str,
    )
    current_config.bot_prefix = bot_prefix

    return current_config


# ── reusable channel configuration flow (used by init_cmd too) ─────

# Full registry — filtered at runtime by get_channel_configurators().
_ALL_CHANNEL_CONFIGURATORS = {
    "imessage": ("iMessage", configure_imessage),
    "discord": ("Discord", configure_discord),
    "dingtalk": ("DingTalk", configure_dingtalk),
    "feishu": ("Feishu", configure_feishu),
    "qq": ("QQ", configure_qq),
    "console": ("Console", configure_console),
}


def get_channel_configurators() -> dict:
    """Return channel configurators filtered by COPAW_ENABLED_CHANNELS."""
    available = get_available_channels()
    return {
        k: v for k, v in _ALL_CHANNEL_CONFIGURATORS.items() if k in available
    }


def configure_channels_interactive(config: Config) -> None:
    """Run the interactive channel selection / configuration loop.

    Mutates *config.channels* in-place.
    """
    configurators = get_channel_configurators()
    click.echo("\n=== Channel Configuration ===")

    while True:
        channel_choices: list[tuple[str, str]] = []
        for channel_key, (channel_name, _) in configurators.items():
            channel_config = getattr(config.channels, channel_key)
            status = "✓" if channel_config.enabled else "✗"
            channel_choices.append(
                (f"{channel_name} [{status}]", channel_key),
            )
        channel_choices.append(("Save and exit", "exit"))

        click.echo()
        choice = prompt_select(
            "Select a channel to configure:",
            options=channel_choices,
        )

        if choice is None:
            click.echo("\n\nOperation cancelled.")
            return

        if choice == "exit":
            break

        channel_name, configure_func = configurators[choice]
        current_config = getattr(config.channels, choice)
        updated_config = configure_func(current_config)
        setattr(config.channels, choice, updated_config)

    # Show enabled channels summary
    enabled_channels = [
        name
        for key, (name, _) in configurators.items()
        if getattr(config.channels, key).enabled
    ]

    if enabled_channels:
        click.echo(
            f"\n✓ Enabled channels: {', '.join(enabled_channels)}",
        )
    else:
        click.echo("\n⚠ Warning: No channels enabled!")


# ── CLI commands ───────────────────────────────────────────────────


@click.group("channels")
def channels_group() -> None:
    """Manage channel configuration (iMessage/Discord/DingTalk/Feishu/QQ/Console)."""


@channels_group.command("list")
def list_cmd() -> None:
    """Show current channel configuration."""
    config_path = get_config_path()

    if not config_path.is_file():
        click.echo(f"Config not found: {config_path}")
        click.echo("Will load default config.")
        click.echo("Run `copaw channels config` to create one.")
        cfg = load_config()
    else:
        cfg = load_config(config_path)

    for key, name in _get_channel_names().items():
        ch = getattr(cfg.channels, key)
        status = (
            click.style("enabled", fg="green")
            if ch.enabled
            else click.style("disabled", fg="red")
        )
        click.echo(f"\n{'─' * 40}")
        click.echo(f"  {name}  [{status}]")
        click.echo(f"{'─' * 40}")

        for field_name in type(ch).model_fields:
            if field_name == "enabled":
                continue
            value = getattr(ch, field_name)
            display = (
                _mask(str(value)) if field_name in _SECRET_FIELDS else value
            )
            click.echo(f"  {field_name:20s}: {display}")

    click.echo()


@channels_group.command("config")
def configure_cmd() -> None:
    """Interactively configure channels."""
    config_path = get_config_path()
    working_dir = config_path.parent

    click.echo(f"Working dir: {working_dir}")
    working_dir.mkdir(parents=True, exist_ok=True)

    existing = load_config(config_path) if config_path.is_file() else Config()

    configure_channels_interactive(existing)

    save_config(existing, config_path)
    click.echo(f"\n✓ Configuration saved to {config_path}")
