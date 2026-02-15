# -*- coding: utf-8 -*-
# pylint: disable=too-many-statements,too-many-branches
# pylint: disable=too-many-return-statements
"""DingTalk Channel.

Why only one reply by default: DingTalk Stream callback is request-reply.
The handler process() is awaited until reply_future is set once,
then reply_text() is called once.
So we merge all streamed content into one reply. When sessionWebhook is
present we can send multiple messages via that webhook (one POST per
completed message), then set the future to a sentinel so process() skips the
single reply_text.
"""

from __future__ import annotations

import binascii
import base64
import json
import re
import asyncio
import logging
import os
import threading
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import urlparse


import aiohttp
import dingtalk_stream
from dingtalk_stream import CallbackMessage, ChatbotMessage
from agentscope_runtime.engine.schemas.agent_schemas import RunStatus

from ...config.config import DingTalkConfig as DingTalkChannelConfig
from ...config.utils import get_config_path

from .schema import Incoming, IncomingContentItem
from .base import BaseChannel, OnReplySent, OutgoingContentPart, ProcessHandler

if TYPE_CHECKING:
    from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

logger = logging.getLogger(__name__)

# When consumer sends all messages via sessionWebhook, it sets this so
# process() skips reply_text
SENT_VIA_WEBHOOK = "__SENT_VIA_WEBHOOK__"

# token cache TTL (1 hour)
DINGTALK_TOKEN_TTL_SECONDS = 3600

DINGTALK_DEBOUNCE_SECONDS = 0.3  # 300ms

# Short suffix length for session_id from conversation_id (for request and
# webhook_key so cron can use the same short session_id to look up webhook).
DINGTALK_SESSION_ID_SUFFIX_LEN = 8

_DINGTALK_TOKEN_LOCK = asyncio.Lock()
_DINGTALK_TOKEN_VALUE: Optional[str] = None
_DINGTALK_TOKEN_EXPIRES_AT: float = 0.0  # monotonic seconds

_DINGTALK_TYPE_MAPPING = {
    "picture": "image",
}

_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>[^;]+);base64,(?P<b64>.*)$",
    re.I | re.S,
)


def _parse_data_url(data_url: str) -> tuple[bytes, str | None]:
    """
    Return (bytes, mime or None)
    """
    m = _DATA_URL_RE.match(data_url.strip())
    if not m:
        # not a data url, treat as raw base64
        return base64.b64decode(data_url, validate=False), None

    mime = (m.group("mime") or "").strip().lower()
    b64 = m.group("b64").strip()
    try:
        data = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError):
        data = base64.b64decode(b64 + "==", validate=False)
    return data, mime or None


def ensure_list_spacing(text: str) -> str:
    """
    Ensure there is a blank line before numbered list items (e.g. "1. ..."),
    to avoid DingTalk merging the list item into the previous paragraph and
    breaking Markdown parsing.

    Example (before):
        Image: `xxx`
        3. **Make sure you are on the latest branch**

    Example (after):
        Image: `xxx`

        3. **Make sure you are on the latest branch**
    """
    lines = text.split("\n")
    out = []

    for i, line in enumerate(lines):
        is_numbered = re.match(r"^\d+\.\s", line.strip()) is not None
        if is_numbered and i > 0:
            prev = lines[i - 1]
            prev_is_empty = prev.strip() == ""
            prev_is_numbered = re.match(r"^\d+\.\s", prev.strip()) is not None
            if not prev_is_empty and not prev_is_numbered:
                out.append("")
        out.append(line)

    return "\n".join(out)


def dedent_code_blocks(text: str) -> str:
    """
    Remove unnecessary leading indentation before fenced code blocks.

    DingTalk may render code blocks incorrectly if the opening ``` fence
    is indented.

    This function detects an indented fenced block and removes the same
    indentation from all lines inside that block, while keeping relative
    indentation within the code.

    Note:
    - It only targets blocks that start at line-begin with optional spaces:
      <indent>```lang
      ...
      ```
    """
    pattern = r"^([ \t]*)(```[^\n]*\n.*?\n```)[ \t]*$"

    def _dedent(m: re.Match) -> str:
        indent = m.group(1)
        block = m.group(2)
        if not indent:
            return block

        n = len(indent)
        lines = block.split("\n")
        new_lines = []
        for ln in lines:
            if ln.startswith(indent):
                new_lines.append(ln[n:])
            else:
                new_lines.append(ln)
        return "\n".join(new_lines)

    return re.sub(pattern, _dedent, text, flags=re.MULTILINE | re.DOTALL)


def format_code_blocks(text: str, prefix: str = "·") -> str:
    """
    Prefix each non-empty line inside fenced code blocks with a marker.

    This is sometimes used as a workaround when DingTalk's Markdown parser
    behaves unexpectedly with certain code content.

    It preserves the fences (```lang ... ```).

    Example:
        ```json
        {"a": 1}
        ```

    Becomes:
        ```json
        ·{"a": 1}
        ```
    """
    pattern = r"```([^\n]*)\n(.*?)\n```"

    def _replace(m: re.Match) -> str:
        lang = m.group(1).strip()
        code = m.group(2)

        prefixed = []
        for ln in code.split("\n"):
            prefixed.append(f"{prefix}{ln}" if ln.strip() else ln)

        fence = f"```{lang}".rstrip()
        return fence + "\n" + "\n".join(prefixed) + "\n```"

    return re.sub(pattern, _replace, text, flags=re.DOTALL)


def _sender_from_chatbot_message(
    incoming_message: Any,
) -> tuple[str, bool]:
    """Build sender as nickname#last4(sender_id).
    Return (sender, should_skip).
    """
    nickname = (
        getattr(incoming_message, "sender_nick", None)
        or getattr(incoming_message, "senderNick", None)
        or ""
    )
    nickname = nickname.strip() if isinstance(nickname, str) else ""
    sender_id = (
        getattr(incoming_message, "sender_id", None)
        or getattr(incoming_message, "senderId", None)
        or ""
    )
    sender_id = str(sender_id).strip() if sender_id else ""
    suffix = sender_id[-4:] if len(sender_id) >= 4 else (sender_id or "????")
    sender = f"{(nickname or 'unknown')}#{suffix}"
    skip = not suffix and not nickname
    return sender, skip


def _conversation_id_from_chatbot_message(
    incoming_message: Any,
) -> str:
    """Extract conversation_id from DingTalk ChatbotMessage."""
    cid = getattr(incoming_message, "conversationId", None) or getattr(
        incoming_message,
        "conversation_id",
        None,
    )
    return str(cid).strip() if cid else ""


def _short_session_id_from_conversation_id(conversation_id: str) -> str:
    """Use last N chars of conversation_id as session_id (shorter for request
    and webhook_key; cron uses this same value to look up webhook).
    """
    n = DINGTALK_SESSION_ID_SUFFIX_LEN
    return (
        conversation_id[-n:] if len(conversation_id) >= n else conversation_id
    )


def normalize_dingtalk_markdown(
    text: str,
    code_prefix: str | None = None,
) -> str:
    """
    Apply a set of DingTalk Markdown normalization steps:
    1) Ensure blank lines before numbered list items
    2) Dedent fenced code blocks
    3) Optionally prefix code lines inside fenced blocks

    Args:
        text: Markdown text
        code_prefix: If provided, prefixes each code line with this string.
                     If None, code lines are not prefixed.

    Returns:
        Normalized Markdown text.
    """
    text = ensure_list_spacing(text)
    text = dedent_code_blocks(text)
    if code_prefix is not None:
        text = format_code_blocks(text, prefix=code_prefix)
    return text


class _DingTalkChannelHandler(dingtalk_stream.ChatbotHandler):
    """Internal handler: convert DingTalk message to Incoming, enqueue it,
    await reply_future, then reply."""

    def __init__(
        self,
        main_loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[Incoming],
        bot_prefix: str,
        download_url_fetcher,
    ):
        super().__init__()
        self._main_loop = main_loop
        self._queue = queue
        self._bot_prefix = bot_prefix
        self._download_url_fetcher = download_url_fetcher

    def _emit_incoming_threadsafe(self, msg: Incoming) -> None:
        self._main_loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    def _parse_rich_content(
        self,
        incoming_message: Any,
    ) -> List[IncomingContentItem]:
        """Parse richText from incoming_message into content items."""
        content: List[IncomingContentItem] = []
        try:
            robot_code = getattr(
                incoming_message,
                "robot_code",
                None,
            ) or getattr(incoming_message, "robotCode", None)
            msg_dict = incoming_message.to_dict()
            c = msg_dict.get("content") or {}
            raw = c.get("richText")
            raw = raw or c.get("rich_text")
            rich_list = raw if isinstance(raw, list) else []
            for item in rich_list:
                if not isinstance(item, dict):
                    continue
                if item.get("text") is not None:
                    content.append(
                        IncomingContentItem(
                            type="text",
                            text=item.get("text"),
                        ),
                    )
                dl_code = item.get("downloadCode")
                if not dl_code or not robot_code:
                    continue
                fut = asyncio.run_coroutine_threadsafe(
                    self._download_url_fetcher(
                        download_code=dl_code,
                        robot_code=robot_code,
                    ),
                    self._main_loop,
                )
                download_url = fut.result(timeout=15)
                content.append(
                    IncomingContentItem(
                        type=_DINGTALK_TYPE_MAPPING.get(
                            item.get("type", "file"),
                            item.get("type", "file"),
                        ),
                        url=download_url,
                    ),
                )

            # -------- 2) single downloadCode (pure picture/file) --------
            if not content:
                dl_code = c.get("downloadCode") or c.get("download_code")
                if dl_code and robot_code:
                    fut = asyncio.run_coroutine_threadsafe(
                        self._download_url_fetcher(
                            download_code=dl_code,
                            robot_code=robot_code,
                        ),
                        self._main_loop,
                    )
                    download_url = fut.result(timeout=15)

                    msgtype = (
                        (
                            msg_dict.get(
                                "msgtype",
                            )
                            or ""
                        )
                        .lower()
                        .strip()
                    )
                    mapped = _DINGTALK_TYPE_MAPPING.get(
                        msgtype,
                        msgtype or "file",
                    )
                    if mapped not in ("image", "file", "video", "audio"):
                        mapped = "file"

                    content.append(
                        IncomingContentItem(type=mapped, url=download_url),
                    )

        except Exception:
            logger.exception("failed to fetch richText download url(s)")
        return content

    async def process(self, callback: CallbackMessage) -> tuple[int, str]:
        try:
            incoming_message = ChatbotMessage.from_dict(callback.data)

            logger.debug(
                f"Dingtalk message received:" f" {incoming_message.to_dict()}",
            )
            content: List[IncomingContentItem] = []
            text = ""
            if incoming_message.text:
                text = (incoming_message.text.content or "").strip()
            if not text:
                content = self._parse_rich_content(incoming_message)

            sender, skip = _sender_from_chatbot_message(incoming_message)
            if skip:
                return dingtalk_stream.AckMessage.STATUS_OK, "ok"

            conversation_id = _conversation_id_from_chatbot_message(
                incoming_message,
            )
            loop = asyncio.get_running_loop()
            reply_future: asyncio.Future[str] = loop.create_future()
            meta: Dict[str, Any] = {
                "incoming_message": incoming_message,
                "reply_future": reply_future,
                "reply_loop": loop,
            }
            if conversation_id:
                meta["conversation_id"] = conversation_id

            msg = Incoming(
                channel="dingtalk",
                sender=sender,
                text=text,
                content=content,
                meta=meta,
            )
            logger.info(f"recv from={sender} text={text[:100]}")
            self._emit_incoming_threadsafe(msg)

            response_text = await reply_future
            if response_text == SENT_VIA_WEBHOOK:
                logger.info(
                    "sent to=%s via sessionWebhook (multi-message)",
                    sender,
                )
            else:
                out = self._bot_prefix + response_text
                self.reply_text(out, incoming_message)
                logger.info("sent to=%s text=%r", sender, out[:100])
            return dingtalk_stream.AckMessage.STATUS_OK, "ok"

        except Exception:
            logger.exception("process failed")
            return dingtalk_stream.AckMessage.STATUS_SYSTEM_EXCEPTION, "error"


class DingTalkChannel(BaseChannel):
    """DingTalk Channel: DingTalk Stream -> Incoming -> to_agent_request ->
    process -> send_response -> DingTalk reply.

    Proactive send (stored sessionWebhook):
    - We store sessionWebhook from incoming messages in memory; send() uses it.
    - Key uses short suffix of conversation_id so request and cron stay short.
    - to_handle "dingtalk:sw:<session_id>" (session_id = last N of conv id).
    - Note: sessionWebhook has an expiry (sessionWebhookExpiredTime);
      push only works for users who have chatted recently. For cron to
      users who may not
      have spoken, consider Open API (corp_id + batchSend) instead.
    """

    channel = "dingtalk"

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        client_id: str,
        client_secret: str,
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
        self.client_id = client_id
        self.client_secret = client_secret
        self.bot_prefix = bot_prefix

        self._client: Optional[dingtalk_stream.DingTalkStreamClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue[Incoming]] = None
        self._consumer_task: Optional[asyncio.Task[None]] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Store sessionWebhook for proactive send (in-memory).
        # Key is a handle string, e.g. "dingtalk:sw:<sender>"
        self._session_webhook_store: Dict[str, str] = {}
        self._session_webhook_lock = asyncio.Lock()

        self._debounced_queue: Optional[asyncio.Queue[Incoming]] = None
        self._debounce_task: Optional[asyncio.Task[None]] = None

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "DingTalkChannel":
        return cls(
            process=process,
            enabled=os.getenv("DINGTALK_CHANNEL_ENABLED", "1") == "1",
            client_id=os.getenv("DINGTALK_CLIENT_ID", ""),
            client_secret=os.getenv("DINGTALK_CLIENT_SECRET", ""),
            bot_prefix=os.getenv("DINGTALK_BOT_PREFIX", "[BOT] "),
            on_reply_sent=on_reply_sent,
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: DingTalkChannelConfig,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
    ) -> "DingTalkChannel":
        return cls(
            process=process,
            enabled=config.enabled,
            client_id=config.client_id or "",
            client_secret=config.client_secret or "",
            bot_prefix=config.bot_prefix or "[BOT] ",
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
        )

    # ---------------------------
    # Proactive send: webhook store
    # ---------------------------

    def to_agent_request(self, incoming: Incoming) -> "AgentRequest":
        """Override: set session_id to short suffix of conversation_id when
        present, so request and webhook_key stay short and cron can look up.
        """
        req = super().to_agent_request(incoming)
        meta = incoming.meta or {}
        cid = meta.get("conversation_id")
        if cid:
            req.session_id = _short_session_id_from_conversation_id(cid)
        return req

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        # Key by session_id (short suffix of conversation_id) so cron can
        # use the same session_id to look up stored sessionWebhook.
        return f"dingtalk:sw:{session_id}"

    def _route_from_handle(self, to_handle: str) -> dict:
        # to_handle:
        # - "dingtalk:sw:<sender>" -> use stored webhook by key
        # - "dingtalk:webhook:<url>" -> direct webhook URL
        # - "<url>" (starts with http/https) -> direct webhook URL
        s = (to_handle or "").strip()
        if s.startswith("http://") or s.startswith("https://"):
            return {"session_webhook": s}

        parts = s.split(":", 2)
        if len(parts) == 3 and parts[0] == "dingtalk":
            kind, ident = parts[1], parts[2]
            if kind == "sw":
                return {"webhook_key": f"dingtalk:sw:{ident}"}
            if kind == "webhook":
                return {"session_webhook": ident}
        return {"webhook_key": s} if s else {}

    def _session_webhook_store_path(self) -> Path:
        """Path to persist session webhook mapping (for cron after restart)."""
        return get_config_path().parent / "dingtalk_session_webhooks.json"

    def _load_session_webhook_store_from_disk(self) -> None:
        """Load session webhook mapping from disk into memory."""
        path = self._session_webhook_store_path()
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str) and v:
                        self._session_webhook_store[k] = v
        except Exception:
            logger.debug(
                "dingtalk load session_webhook store from %s failed",
                path,
                exc_info=True,
            )

    def _save_session_webhook_store_to_disk(self) -> None:
        """Persist in-memory session webhook store to disk."""
        path = self._session_webhook_store_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    self._session_webhook_store,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception:
            logger.debug(
                "dingtalk save session_webhook store to %s failed",
                path,
                exc_info=True,
            )

    async def _save_session_webhook(
        self,
        webhook_key: str,
        session_webhook: str,
    ) -> None:
        if not webhook_key or not session_webhook:
            return
        async with self._session_webhook_lock:
            self._session_webhook_store[webhook_key] = session_webhook
            self._save_session_webhook_store_to_disk()

    async def _load_session_webhook(self, webhook_key: str) -> Optional[str]:
        if not webhook_key:
            return None
        async with self._session_webhook_lock:
            out = self._session_webhook_store.get(webhook_key)
            if out is not None:
                return out
            self._load_session_webhook_store_from_disk()
            return self._session_webhook_store.get(webhook_key)

    # ---------------------------
    # Reply via stream thread
    # ---------------------------

    def _reply_sync(self, meta: Dict[str, Any], text: str) -> None:
        """Resolve reply_future on the stream thread's loop so process()
        can continue and reply.
        """
        reply_loop = meta.get("reply_loop")
        reply_future = meta.get("reply_future")
        if reply_loop is None or reply_future is None:
            return
        reply_loop.call_soon_threadsafe(reply_future.set_result, text)

    def _get_session_webhook(
        self,
        meta: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Get sessionWebhook from incoming_message in meta
        (for multi-message send).
        """
        if not meta:
            return None
        inc = meta.get("incoming_message")
        if inc is None:
            return None
        return getattr(inc, "sessionWebhook", None) or getattr(
            inc,
            "session_webhook",
            None,
        )

    def _parts_to_single_text(
        self,
        parts: List[OutgoingContentPart],
        bot_prefix: str = "",
    ) -> str:
        """Build one reply text from parts
        (same logic as send_content_parts body).
        """
        text_parts: List[str] = []
        for p in parts:
            t = p.get("type")
            if t == "text" and p.get("text"):
                text_parts.append(p["text"])
            elif t == "refusal" and p.get("refusal"):
                text_parts.append(p["refusal"])
            elif t == "image" and p.get("image_url"):
                text_parts.append(f"[Image: {p['image_url']}]")
            elif t == "video" and p.get("video_url"):
                text_parts.append(f"[Video: {p['video_url']}]")
            elif t == "file" and (p.get("file_url") or p.get("file_id")):
                text_parts.append(
                    f"[File: {p.get('file_url') or p.get('file_id')}]",
                )
            elif t == "audio" and p.get("data"):
                text_parts.append("[Audio]")
            elif t == "data":
                text_parts.append("[Data]")
        body = "\n".join(text_parts) if text_parts else ""
        if bot_prefix and body:
            body = bot_prefix + body
        return body

    async def _send_payload_via_session_webhook(
        self,
        session_webhook: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Send one message via DingTalk sessionWebhook with given JSON
        payload (e.g. msgtype text, markdown, image, file). Returns True
        on success.
        """
        msgtype = payload.get("msgtype", "?")
        wh = (
            session_webhook[:60] + "..."
            if len(session_webhook) > 60
            else session_webhook
        )
        logger.info(
            "dingtalk sessionWebhook send: msgtype=%s webhook_host=%s",
            msgtype,
            wh,
        )
        logger.info(f"dingtalk sessionWebhook send: payload={payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    session_webhook,
                    json=payload,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                    },
                ) as resp:
                    body_text = await resp.text()
                    if resp.status >= 400:
                        logger.warning(
                            "dingtalk sessionWebhook POST failed: msgtype=%s "
                            "status=%s body=%s",
                            msgtype,
                            resp.status,
                            body_text[:500],
                        )
                        return False
                    logger.info(
                        f"dingtalk sessionWebhook POST ok: msgtype={msgtype} "
                        f"status={resp.status}",
                    )
                    return True
        except Exception:
            logger.exception(
                f"dingtalk sessionWebhook POST failed: msgtype={msgtype}",
            )
            return False

    async def _send_via_session_webhook(
        self,
        session_webhook: str,
        body: str,
        bot_prefix: str = "",
    ) -> bool:
        """Send one text message via DingTalk sessionWebhook. Returns True
        on success."""
        text = (bot_prefix + body) if body else bot_prefix
        if len(text) > 3500:
            payload = {"msgtype": "text", "text": {"content": text}}
        else:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"💬{normalize_dingtalk_markdown(text)[:10]}...",
                    "text": normalize_dingtalk_markdown(text),
                },
            }
        return await self._send_payload_via_session_webhook(
            session_webhook,
            payload,
        )

    async def _upload_media(
        self,
        data: bytes,
        media_type: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """Upload media via DingTalk Open API and return media_id."""
        logger.info(
            "dingtalk upload_media: type=%s size=%s filename=%s",
            media_type,
            len(data),
            filename or "(none)",
        )
        token = await self._get_access_token()
        # Use oapi media upload (api.dingtalk.com upload returns 404).
        # Doc:
        # https://open.dingtalk.com/document/development/upload-media-files
        url = (
            "https://oapi.dingtalk.com/media/upload"
            f"?access_token={token}&type={media_type}"
        )
        ext = "jpg" if media_type == "image" else "bin"
        name = filename or f"upload.{ext}"
        logger.info(f"dingtalk upload_media: name={name}")
        form = aiohttp.FormData()
        form.add_field(
            "media",
            data,
            filename=name,
            content_type=content_type
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream",
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form) as resp:
                    result = await resp.json(content_type=None)
                    if resp.status >= 400:
                        logger.warning(
                            "dingtalk upload_media failed: type=%s status=%s "
                            "body=%s",
                            media_type,
                            resp.status,
                            result,
                        )
                        return None
                    # Old oapi returns errcode; 0 means success.
                    errcode = result.get("errcode", 0)
                    if errcode != 0:
                        logger.warning(
                            f"dingtalk upload_media oapi err: "
                            f"type={media_type} "
                            f"errcode={errcode} "
                            f"errmsg={result.get('errmsg', '')}",
                        )
                        return None
                    media_id = (
                        result.get("media_id")
                        or result.get("mediaId")
                        or (result.get("result") or {}).get("media_id")
                        or (result.get("result") or {}).get("mediaId")
                    )
                    if media_id:
                        mid_preview = (
                            media_id[:32] + "..."
                            if len(media_id) > 32
                            else media_id
                        )
                        logger.info(
                            "dingtalk upload_media ok: type=%s media_id=%s",
                            media_type,
                            mid_preview,
                        )
                    else:
                        logger.warning(
                            "dingtalk upload_media: no media_id in response "
                            "result=%s",
                            result,
                        )
                    return media_id
        except Exception:
            logger.exception(
                "dingtalk upload_media failed: type=%s filename=%s",
                media_type,
                filename,
            )
            return None

    async def _fetch_bytes_from_url(self, url: str) -> Optional[bytes]:
        """Download binary content from URL. Returns None on failure."""
        logger.info(
            "dingtalk fetch_bytes_from_url: url=%s",
            url[:80] + "..." if len(url) > 80 else url,
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            "dingtalk fetch_bytes_from_url failed: status=%s",
                            resp.status,
                        )
                        return None
                    data = await resp.read()
                    logger.info(
                        "dingtalk fetch_bytes_from_url ok: size=%s",
                        len(data),
                    )
                    return data
        except Exception:
            logger.exception(
                "dingtalk fetch_bytes_from_url failed: url=%s",
                url[:80],
            )
            return None

    async def _get_session_webhook_for_send(
        self,
        to_handle: str,
        meta: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Resolve session_webhook for sending (from meta or to_handle)."""
        m = meta or {}
        webhook = m.get("session_webhook") or m.get("sessionWebhook")
        if webhook:
            return webhook
        route = self._route_from_handle(to_handle)
        webhook = route.get("session_webhook")
        if webhook:
            return webhook
        key = route.get("webhook_key")
        if key:
            return await self._load_session_webhook(key)
        return None

    def _map_upload_type(self, part: OutgoingContentPart) -> Optional[str]:
        """
        Map OutgoingContentPart type to DingTalk media/upload type.
        DingTalk upload type must be one of: image | voice | video | file
        """
        ptype = (part.get("type") or "").strip().lower()

        if ptype in ("text", "refusal", "auto", ""):
            return None  # no upload

        if ptype == "image":
            return "image"
        if ptype == "audio":
            return "voice"
        if ptype == "video":
            return "video"
        if ptype == "file":
            return "file"

        # unknown -> treat as file
        return "file"

    async def _send_media_part_via_webhook(
        self,
        session_webhook: str,
        part: OutgoingContentPart,
    ) -> bool:
        """Upload and send one media part via session webhook."""
        ptype = (part.get("type") or "").strip().lower()
        upload_type = self._map_upload_type(part)

        logger.info(
            f"dingtalk _send_media_part_via_webhook: type={ptype} "
            f"upload_type={upload_type} "
            f"keys={list(part.keys())}",
        )

        # text/auto/refusal: no-op here (text is handled elsewhere)
        if upload_type is None:
            return True

        # ---------- image special-case: if public picURL, send directly ------
        if upload_type == "image":
            url = (part.get("image_url") or part.get("url") or "").strip()
            if self._is_public_http_url(url):
                payload = {"msgtype": "image", "image": {"picURL": url}}
                return await self._send_payload_via_session_webhook(
                    session_webhook,
                    payload,
                )
            # else: fallthrough to upload-by-bytes then send as file
            # (your existing fallback)

        # ---------- decide filename/ext ----------
        default_name = {
            "image": "image.png",
            "voice": "audio.amr",
            "video": "video.mp4",
            "file": "file.bin",
        }.get(upload_type, "file.bin")
        filename, ext = self._guess_filename_and_ext(
            part,
            default=default_name,
        )

        # ---------- if already has media id ----------
        # for file you used file_id;
        # keep compatibility but also accept media_id
        media_id = (
            part.get("media_id")
            or part.get("mediaId")
            or part.get(
                "file_id",
            )
        )
        if media_id:
            media_id = str(media_id).strip()
            if not media_id:
                return False

            if upload_type == "image":
                # sendBySession supports image by picURL;
                # but if we only have mediaId, send as file
                payload = {
                    "msgtype": "file",
                    "file": {
                        "mediaId": media_id,
                        "fileType": ext,
                        "fileName": filename,
                    },
                }
                return await self._send_payload_via_session_webhook(
                    session_webhook,
                    payload,
                )

            if upload_type == "voice":
                payload = {"msgtype": "voice", "voice": {"mediaId": media_id}}
                return await self._send_payload_via_session_webhook(
                    session_webhook,
                    payload,
                )

            if upload_type == "video":
                pic_media_id = (
                    part.get("pic_media_id") or part.get("picMediaId") or ""
                ).strip()
                if pic_media_id:
                    duration = part.get("duration")
                    if duration is None:
                        duration = 1
                    payload = {
                        "msgtype": "video",
                        "video": {
                            "videoMediaId": media_id,
                            "duration": str(int(duration)),
                            "picMediaId": pic_media_id,
                        },
                    }
                    return await self._send_payload_via_session_webhook(
                        session_webhook,
                        payload,
                    )
                # No picMediaId: send as file so user still gets the video
                payload = {
                    "msgtype": "file",
                    "file": {
                        "mediaId": media_id,
                        "fileType": ext,
                        "fileName": filename,
                    },
                }
                return await self._send_payload_via_session_webhook(
                    session_webhook,
                    payload,
                )

            # file
            payload = {
                "msgtype": "file",
                "file": {
                    "mediaId": media_id,
                    "fileType": ext,
                    "fileName": filename,
                },
            }
            return await self._send_payload_via_session_webhook(
                session_webhook,
                payload,
            )

        # ---------- load bytes from base64 or url ----------
        data: Optional[bytes] = None

        raw_b64 = part.get("base64")
        url = (
            part.get("file_url")
            or part.get("image_url")
            or part.get(
                "video_url",
            )
            or part.get("url")
            or ""
        ).strip()

        if raw_b64:
            if isinstance(raw_b64, str) and raw_b64.startswith("data:"):
                data, mime = _parse_data_url(raw_b64)
                if mime and not part.get("mime_type"):
                    part["mime_type"] = mime
                if mime and not part.get("filename"):
                    ext_guess = (mimetypes.guess_extension(mime) or "").lstrip(
                        ".",
                    ) or ""
                    if ext_guess:
                        filename = f"upload.{ext_guess}"
                        ext = ext_guess
            else:
                data = base64.b64decode(raw_b64, validate=False)
        elif url:
            data = await self._fetch_bytes_from_url(url)

        if not data:
            logger.warning(
                "dingtalk media part: no data to upload, type=%s",
                ptype,
            )
            return False

        # ---------- upload ----------
        media_id = await self._upload_media(
            data,
            upload_type,  # image | voice | video | file
            filename=filename,
            content_type=part.get("mime_type"),
        )
        if not media_id:
            return False

        # ---------- send ----------
        if upload_type == "image":
            # no public url -> safest is send as file (your current behavior)
            payload = {
                "msgtype": "file",
                "file": {
                    "mediaId": media_id,
                    "fileType": ext,
                    "fileName": filename,
                },
            }
            return await self._send_payload_via_session_webhook(
                session_webhook,
                payload,
            )

        if upload_type == "voice":
            payload = {"msgtype": "voice", "voice": {"mediaId": media_id}}
            return await self._send_payload_via_session_webhook(
                session_webhook,
                payload,
            )

        if upload_type == "video":
            pic_media_id = (
                part.get("pic_media_id") or part.get("picMediaId") or ""
            ).strip()
            if pic_media_id:
                duration = part.get("duration")
                if duration is None:
                    duration = 1
                payload = {
                    "msgtype": "video",
                    "video": {
                        "videoMediaId": media_id,
                        "duration": str(int(duration)),
                        "picMediaId": pic_media_id,
                    },
                }
                return await self._send_payload_via_session_webhook(
                    session_webhook,
                    payload,
                )
            # No picMediaId: send as file so user still gets the video
            payload = {
                "msgtype": "file",
                "file": {
                    "mediaId": media_id,
                    "fileType": ext,
                    "fileName": filename,
                },
            }
            return await self._send_payload_via_session_webhook(
                session_webhook,
                payload,
            )

        payload = {
            "msgtype": "file",
            "file": {
                "mediaId": media_id,
                "fileType": ext,
                "fileName": filename,
            },
        }
        return await self._send_payload_via_session_webhook(
            session_webhook,
            payload,
        )

    async def send_content_parts(
        self,
        to_handle: str,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Build one body from parts. If meta has reply_future (reply path),
        deliver via _reply_sync; otherwise proactive send via send().
        When session_webhook is available, sends text then image/file
        messages (upload media first for image/file).
        """
        text_parts = []
        media_parts: List[OutgoingContentPart] = []
        for p in parts:
            t = p.get("type")
            if t == "text" and p.get("text"):
                text_parts.append(p["text"])
            elif t == "refusal" and p.get("refusal"):
                text_parts.append(p["refusal"])
            elif t == "image":
                media_parts.append(p)
            elif t == "file":
                media_parts.append(p)
            elif t == "video":
                media_parts.append(p)
            elif t == "audio":
                media_parts.append(p)
            elif t == "data":
                text_parts.append("[Data]")
        body = "\n".join(text_parts) if text_parts else ""
        prefix = (meta or {}).get("bot_prefix", "") or ""
        if prefix and body:
            body = prefix + body
        elif prefix and not body and not media_parts:
            body = prefix
        m = meta or {}
        session_webhook = await self._get_session_webhook_for_send(
            to_handle,
            meta,
        )
        logger.info(
            "dingtalk send_content_parts: to_handle=%s has_webhook=%s "
            "text_parts=%s media_parts=%s",
            to_handle[:40] if to_handle else "",
            bool(session_webhook),
            len(text_parts),
            len(media_parts),
        )
        if session_webhook and (body.strip() or media_parts):
            if body.strip():
                logger.info("dingtalk send_content_parts: sending text body")
                await self._send_via_session_webhook(
                    session_webhook,
                    body.strip(),
                    bot_prefix="",
                )
            for i, part in enumerate(media_parts):
                logger.info(
                    "dingtalk send_content_parts: "
                    "sending media part %s/%s type=%s",
                    i + 1,
                    len(media_parts),
                    part.get("type"),
                )
                ok = await self._send_media_part_via_webhook(
                    session_webhook,
                    part,
                )
                logger.info(
                    "dingtalk send_content_parts: media part %s result=%s",
                    i + 1,
                    ok,
                )
            if m.get("reply_loop") is not None and m.get("reply_future"):
                self._reply_sync(m, SENT_VIA_WEBHOOK)
            return
        if not body and media_parts:
            for p in media_parts:
                if p.get("type") == "image" and p.get("image_url"):
                    text_parts.append(f"[Image: {p['image_url']}]")
                elif p.get("type") == "file" and (
                    p.get("file_url") or p.get("file_id")
                ):
                    text_parts.append(
                        f"[File: {p.get('file_url') or p.get('file_id')}]",
                    )
            body = "\n".join(text_parts) if text_parts else ""
            if prefix and body:
                body = prefix + body
        if (
            m.get("reply_loop") is not None
            and m.get("reply_future") is not None
        ):
            self._reply_sync(m, body)
        else:
            await self.send(to_handle, body.strip() or prefix, meta)

    async def _consume_loop(self) -> None:
        assert self._debounced_queue is not None
        while True:
            msg = await self._debounced_queue.get()
            await self._consume_one(msg)

    async def _consume_one(
        self,
        msg: Incoming,
    ) -> None:  # pylint: disable=too-many-branches
        request = self.to_agent_request(msg)
        last_response = None
        accumulated_parts: list = []
        event_count = 0
        send_meta = {**(msg.meta or {}), "bot_prefix": self.bot_prefix}

        session_webhook = self._get_session_webhook(msg.meta)
        use_multi = bool(session_webhook)

        # Store sessionWebhook (keyed by conversation).
        if session_webhook:
            fallback_sid = f"{self.channel}:{msg.sender}"
            webhook_key = self.to_handle_from_target(
                user_id=request.user_id or msg.sender,
                session_id=request.session_id or fallback_sid,
            )
            await self._save_session_webhook(
                webhook_key,
                session_webhook,
            )

        async for event in self._process(request):
            event_count += 1
            obj = getattr(event, "object", None)
            status = getattr(event, "status", None)
            ev_type = getattr(event, "type", None)
            logger.debug(
                "dingtalk event #%s: object=%s status=%s type=%s",
                event_count,
                obj,
                status,
                ev_type,
            )
            if obj == "message" and status == RunStatus.Completed:
                parts = self._message_to_content_parts(event)
                logger.info(
                    f"dingtalk completed message: type={ev_type} "
                    f"parts_count={len(parts)}",
                )
                if use_multi and parts and session_webhook:
                    body = self._parts_to_single_text(
                        parts,
                        bot_prefix="",
                    )
                    if body.strip():
                        await self._send_via_session_webhook(
                            session_webhook,
                            body.strip(),
                            bot_prefix="",
                        )
                    _media_types = ("image", "file", "video", "audio")
                    media_count = sum(
                        1 for p in parts if p.get("type") in _media_types
                    )
                    if media_count:
                        logger.info(
                            "dingtalk consume_loop: "
                            "sending %s media "
                            "parts via webhook",
                            media_count,
                        )
                    for part in parts:
                        if part.get("type") in _media_types:
                            ok = await self._send_media_part_via_webhook(
                                session_webhook,
                                part,
                            )
                            logger.info(
                                "dingtalk consume_loop: media part "
                                "type=%s result=%s",
                                part.get("type"),
                                ok,
                            )
                else:
                    accumulated_parts.extend(parts)
            elif obj == "response":
                last_response = event

        logger.info(
            "dingtalk stream done: event_count=%s parts=%s webhook=%s",
            event_count,
            len(accumulated_parts),
            use_multi,
        )

        if last_response and getattr(last_response, "error", None):
            err = getattr(
                last_response.error,
                "message",
                str(last_response.error),
            )
            err_text = self.bot_prefix + f"Error: {err}"
            if use_multi and session_webhook:
                await self._send_via_session_webhook(
                    session_webhook,
                    err_text,
                    bot_prefix="",
                )
            self._reply_sync(
                send_meta,
                SENT_VIA_WEBHOOK if use_multi else err_text,
            )
        elif use_multi:
            self._reply_sync(send_meta, SENT_VIA_WEBHOOK)
        elif accumulated_parts:
            await self.send_content_parts(
                msg.sender,
                accumulated_parts,
                send_meta,
            )
        elif last_response is None:
            self._reply_sync(
                send_meta,
                self.bot_prefix
                + "An error occurred while processing your request.",
            )

        if self._on_reply_sent:
            self._on_reply_sent(
                self.channel,
                request.user_id or msg.sender,
                request.session_id or f"{self.channel}:{msg.sender}",
            )

    def _debounce_key(self, msg: Incoming) -> str:
        meta = msg.meta or {}
        cid = meta.get("conversation_id") or ""
        if cid:
            return _short_session_id_from_conversation_id(str(cid))
        # fallback: at least avoid mixing different senders
        return f"{self.channel}:{msg.sender}"

    def _merge_incoming(self, items: list[Incoming]) -> Incoming:
        """Merge multiple Incoming messages into one."""
        first = items[0]
        merged_texts: list[str] = []
        merged_content: list[IncomingContentItem] = []

        for it in items:
            t = (it.text or "").strip()
            if t:
                merged_texts.append(t)
            if it.content:
                merged_content.extend(it.content)

        merged = Incoming(
            channel=first.channel,
            sender=first.sender,
            text="\n".join(merged_texts).strip(),
            content=merged_content,
            meta=dict(first.meta or {}),
        )

        # Keep last item's reply_future/reply_loop/incoming_message to avoid
        # hanging.
        last_meta = items[-1].meta or {}
        for k in (
            "reply_future",
            "reply_loop",
            "incoming_message",
            "conversation_id",
        ):
            if k in last_meta:
                merged.meta[k] = last_meta[k]

        # (Optional) Store batched count for debugging/tracing.
        merged.meta["batched_count"] = len(items)
        return merged

    async def _debounce_loop(self) -> None:
        assert self._queue is not None
        assert self._debounced_queue is not None

        pending: dict[str, list[Incoming]] = {}
        timers: dict[str, asyncio.Task[None]] = {}

        async def flush(key: str) -> None:
            try:
                await asyncio.sleep(DINGTALK_DEBOUNCE_SECONDS)
                items = pending.pop(key, [])
                timers.pop(key, None)
                if not items:
                    return
                merged = self._merge_incoming(items)
                await self._debounced_queue.put(merged)
            except asyncio.CancelledError as e:
                raise e
            except Exception:
                logger.exception("dingtalk debounce flush failed")

        while True:
            msg = await self._queue.get()
            key = self._debounce_key(msg)

            # If this key already has pending, the previous msg will be merged
            # and won't get a real reply. Set reply_future first so stream
            # callback doesn't wait until timeout.
            if pending.get(key):
                prev = pending[key][-1]  # previous message
                pm = prev.meta or {}
                if (
                    pm.get("reply_loop") is not None
                    and pm.get(
                        "reply_future",
                    )
                    is not None
                ):
                    self._reply_sync(pm, SENT_VIA_WEBHOOK)

            pending.setdefault(key, []).append(msg)

            # Reset timer: 300ms window starts from when the last msg arrives.
            old = timers.get(key)
            if old and not old.done():
                old.cancel()
            timers[key] = asyncio.create_task(flush(key))

    def _run_stream_forever(self) -> None:
        logger.info(
            "dingtalk stream thread started (client_id=%s)",
            self.client_id,
        )
        try:
            if self._client:
                self._client.start_forever()
        except Exception:
            logger.exception("dingtalk stream thread failed")
        finally:
            self._stop_event.set()
            logger.info("dingtalk stream thread stopped")

    async def start(self) -> None:
        if not self.enabled:
            logger.info("disabled by env DINGTALK_CHANNEL_ENABLED=0")
            return
        self._load_session_webhook_store_from_disk()
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET are required "
                "when channel is enabled.",
            )

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=1000)  # raw input
        self._debounced_queue = asyncio.Queue(maxsize=1000)  # after merge

        self._debounce_task = asyncio.create_task(
            self._debounce_loop(),
            name="dingtalk_channel_debounce",
        )

        self._consumer_task = asyncio.create_task(
            self._consume_loop(),  # consume_loop reads from debounced_queue
            name="dingtalk_channel_consumer",
        )

        credential = dingtalk_stream.Credential(
            self.client_id,
            self.client_secret,
        )
        self._client = dingtalk_stream.DingTalkStreamClient(credential)
        internal_handler = _DingTalkChannelHandler(
            main_loop=self._loop,
            queue=self._queue,
            bot_prefix=self.bot_prefix,
            download_url_fetcher=self._get_message_file_download_url,
        )
        self._client.register_callback_handler(
            ChatbotMessage.TOPIC,
            internal_handler,
        )

        self._stop_event.clear()
        self._stream_thread = threading.Thread(
            target=self._run_stream_forever,
            daemon=True,
        )
        self._stream_thread.start()

    async def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._stream_thread:
            self._stream_thread.join(timeout=5)
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._client = None
        if self._debounce_task:
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Proactive send for DingTalk via stored sessionWebhook.

        Supports:
        1) meta["session_webhook"] or meta["sessionWebhook"]: direct url
        2) to_handle: dingtalk:sw:<sender> (stored) or http(s) url
        If no webhook is found, logs warning and returns (no 500).
        """
        if not self.enabled:
            return

        meta = meta or {}

        # direct webhook provided in meta
        session_webhook = meta.get("session_webhook") or meta.get(
            "sessionWebhook",
        )

        if not session_webhook:
            route = self._route_from_handle(to_handle)
            session_webhook = route.get("session_webhook")
            if not session_webhook:
                webhook_key = route.get("webhook_key")
                if webhook_key:
                    session_webhook = await self._load_session_webhook(
                        webhook_key,
                    )

        if not session_webhook:
            logger.warning(
                "DingTalkChannel.send: no sessionWebhook for to_handle=%s. "
                "User must have chatted with the bot first, or pass "
                "meta['session_webhook']. Skip sending.",
                to_handle,
            )
            return

        logger.info(
            "DingTalkChannel.send to_handle=%s len=%s",
            to_handle,
            len(text),
        )

        # Caller (send_content_parts) already prepends bot_prefix to text.
        await self._send_via_session_webhook(
            session_webhook,
            text,
            bot_prefix="",
        )

    async def _get_access_token(self) -> str:
        """Get and cache DingTalk accessToken for 1 hour."""
        global _DINGTALK_TOKEN_VALUE, _DINGTALK_TOKEN_EXPIRES_AT

        if not self.client_id or not self.client_secret:
            raise RuntimeError("DingTalk client_id/client_secret missing")

        now = asyncio.get_running_loop().time()
        if _DINGTALK_TOKEN_VALUE and now < _DINGTALK_TOKEN_EXPIRES_AT:
            return _DINGTALK_TOKEN_VALUE

        async with _DINGTALK_TOKEN_LOCK:
            now = asyncio.get_running_loop().time()
            if _DINGTALK_TOKEN_VALUE and now < _DINGTALK_TOKEN_EXPIRES_AT:
                return _DINGTALK_TOKEN_VALUE

            url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
            payload = {
                "appKey": self.client_id,
                "appSecret": self.client_secret,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status >= 400:
                        raise RuntimeError(
                            f"get accessToken failed status={resp.status} "
                            f"body={data}",
                        )

            token = data.get("accessToken") or data.get("access_token")
            if not token:
                raise RuntimeError(
                    f"accessToken not found in response: {data}",
                )

            # cache: 1 hour fixed as requested
            _DINGTALK_TOKEN_VALUE = token
            _DINGTALK_TOKEN_EXPIRES_AT = (
                asyncio.get_running_loop().time() + DINGTALK_TOKEN_TTL_SECONDS
            )
            return token

    async def _get_message_file_download_url(
        self,
        *,
        download_code: str,
        robot_code: str,
    ) -> Optional[str]:
        """Call DingTalk messageFiles/download to get a downloadable URL."""
        if not download_code or not robot_code:
            return None

        token = await self._get_access_token()
        url = "https://api.dingtalk.com/v1.0/robot/messageFiles/download"
        payload = {"downloadCode": download_code, "robotCode": robot_code}
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": token,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    logger.warning(
                        "messageFiles/download failed status=%s body=%s",
                        resp.status,
                        data,
                    )
                    return None

        logger.debug("messageFiles/download response=%s", data)
        return (
            data.get("downloadUrl")
            or data.get("url")
            or (data.get("result") or {}).get("downloadUrl")
            or (data.get("result") or {}).get("url")
        )

    def _guess_filename_and_ext(
        self,
        part: OutgoingContentPart,
        default: str,
    ) -> tuple[str, str]:
        """
        Return (filename, ext) where ext has no dot.
        Tries: part['filename'] -> url path basename -> default
        """
        filename = (part.get("filename") or "").strip()

        if not filename:
            url = (
                part.get("file_url")
                or part.get("image_url")
                or part.get(
                    "url",
                )
                or ""
            ).strip()
            if url:
                try:
                    path = urlparse(url).path
                    base = os.path.basename(path)
                    if base:
                        filename = base
                except Exception:
                    pass

        if not filename:
            filename = default

        ext = ""
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower().strip()

        if not ext:
            # try from mime_type if provided
            mime = (
                part.get("mime_type")
                or part.get(
                    "content_type",
                )
                or ""
            ).strip()
            if mime:
                guess = mimetypes.guess_extension(mime)  # like ".png"
                if guess:
                    ext = guess.lstrip(".").lower()

        if not ext:
            ext = (
                default.rsplit(".", 1)[-1].lower() if "." in default else "bin"
            )

        # normalize common cases
        if ext == "jpeg":
            ext = "jpg"

        return filename, ext

    def _is_public_http_url(self, s: Optional[str]) -> bool:
        if not s or not isinstance(s, str):
            return False
        s = s.strip()
        return s.startswith("http://") or s.startswith("https://")
