# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements,unused-argument
"""
Base Channel: bound to AgentRequest/AgentResponse, unified by process.
"""
from __future__ import annotations

import json
import logging
from abc import ABC
from typing import (
    Optional,
    Dict,
    Any,
    List,
    AsyncIterator,
    Callable,
    TYPE_CHECKING,
)

from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

from .schema import Incoming, ChannelType

# Called when a user-originated reply was sent (channel, user_id, session_id)
OnReplySent = Optional[Callable[[str, str, str], None]]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agentscope_runtime.engine.schemas.agent_schemas import (
        AgentRequest,
        AgentResponse,
        Event,
    )

# process: accepts AgentRequest, streams Event
# (including message events with status completed)
ProcessHandler = Callable[[Any], AsyncIterator["Event"]]

# One content part to send
# (aligned with agent_schemas ContentType and content classes)
OutgoingContentPart = Dict[str, Any]


class BaseChannel(ABC):
    channel: ChannelType

    def __init__(
        self,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
    ):
        self._process = process
        self._on_reply_sent = on_reply_sent
        self._show_tool_details = show_tool_details

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "BaseChannel":
        raise NotImplementedError

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Any,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
    ) -> "BaseChannel":
        raise NotImplementedError

    def to_agent_request(self, incoming: Incoming) -> "AgentRequest":
        """
        Convert this channel's Incoming to AgentRequest.
        Subclasses may override to support image, video, etc.
        (from get_content_list() or meta).
        """
        from agentscope_runtime.engine.schemas.agent_schemas import (
            AgentRequest,
            Message,
            TextContent,
            ContentType,
            MessageType,
            Role,
            ImageContent,
            VideoContent,
            AudioContent,
            FileContent,
        )

        content_list = incoming.get_content_list()
        contents = []
        for item in content_list:
            if item.type == "text" and item.text:
                contents.append(
                    TextContent(type=ContentType.TEXT, text=item.text),
                )
            elif item.type == "image" and item.url:
                contents.append(
                    ImageContent(
                        type=ContentType.IMAGE,
                        image_url=item.url,
                    ),
                )
            elif item.type == "video" and item.url:
                contents.append(
                    VideoContent(
                        type=ContentType.VIDEO,
                        video_url=item.url,
                    ),
                )
            elif item.type == "audio" and item.url:
                contents.append(
                    AudioContent(
                        type=ContentType.AUDIO,
                        data=item.url,
                    ),
                )
            elif item.type == "file" and item.url:
                contents.append(
                    FileContent(
                        type=ContentType.FILE,
                        file_url=item.url,
                    ),
                )
        if not contents:
            contents = [
                TextContent(type=ContentType.TEXT, text=incoming.text or ""),
            ]

        session_id = f"{incoming.channel}:{incoming.sender}"
        user_id = incoming.sender
        msg = Message(
            type=MessageType.MESSAGE,
            role=Role.USER,
            content=contents,
        )
        return AgentRequest(
            session_id=session_id,
            user_id=user_id,
            input=[msg],
            channel=incoming.channel,
        )

    async def send_response(
        self,
        to_handle: str,
        response: "AgentResponse",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Convert AgentResponse to this channel's reply and send.
        Default: take last message text from output and call
        send(to_handle, text, meta).
        Subclasses may override to support image, video attachments.
        """
        text = self._response_to_text(response)
        await self.send(to_handle, text or "", meta)

    def _message_to_content_parts(
        self,
        message: Any,
    ) -> List[OutgoingContentPart]:
        """
        Convert a Message (object=='message') into a list of sendable
        content parts.
        Supports: MESSAGE (text, image, video, audio, file, refusal, data),
        FUNCTION_CALL / PLUGIN_CALL (show tool name + arguments),
        FUNCTION_CALL_OUTPUT / PLUGIN_CALL_OUTPUT (show result).
        """
        from agentscope_runtime.engine.schemas.agent_schemas import (
            MessageType,
            ContentType,
        )

        msg_type = getattr(message, "type", None)
        content = getattr(message, "content", None) or []
        logger.debug(
            "channel _message_to_content_parts: msg_type=%s content_len=%s",
            msg_type,
            len(content),
        )

        def _parts_for_tool_call(
            content_list: list,
        ) -> List[OutgoingContentPart]:
            parts: List[OutgoingContentPart] = []
            show_detail = getattr(self, "_show_tool_details", True)
            for c in content_list:
                if getattr(c, "type", None) != ContentType.DATA:
                    continue
                data = getattr(c, "data", None) or {}
                name = data.get("name") or "tool"
                if show_detail:
                    args = data.get("arguments") or "{}"
                    args_preview = (
                        args[:200] + "..." if len(args) > 200 else args
                    )
                else:
                    args_preview = "..."
                parts.append(
                    {
                        "type": "text",
                        "text": f"🔧 **{name}**\n```\n{args_preview}\n```",
                    },
                )
            return parts

        def _parts_for_tool_output(
            content_list: list,
        ) -> List[OutgoingContentPart]:
            parts: List[OutgoingContentPart] = []
            show_detail = getattr(self, "_show_tool_details", True)

            def _blocks_to_parts(blocks: list) -> List[OutgoingContentPart]:
                out: List[OutgoingContentPart] = []
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    btype = b.get("type")

                    # text block
                    if btype == "text" and b.get("text"):
                        out.append({"type": "text", "text": b["text"]})
                        continue

                    # media blocks: image/audio/video/file
                    if btype in ("image", "audio", "video", "file"):
                        src = b.get("source") or {}
                        stype = src.get("type")
                        if stype == "url" and src.get("url"):
                            out.append(
                                {
                                    "type": btype,
                                    "url": src["url"],
                                    "filename": b.get("filename"),
                                    "media_type": src.get("media_type"),
                                },
                            )
                        elif stype == "base64" and src.get("data"):
                            out.append(
                                {
                                    "type": btype,
                                    "base64": src["data"],
                                    # base64字符串（可能含data:前缀）
                                    "filename": b.get("filename"),
                                    "media_type": src.get("media_type"),
                                },
                            )
                        continue

                    # 其它 block（thinking/tool_use等）可选择忽略或转文本
                    if btype == "thinking" and b.get("thinking"):
                        out.append({"type": "text", "text": b["thinking"]})
                        continue

                return out

            for c in content_list:
                if getattr(c, "type", None) != ContentType.DATA:
                    continue
                data = getattr(c, "data", None) or {}
                name = data.get("name") or "tool"
                output = data.get("output", "")

                # Convert json str to list
                try:
                    output = json.loads(output)
                except json.decoder.JSONDecodeError:
                    pass

                # 1) output is blocks list: parse and optionally hide text
                if isinstance(output, list):
                    block_parts = _blocks_to_parts(output)
                    if show_detail:
                        parts.append(
                            {"type": "text", "text": f"✅ **{name}**:"},
                        )
                        parts.extend(block_parts)
                    else:
                        # Only send media parts; hide text/thinking
                        media_types = ("image", "audio", "video", "file")
                        media_parts = [
                            p
                            for p in block_parts
                            if p.get("type") in media_types
                        ]
                        parts.extend(media_parts)
                        if not media_parts:
                            parts.append(
                                {
                                    "type": "text",
                                    "text": f"✅ **{name}**:\n```\n...\n```",
                                },
                            )
                    continue

                # 2) output is string: preview or hide
                if isinstance(output, str):
                    if show_detail:
                        output_preview = (
                            output[:500] + "..."
                            if len(output) > 500
                            else output
                        )
                        parts.append(
                            {
                                "type": "text",
                                "text": f"✅ **{name}**:\n```"
                                f"\n{output_preview}\n```",
                            },
                        )
                    else:
                        parts.append(
                            {
                                "type": "text",
                                "text": f"✅ **{name}**:\n```\n...\n```",
                            },
                        )
                    continue

                # 3) fallback: convert to string
                if output is not None:
                    s = str(output)
                    if show_detail:
                        preview = s[:500] + "..." if len(s) > 500 else s
                        parts.append(
                            {
                                "type": "text",
                                "text": f"✅ **{name}**:\n```\n{preview}\n```",
                            },
                        )
                    else:
                        parts.append(
                            {
                                "type": "text",
                                "text": f"✅ **{name}**:\n```\n...\n```",
                            },
                        )

            return parts

        if msg_type in (
            MessageType.FUNCTION_CALL,
            MessageType.PLUGIN_CALL,
            MessageType.MCP_TOOL_CALL,
        ):
            parts = _parts_for_tool_call(content)
            if not parts:
                parts = [{"type": "text", "text": f"[{msg_type}]"}]
            logger.info(
                f"channel {msg_type} -> {len(parts)} part(s)",
            )
            return parts

        if msg_type in (
            MessageType.FUNCTION_CALL_OUTPUT,
            MessageType.PLUGIN_CALL_OUTPUT,
            MessageType.MCP_TOOL_CALL_OUTPUT,
        ):
            parts = _parts_for_tool_output(content)
            if not parts:
                parts = [{"type": "text", "text": f"[{msg_type}]"}]
            logger.info(
                f"channel {msg_type} -> {len(parts)} part(s)",
            )
            return parts

        # All other message types
        # (MESSAGE, component_call, mcp_call, reasoning, etc.):
        # render from content so every object=message gets sent
        parts = []
        for c in content:
            ctype = getattr(c, "type", None)
            if ctype == ContentType.TEXT and getattr(c, "text", None):
                parts.append({"type": "text", "text": c.text})
            # NOTE: In most case, below conditions will not happen
            elif ctype == ContentType.REFUSAL and getattr(c, "refusal", None):
                parts.append({"type": "refusal", "refusal": c.refusal})
            elif ctype == ContentType.IMAGE and getattr(c, "image_url", None):
                parts.append({"type": "image", "image_url": c.image_url})
            elif ctype == ContentType.VIDEO and getattr(c, "video_url", None):
                parts.append({"type": "video", "video_url": c.video_url})
            elif ctype == ContentType.AUDIO:
                data = getattr(c, "data", None)
                fmt = getattr(c, "format", None)
                if data:
                    parts.append(
                        {"type": "audio", "data": data, "format": fmt},
                    )
            elif ctype == ContentType.FILE:
                parts.append(
                    {
                        "type": "file",
                        "file_url": getattr(c, "file_url", None),
                        "file_id": getattr(c, "file_id", None),
                        "filename": getattr(c, "filename", None),
                        "file_data": getattr(c, "file_data", None),
                    },
                )
            elif ctype == ContentType.DATA and getattr(c, "data", None):
                data = c.data
                if isinstance(data, dict):
                    name = data.get("name")
                    output = data.get("output")
                    args = data.get("arguments")
                    show_detail = getattr(self, "_show_tool_details", True)
                    if name is not None and (
                        output is not None or args is not None
                    ):
                        if not show_detail:
                            preview = "..."
                        elif output is not None:
                            preview = str(output)[:500] + (
                                "..." if len(str(output)) > 500 else ""
                            )
                        else:
                            preview = str(args)[:200] + (
                                "..." if len(str(args)) > 200 else ""
                            )
                        parts.append(
                            {
                                "type": "text",
                                "text": f"**{name}**:\n```\n{preview}\n```",
                            },
                        )
                    else:
                        parts.append({"type": "data", "data": data})
                else:
                    parts.append({"type": "data", "data": data})
        if not parts and msg_type:
            parts = [{"type": "text", "text": f"[Message type: {msg_type}]"}]
        return parts

    async def send_message_content(
        self,
        to_handle: str,
        message: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send all content of a Message
        (text, image, video, audio, file, refusal).
        Subclasses may override send_content_parts for channel-specific
        multi-part sending.
        """
        parts = self._message_to_content_parts(message)
        if not parts:
            logger.debug(
                f"channel send_message_content: no parts for to_handle="
                f"{to_handle}, skip send",
            )
            return
        logger.debug(
            f"channel send_message_content: to_handle={to_handle} "
            f"parts_count={len(parts)} "
            f"part_types={[p.get('type') for p in parts]}",
        )
        await self.send_content_parts(to_handle, parts, meta)

    async def send_content_parts(
        self,
        to_handle: str,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a list of content parts.
        Default: merge text/refusal into one text, append media URLs as
        fallback, send one message; optionally call send_media for each
        media part if overridden.
        """
        text_parts: List[str] = []
        media_parts: List[OutgoingContentPart] = []
        for p in parts:
            t = p.get("type")
            if t == "text" and p.get("text"):
                text_parts.append(p["text"])
            elif t == "refusal" and p.get("refusal"):
                text_parts.append(p["refusal"])
            elif t in ("image", "video", "audio", "file", "data"):
                media_parts.append(p)
        body = "\n".join(text_parts) if text_parts else ""
        prefix = (meta or {}).get("bot_prefix", "") or ""
        if prefix and body:
            body = prefix + body
        for m in media_parts:
            t = m.get("type")
            if t == "image" and m.get("image_url"):
                body += f"\n[Image: {m['image_url']}]"
            elif t == "video" and m.get("video_url"):
                body += f"\n[Video: {m['video_url']}]"
            elif t == "file" and (m.get("file_url") or m.get("file_id")):
                body += f"\n[File: {m.get('file_url') or m.get('file_id')}]"
            elif t == "audio" and m.get("data"):
                body += "\n[Audio]"
            elif t == "data":
                body += "\n[Data]"
        if body.strip():
            logger.debug(
                f"channel send_content_parts: to_handle={to_handle} "
                f"body_len={len(body)} preview="
                f"{body[:120] + '...' if len(body) > 120 else body}",
            )
            await self.send(to_handle, body.strip(), meta)
        for m in media_parts:
            await self.send_media(to_handle, m, meta)

    async def send_media(
        self,
        to_handle: str,
        part: OutgoingContentPart,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a single media part (image, video, audio, file).
        Default: no-op (already appended to text in send_content_parts).
        Subclasses override to send real attachments.
        """

    def _response_to_text(self, response: "AgentResponse") -> str:
        """Extract reply text from AgentResponse (last message in output)."""
        from agentscope_runtime.engine.schemas.agent_schemas import (
            MessageType,
            ContentType,
        )

        if not response.output:
            return ""
        last_msg = response.output[-1]
        if last_msg.type != MessageType.MESSAGE or not last_msg.content:
            return ""
        parts = []
        for c in last_msg.content:
            if getattr(c, "type", None) == ContentType.TEXT and getattr(
                c,
                "text",
                None,
            ):
                parts.append(c.text)
            elif getattr(c, "type", None) == ContentType.REFUSAL and getattr(
                c,
                "refusal",
                None,
            ):
                parts.append(c.refusal)
        return "".join(parts)

    def clone(self, config) -> "BaseChannel":
        """Clone a new channel instance with updated config, cloning
        process and on_reply_sent from self.

        Subclasses must implement from_config(process, config, on_reply_sent).
        """
        return self.__class__.from_config(
            process=self._process,
            config=config,
            on_reply_sent=self._on_reply_sent,
            show_tool_details=getattr(self, "_show_tool_details", True),
        )

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Subclass implements: send one text
        (and optional attachments) to to_handle.
        """
        raise NotImplementedError

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        """Map cron dispatch target to channel-specific to_handle.

        Default: use user_id. For many channels, this is enough.
        Discord proactive send relies on meta['channel_id'] or
         meta['user_id'] anyway.
        """
        return user_id

    async def send_event(
        self,
        *,
        user_id: str,
        session_id: str,
        event: "Event",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a runner Event to this channel (non-stream).

        We only send when event is a completed message, then reuse
        send_message_content().
        """
        # Delay import to avoid hard dependency at module import time

        obj = getattr(event, "object", None)
        status = getattr(event, "status", None)

        if obj != "message" or status != RunStatus.Completed:
            return

        to_handle = self.to_handle_from_target(
            user_id=user_id,
            session_id=session_id,
        )
        await self.send_message_content(to_handle, event, meta)
