# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
from __future__ import annotations

import os
import logging
import asyncio
from typing import Optional

import aiohttp
from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

from ...config.config import DiscordConfig as DiscordChannelConfig

from .schema import Incoming, IncomingContentItem
from .base import BaseChannel, OnReplySent, ProcessHandler

logger = logging.getLogger(__name__)


class DiscordChannel(BaseChannel):
    channel = "discord"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        token: str,
        http_proxy: str,
        http_proxy_auth: str,
        bot_prefix: str,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
    ):
        super().__init__(
            process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
        )
        self.enabled = enabled
        self.token = token
        self.http_proxy = http_proxy
        self.http_proxy_auth = http_proxy_auth
        self.bot_prefix = bot_prefix
        self._task: Optional[asyncio.Task] = None
        self._client = None

        if self.enabled:
            import discord  # type: ignore

            intents = discord.Intents.default()
            intents.message_content = True
            intents.dm_messages = True
            intents.messages = True
            intents.guilds = True

            proxy_auth = None
            if self.http_proxy_auth:
                u, p = self.http_proxy_auth.split(":", 1)
                proxy_auth = aiohttp.BasicAuth(u, p)

            self._client = discord.Client(
                intents=intents,
                proxy=self.http_proxy,
                proxy_auth=proxy_auth,
            )

            @self._client.event
            async def on_message(message):
                if message.author.bot:
                    return
                text = (message.content or "").strip()
                attachments = message.attachments

                # Build content
                content = []
                if text:
                    content.append(IncomingContentItem(type="text", text=text))
                if attachments:
                    for att in attachments:
                        file_name = (att.filename or "").lower()
                        url = att.url
                        ctype = (att.content_type or "").lower()

                        is_image = ctype.startswith(
                            "image/",
                        ) or file_name.endswith(
                            (
                                ".png",
                                ".jpg",
                                ".jpeg",
                                ".gif",
                                ".webp",
                                ".bmp",
                                ".tiff",
                            ),
                        )
                        is_video = ctype.startswith(
                            "video/",
                        ) or file_name.endswith(
                            (".mp4", ".mov", ".mkv", ".webm", ".avi"),
                        )
                        is_audio = ctype.startswith(
                            "audio/",
                        ) or file_name.endswith(
                            (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"),
                        )

                        if is_image:
                            item_type = "image"
                        elif is_video:
                            item_type = "video"
                        elif is_audio:
                            item_type = "audio"
                        else:
                            item_type = "file"

                        content.append(
                            IncomingContentItem(
                                type=item_type,
                                url=url,
                            ),
                        )

                msg = Incoming(
                    channel="discord",
                    sender=str(message.author),
                    text=text,
                    content=content,
                    meta={
                        # "user_id": str(message.author.id),  # no need for id
                        "channel_id": str(message.channel.id),
                        "guild_id": str(message.guild.id)
                        if message.guild
                        else None,
                        "message_id": str(message.id),
                        "is_dm": message.guild is None,
                    },
                )

                try:
                    request = self.to_agent_request(msg)
                    last_response = None
                    send_meta = {
                        **(msg.meta or {}),
                        "bot_prefix": self.bot_prefix,
                    }
                    event_count = 0
                    async for event in self._process(request):
                        event_count += 1
                        obj = getattr(event, "object", None)
                        status = getattr(event, "status", None)
                        ev_type = getattr(event, "type", None)
                        logger.debug(
                            "discord event #%s: object=%s status=%s type=%s",
                            event_count,
                            obj,
                            status,
                            ev_type,
                        )
                        if obj == "message" and status == RunStatus.Completed:
                            logger.info(
                                "discord sending completed message: type=%s "
                                "to=%s",
                                ev_type,
                                msg.sender,
                            )
                            await self.send_message_content(
                                msg.sender,
                                event,
                                send_meta,
                            )
                        elif obj == "response":
                            last_response = event
                    logger.info(
                        "discord stream done: event_count=%s "
                        "has_response=%s has_error=%s",
                        event_count,
                        last_response is not None,
                        getattr(last_response, "error", None) is not None
                        if last_response
                        else False,
                    )
                    if last_response and getattr(last_response, "error", None):
                        err = getattr(
                            last_response.error,
                            "message",
                            str(last_response.error),
                        )
                        await message.channel.send(
                            self.bot_prefix + f"Error: {err}",
                        )
                    if self._on_reply_sent:
                        self._on_reply_sent(
                            self.channel,
                            request.user_id or msg.sender,
                            request.session_id
                            or f"{self.channel}:{msg.sender}",
                        )
                except Exception:
                    logger.exception("process/send failed")

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "DiscordChannel":
        return cls(
            process=process,
            enabled=os.getenv("DISCORD_CHANNEL_ENABLED", "1") == "1",
            token=os.getenv("DISCORD_BOT_TOKEN", ""),
            http_proxy=os.getenv(
                "DISCORD_HTTP_PROXY",
                "",
            ),
            http_proxy_auth=os.getenv("DISCORD_HTTP_PROXY_AUTH", ""),
            bot_prefix=os.getenv("DISCORD_BOT_PREFIX", "[BOT] "),
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: DiscordChannelConfig,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
    ) -> "DiscordChannel":
        return cls(
            process=process,
            enabled=config.enabled,
            token=config.bot_token or "",
            http_proxy=config.http_proxy,
            http_proxy_auth=config.http_proxy_auth or "",
            bot_prefix=config.bot_prefix or "[BOT] ",
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
        )

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[dict] = None,
    ) -> None:
        """
        Proactive send for Discord.

        Notes:
        - Discord cannot send to a "user handle" directly without resolving
            a User/Channel.
        - This implementation supports:
            1) meta["channel_id"]  -> send to that channel
            2) meta["user_id"]     -> DM that user (opens/uses DM channel)
        - If neither is provided, this raises ValueError.
        """
        if not self.enabled:
            return
        if not self._client:
            raise RuntimeError("Discord client is not initialized")
        if not self._client.is_ready():
            raise RuntimeError("Discord client is not ready yet")

        meta = meta or {}

        if not meta.get("channel_id") and not meta.get("user_id"):
            meta.update(self._route_from_handle(to_handle))

        channel_id = meta.get("channel_id")
        user_id = meta.get("user_id")

        if channel_id:
            ch = self._client.get_channel(int(channel_id))
            if ch is None:
                ch = await self._client.fetch_channel(
                    int(channel_id),
                )
            await ch.send(text)
            return

        if user_id:
            user = self._client.get_user(int(user_id))
            if user is None:
                user = await self._client.fetch_user(
                    int(user_id),
                )
            dm = user.dm_channel or await user.create_dm()
            await dm.send(text)
            return

        raise ValueError(
            "DiscordChannel.send requires meta['channel_id'] or meta["
            "'user_id']",
        )

    async def _run(self) -> None:
        if not self.enabled or not self.token or not self._client:
            return
        await self._client.start(self.token, reconnect=True)

    async def start(self) -> None:
        if not self.enabled:
            return
        self._task = asyncio.create_task(self._run(), name="discord_gateway")

    async def stop(self) -> None:
        if not self.enabled:
            return
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.CancelledError, Exception):
                pass
        if self._client:
            await self._client.close()

    def to_agent_request(self, incoming: Incoming):
        req = super().to_agent_request(incoming)

        meta = incoming.meta or {}
        is_dm = bool(meta.get("is_dm"))
        channel_id = meta.get("channel_id")
        discord_user_id = meta.get("user_id") or incoming.sender

        req.user_id = str(discord_user_id)

        if is_dm:
            req.session_id = f"discord:dm:{discord_user_id}"
        else:
            if channel_id:
                req.session_id = f"discord:ch:{channel_id}"
            else:
                req.session_id = f"discord:dm:{discord_user_id}"  # fallback

        return req

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        return session_id

    def _route_from_handle(self, to_handle: str) -> dict:
        # to_handle: discord:ch:<channel_id> 或 discord:dm:<user_id>
        parts = (to_handle or "").split(":")
        if len(parts) >= 3 and parts[0] == "discord":
            kind, ident = parts[1], parts[2]
            if kind == "ch":
                return {"channel_id": ident}
            if kind == "dm":
                return {"user_id": ident}
        return {}
