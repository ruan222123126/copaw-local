# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
"""Console Channel.

A lightweight channel that prints all agent responses to stdout.

Messages are sent to the agent via the standard AgentApp ``/agent/process``
endpoint.  This channel only handles the **output** side: whenever a
completed message event or a proactive send arrives, it is pretty-printed
to the terminal.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

from ...config.config import ConsoleConfig as ConsoleChannelConfig
from ..console_push_store import append as push_store_append
from .schema import Incoming
from .base import BaseChannel, OnReplySent, OutgoingContentPart, ProcessHandler


logger = logging.getLogger(__name__)

# ANSI colour helpers (degrade gracefully if not a tty)
_USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_GREEN = "\033[32m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_RESET = "\033[0m" if _USE_COLOR else ""


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ConsoleChannel(BaseChannel):
    """Console Channel: prints agent responses to stdout.

    Input is handled by AgentApp's ``/agent/process`` endpoint; this
    channel only takes care of output (printing to the terminal).
    """

    channel = "console"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        bot_prefix: str,
        on_reply_sent: OnReplySent = None,
    ):
        super().__init__(process, on_reply_sent=on_reply_sent)
        self.enabled = enabled
        self.bot_prefix = bot_prefix

        self._queue: Optional[asyncio.Queue[Incoming]] = None
        self._consumer_task: Optional[asyncio.Task[None]] = None

    # ── factory methods ─────────────────────────────────────────────

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "ConsoleChannel":
        return cls(
            process=process,
            enabled=os.getenv("CONSOLE_CHANNEL_ENABLED", "1") == "1",
            bot_prefix=os.getenv("CONSOLE_BOT_PREFIX", "[BOT] "),
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: ConsoleChannelConfig,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,  # TODO: fix me
    ) -> "ConsoleChannel":
        return cls(
            process=process,
            enabled=config.enabled,
            bot_prefix=config.bot_prefix or "[BOT] ",
            on_reply_sent=on_reply_sent,
        )

    # ── consume loop ────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        """Process messages from the queue."""
        assert self._queue is not None
        while True:
            msg = await self._queue.get()
            try:
                request = self.to_agent_request(msg)
                last_response = None
                event_count = 0
                _ = {
                    **(msg.meta or {}),
                    "bot_prefix": self.bot_prefix,
                }

                async for event in self._process(request):
                    event_count += 1
                    obj = getattr(event, "object", None)
                    status = getattr(event, "status", None)
                    ev_type = getattr(event, "type", None)

                    logger.debug(
                        "console event #%s: object=%s status=%s type=%s",
                        event_count,
                        obj,
                        status,
                        ev_type,
                    )

                    if obj == "message" and status == RunStatus.Completed:
                        parts = self._message_to_content_parts(event)
                        self._print_parts(parts, ev_type)

                    elif obj == "response":
                        last_response = event

                logger.info(
                    "console stream done: event_count=%s has_response=%s",
                    event_count,
                    last_response is not None,
                )

                if last_response and getattr(last_response, "error", None):
                    err = getattr(
                        last_response.error,
                        "message",
                        str(last_response.error),
                    )
                    self._print_error(err)

                if self._on_reply_sent:
                    self._on_reply_sent(
                        self.channel,
                        request.user_id or msg.sender,
                        request.session_id or f"{self.channel}:{msg.sender}",
                    )

            except Exception:
                logger.exception("console process/reply failed")
                self._print_error(
                    "An error occurred while processing your request.",
                )

    # ── pretty-print helpers ────────────────────────────────────────

    def _print_parts(
        self,
        parts: List[OutgoingContentPart],
        ev_type: Optional[str] = None,
    ) -> None:
        """Print outgoing content parts to stdout."""
        ts = _ts()
        label = f" ({ev_type})" if ev_type else ""
        print(
            f"\n{_GREEN}{_BOLD}🤖 [{ts}] Bot{label}{_RESET}",
        )
        for p in parts:
            t = p.get("type")
            if t == "text" and p.get("text"):
                print(f"{self.bot_prefix}{p['text']}")
            elif t == "refusal" and p.get("refusal"):
                print(f"{_RED}⚠ Refusal: {p['refusal']}{_RESET}")
            elif t == "image" and p.get("image_url"):
                print(f"{_YELLOW}🖼  [Image: {p['image_url']}]{_RESET}")
            elif t == "video" and p.get("video_url"):
                print(f"{_YELLOW}🎬 [Video: {p['video_url']}]{_RESET}")
            elif t == "audio" and p.get("data"):
                print(f"{_YELLOW}🔊 [Audio]{_RESET}")
            elif t == "file":
                url = p.get("file_url") or p.get("file_id") or ""
                print(f"{_YELLOW}📎 [File: {url}]{_RESET}")
            elif t == "data":
                print(f"{_YELLOW}📊 [Data]{_RESET}")
        print()

    def _print_error(self, err: str) -> None:
        ts = _ts()
        print(
            f"\n{_RED}{_BOLD}❌ [{ts}] Error{_RESET}\n"
            f"{_RED}{err}{_RESET}\n",
        )

    def _parts_to_text(
        self,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Merge parts to one body string (same logic as base send_content_parts).
        """
        text_parts: List[str] = []
        for p in parts:
            t = p.get("type")
            if t == "text" and p.get("text"):
                text_parts.append(p["text"])
            elif t == "refusal" and p.get("refusal"):
                text_parts.append(p["refusal"])
        body = "\n".join(text_parts) if text_parts else ""
        prefix = (meta or {}).get("bot_prefix", self.bot_prefix) or ""
        if prefix and body:
            body = prefix + body
        return body

    # ── send (for proactive sends / cron) ───────────────────────────

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a text message — prints to stdout and pushes to frontend."""
        if not self.enabled:
            return
        ts = _ts()
        prefix = (meta or {}).get("bot_prefix", self.bot_prefix) or ""
        print(
            f"\n{_GREEN}{_BOLD}🤖 [{ts}] Bot → {to_handle}{_RESET}\n"
            f"{prefix}{text}\n",
        )
        sid = (meta or {}).get("session_id")
        if sid and text.strip():
            await push_store_append(sid, text.strip())

    async def send_content_parts(
        self,
        to_handle: str,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send content parts — prints to stdout and pushes to frontend store.
        """
        self._print_parts(parts)
        sid = (meta or {}).get("session_id")
        if sid:
            body = self._parts_to_text(parts, meta)
            if body.strip():
                await push_store_append(sid, body.strip())

    # ── lifecycle ───────────────────────────────────────────────────

    async def start(self) -> None:
        if not self.enabled:
            logger.info("console channel disabled")
            return

        self._queue = asyncio.Queue(maxsize=1000)
        self._consumer_task = asyncio.create_task(
            self._consume_loop(),
            name="console_channel_consumer",
        )

        logger.info("console channel started")
        print(
            f"\n{_GREEN}{_BOLD}✅ Console channel started{_RESET}\n",
        )

    async def stop(self) -> None:
        if not self.enabled:
            return
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        logger.info("console channel stopped")
