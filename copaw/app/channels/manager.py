# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import logging

from typing import Callable, List, Optional, Any, Dict, TYPE_CHECKING

from .base import BaseChannel, ProcessHandler
from .imessage import IMessageChannel
from .discord_ import DiscordChannel
from .dingtalk import DingTalkChannel
from .feishu import FeishuChannel
from .qq import QQChannel
from .console import ConsoleChannel
from ...constant import get_available_channels

if TYPE_CHECKING:
    from ...config.config import Config

logger = logging.getLogger(__name__)

# Callback when user reply was sent: (channel, user_id, session_id)
OnLastDispatch = Optional[Callable[[str, str, str], None]]

# channel_key -> Channel class (used for building from env / config)
_CHANNEL_CLASSES: dict[str, type[BaseChannel]] = {
    "imessage": IMessageChannel,
    "discord": DiscordChannel,
    "dingtalk": DingTalkChannel,
    "feishu": FeishuChannel,
    "qq": QQChannel,
    "console": ConsoleChannel,
}


class ChannelManager:
    def __init__(self, channels: List[BaseChannel]):
        self.channels = channels
        self._lock = asyncio.Lock()

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_last_dispatch: OnLastDispatch = None,
    ) -> "ChannelManager":
        """
        Create channels from env and inject unified process
        (AgentRequest -> Event stream).
        process is typically runner.stream_query, handled by AgentApp's
        process endpoint.
        on_last_dispatch: called when a user send+reply was sent.
        """
        available = get_available_channels()
        channels: list[BaseChannel] = [
            ch_cls.from_env(process, on_reply_sent=on_last_dispatch)
            for key, ch_cls in _CHANNEL_CLASSES.items()
            if key in available
        ]
        return cls(channels)

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: "Config",
        on_last_dispatch: OnLastDispatch = None,
    ) -> "ChannelManager":
        """Create channels from config (config.json)."""
        available = get_available_channels()
        ch = config.channels
        show_tool_details = getattr(config, "show_tool_details", True)

        channels: list[BaseChannel] = []
        for key, ch_cls in _CHANNEL_CLASSES.items():
            if key not in available:
                continue
            ch_cfg = getattr(ch, key, None)
            if ch_cfg is None:
                continue
            # ConsoleChannel.from_config does not accept show_tool_details
            if key == "console":
                channels.append(
                    ch_cls.from_config(
                        process,
                        ch_cfg,
                        on_reply_sent=on_last_dispatch,
                    ),
                )
            else:
                channels.append(
                    ch_cls.from_config(
                        process,
                        ch_cfg,
                        on_reply_sent=on_last_dispatch,
                        show_tool_details=show_tool_details,
                    ),
                )
        return cls(channels)

    async def start_all(self) -> None:
        async with self._lock:
            snapshot = list(self.channels)
        logger.info(f"starting channels={[g.channel for g in snapshot]}")
        for g in snapshot:
            try:
                await g.start()
            except Exception:
                logger.exception(f"failed to start channels={g.channel}")

    async def stop_all(self) -> None:
        async with self._lock:
            snapshot = list(self.channels)

        async def _stop(ch):
            try:
                await ch.stop()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(f"failed to stop channels={ch.channel}")

        await asyncio.gather(*[_stop(g) for g in reversed(snapshot)])

    async def get_channel(self, channel: str) -> Optional[BaseChannel]:
        async with self._lock:
            for ch in self.channels:
                if ch.channel == channel:
                    return ch
            return None

    async def replace_channel(
        self,
        new_channel: BaseChannel,
    ) -> None:
        """Replace a single channel by name.

        Flow: start new (outside lock) → swap + stop old (inside lock).
        Lock only guards the swap+stop so it is held as briefly as possible.

        Args:
            new_channel: New channel instance to replace with
        """
        # 1) Start new channel outside lock (may be slow, e.g. Discord gateway)
        new_channel_name = new_channel.channel
        logger.info(f"Pre-starting new channel: {new_channel_name}")
        try:
            await new_channel.start()
        except Exception:
            logger.exception(
                f"Failed to start new channel: {new_channel_name}",
            )
            try:
                await new_channel.stop()
            except Exception:
                pass
            raise

        # 2) Swap + stop old inside lock
        async with self._lock:
            old_channel = None
            for i, ch in enumerate[BaseChannel](self.channels):
                if ch.channel == new_channel_name:
                    old_channel = ch
                    self.channels[i] = new_channel
                    break

            if old_channel is None:
                logger.info(f"Adding new channel: {new_channel_name}")
                self.channels.append(new_channel)
            else:
                logger.info(f"Stopping old channel: {old_channel.channel}")
                try:
                    await old_channel.stop()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception(
                        f"Failed to stop old channel: {old_channel.channel}",
                    )

    async def send_event(
        self,
        *,
        channel: str,
        user_id: str,
        session_id: str,
        event: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        ch = await self.get_channel(channel)
        if not ch:
            raise KeyError(f"channel not found: {channel}")
        merged_meta = dict(meta or {})
        merged_meta["session_id"] = session_id
        merged_meta["user_id"] = user_id
        bot_prefix = getattr(ch, "bot_prefix", None) or getattr(
            ch,
            "_bot_prefix",
            None,
        )
        if bot_prefix and "bot_prefix" not in merged_meta:
            merged_meta["bot_prefix"] = bot_prefix
        await ch.send_event(
            user_id=user_id,
            session_id=session_id,
            event=event,
            meta=merged_meta,
        )

    async def send_text(
        self,
        *,
        channel: str,
        user_id: str,
        session_id: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send plain text to a specific channel
        (used for scheduled jobs like task_type='text').
        """
        ch = await self.get_channel(channel.lower())
        if not ch:
            raise KeyError(f"channel not found: {channel}")

        # Convert (user_id, session_id) into the channel-specific target handle
        to_handle = ch.to_handle_from_target(
            user_id=user_id,
            session_id=session_id,
        )
        ch_name = getattr(ch, "channel", channel)
        logger.info(
            "channel send_text: channel=%s user_id=%s session_id=%s "
            "to_handle=%s",
            ch_name,
            (user_id or "")[:40],
            (session_id or "")[:40],
            (to_handle or "")[:60],
        )

        # Keep the same behavior as the agent pipeline:
        # if the channel has a fixed bot prefix, merge it into meta so
        # send_content_parts can use it.
        merged_meta = dict(meta or {})
        bot_prefix = getattr(ch, "bot_prefix", None) or getattr(
            ch,
            "_bot_prefix",
            None,
        )
        if bot_prefix and "bot_prefix" not in merged_meta:
            merged_meta["bot_prefix"] = bot_prefix
        merged_meta["session_id"] = session_id
        merged_meta["user_id"] = user_id

        # Send as content parts (single text part)
        await ch.send_content_parts(
            to_handle,
            [{"type": "text", "text": text}],
            merged_meta,
        )
