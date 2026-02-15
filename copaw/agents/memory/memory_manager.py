# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
"""Memory Manager for CoPaw agents.

Inherits from ReMeFs to provide memory management capabilities including:
- Message compaction and summarization
- Semantic memory search
- Memory file retrieval
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from agentscope.formatter import DashScopeChatFormatter
from agentscope.formatter._dashscope_formatter import (
    _format_dashscope_media_block,
    _reformat_messages,
)
from agentscope.message import (
    ImageBlock,
    AudioBlock,
    VideoBlock,
    TextBlock,
    URLSource,
)
from agentscope.message import Msg
from agentscope.tool import ToolResponse

from ...config.utils import load_config
from ...providers import get_active_llm_config

logger = logging.getLogger(__name__)


class TimestampedDashScopeChatFormatter(DashScopeChatFormatter):
    """DashScope formatter that includes timestamp in formatted messages.

    Extends DashScopeChatFormatter to add the timestamp to each formatted
    message as a 'time_created' field.
    """

    async def _format(
        self,
        msgs: list[Msg],
    ) -> list[dict[str, Any]]:
        """Format message objects into DashScope API format with timestamps.

        Args:
            msgs (`list[Msg]`):
                The list of message objects to format.

        Returns:
            `list[dict[str, Any]]`:
                The formatted messages with  time_created fields.
        """
        # Import required modules from parent implementation

        self.assert_list_of_msgs(msgs)

        formatted_msgs: list[dict] = []

        i = 0
        while i < len(msgs):
            msg = msgs[i]
            content_blocks: list[dict[str, Any]] = []
            tool_calls = []

            for block in msg.get_content_blocks():
                typ = block.get("type")

                if typ == "text":
                    content_blocks.append(
                        {
                            "text": block.get("text"),
                        },
                    )

                elif typ in ["image", "audio", "video"]:
                    content_blocks.append(
                        _format_dashscope_media_block(
                            block,  # type: ignore[arg-type]
                        ),
                    )

                elif typ == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(
                                    block.get("input", {}),
                                    ensure_ascii=False,
                                ),
                            },
                        },
                    )

                elif typ == "tool_result":
                    (
                        textual_output,
                        multimodal_data,
                    ) = self.convert_tool_result_to_string(block["output"])

                    # First add the tool result message in DashScope API format
                    formatted_msgs.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.get("id"),
                            "content": textual_output,
                            "name": block.get("name"),
                        },
                    )

                    # Then, handle the multimodal data if any
                    promoted_blocks: list = []
                    for url, multimodal_block in multimodal_data:
                        if (
                            multimodal_block["type"] == "image"
                            and self.promote_tool_result_images
                        ):
                            promoted_blocks.extend(
                                [
                                    TextBlock(
                                        type="text",
                                        text=f"\n- The image from '{url}': ",
                                    ),
                                    ImageBlock(
                                        type="image",
                                        source=URLSource(
                                            type="url",
                                            url=url,
                                        ),
                                    ),
                                ],
                            )
                        elif (
                            multimodal_block["type"] == "audio"
                            and self.promote_tool_result_audios
                        ):
                            promoted_blocks.extend(
                                [
                                    TextBlock(
                                        type="text",
                                        text=f"\n- The audio from '{url}': ",
                                    ),
                                    AudioBlock(
                                        type="audio",
                                        source=URLSource(
                                            type="url",
                                            url=url,
                                        ),
                                    ),
                                ],
                            )
                        elif (
                            multimodal_block["type"] == "video"
                            and self.promote_tool_result_videos
                        ):
                            promoted_blocks.extend(
                                [
                                    TextBlock(
                                        type="text",
                                        text=f"\n- The video from '{url}': ",
                                    ),
                                    VideoBlock(
                                        type="video",
                                        source=URLSource(
                                            type="url",
                                            url=url,
                                        ),
                                    ),
                                ],
                            )

                    if promoted_blocks:
                        # Insert promoted blocks as new user message(s)
                        promoted_blocks = [
                            TextBlock(
                                type="text",
                                text="<system-info>The following are "
                                f"the media contents from the tool "
                                f"result of '{block['name']}':",
                            ),
                            *promoted_blocks,
                            TextBlock(
                                type="text",
                                text="</system-info>",
                            ),
                        ]

                        msgs.insert(
                            i + 1,
                            Msg(
                                name="user",
                                content=promoted_blocks,
                                role="user",
                            ),
                        )

                else:
                    logger.warning(
                        "Unsupported block type %s in the message, skipped.",
                        typ,
                    )

            msg_dashscope = {
                "role": msg.role,
                "content": content_blocks,
                "time_created": msg.timestamp,  # Add timestamp here
            }

            if tool_calls:
                msg_dashscope["tool_calls"] = tool_calls

            if msg_dashscope["content"] or msg_dashscope.get("tool_calls"):
                formatted_msgs.append(msg_dashscope)

            # Move to next message
            i += 1

        return _reformat_messages(formatted_msgs)


# Try to import reme, log warning if it fails
try:
    from reme import ReMeFs

    _REME_AVAILABLE = True
except ImportError:
    logger.warning("reme not found. Install with: pip install reme-ai")
    _REME_AVAILABLE = False

    class ReMeFs:  # type: ignore
        """Placeholder when reme is not available."""


class MemoryManager(ReMeFs):
    """Memory manager that extends ReMeFs functionality for CoPaw agents.

    Provides methods for managing conversation history, searching memories,
    and retrieving specific memory content.
    """

    def __init__(self, *args, working_dir: str, **kwargs):
        """Initialize MemoryManager with ReMeFs configuration."""
        if not _REME_AVAILABLE:
            raise RuntimeError("reme package not installed.")

        llm_cfg = get_active_llm_config()
        if llm_cfg and llm_cfg.api_key:
            model_name = llm_cfg.model or "qwen3-max"
            api_key = llm_cfg.api_key
            base_url = (
                llm_cfg.base_url
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        else:
            logger.warning(
                "No active LLM configured — "
                "falling back to DASHSCOPE_API_KEY env var",
            )
            model_name = "qwen3-max"
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        embedding_api_key = os.environ.get("EMBEDDING_API_KEY", "")
        vector_enabled = bool(embedding_api_key)
        if vector_enabled:
            logger.info("Vector search enabled.")
        else:
            logger.warning(
                "Vector search disabled. "
                "Memory search functionality will be restricted. "
                "To enable, configure: EMBEDDING_API_KEY, EMBEDDING_BASE_URL, "
                "EMBEDDING_MODEL_NAME, and EMBEDDING_DIMENSIONS.",
            )
        fts_enabled = os.environ.get("FTS_ENABLED", "true").lower() == "true"

        embedding_base_url = os.environ.get(
            "EMBEDDING_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        embedding_model_name = os.environ.get(
            "EMBEDDING_MODEL_NAME",
            "text-embedding-v4",
        )

        embedding_dimensions = int(
            os.environ.get("EMBEDDING_DIMENSIONS", "1024"),
        )
        working_path: Path = Path(working_dir)
        super().__init__(
            *args,
            working_dir=working_dir,
            config_path="fs",
            enable_logo=False,
            log_to_console=False,
            llm_api_key=api_key,
            llm_base_url=base_url,
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
            default_llm_config={"model_name": model_name},
            default_embedding_model_config={
                "model_name": embedding_model_name,
                "dimensions": embedding_dimensions,
            },
            default_memory_store_config={
                "backend": "chroma",
                "db_name": "copaw.db",
                "store_name": "copaw",
                "vector_enabled": vector_enabled,
                "fts_enabled": fts_enabled,
            },
            default_file_watcher_config={
                "watch_paths": [
                    str(working_path / "MEMORY.md"),
                    str(working_path / "memory.md"),
                    str(working_path / "memory"),
                ],
            },
            **kwargs,
        )

        global_config = load_config()
        language = global_config.agents.language

        if language == "zh":
            self.language = "zh"
        else:
            self.language = ""

    def update_llm_emb_api_envs(self):
        llm_cfg = get_active_llm_config()
        if llm_cfg and llm_cfg.api_key:
            api_key = llm_cfg.api_key
            base_url = (
                llm_cfg.base_url
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        else:
            logger.warning(
                "No active LLM configured — "
                "falling back to DASHSCOPE_API_KEY env var",
            )
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        embedding_api_key = os.environ.get("EMBEDDING_API_KEY", "")
        embedding_base_url = os.environ.get(
            "EMBEDDING_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        super().update_api_envs(
            llm_api_key=api_key,
            llm_base_url=base_url,
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
        )

    async def start(self):
        """Start the memory manager and initialize services."""
        return await super().start()

    async def close(self):
        """Close the memory manager and cleanup resources."""
        return await super().close()

    async def compact_memory(
        self,
        messages_to_summarize: list[Msg] | None = None,
        turn_prefix_messages: list[Msg] | None = None,
        previous_summary: str = "",
    ) -> str:
        """Compact messages into a summary.

        Args:
            messages_to_summarize: Messages to summarize
            turn_prefix_messages: Messages to prepend to each turn
            previous_summary: Previous summary to build upon

        Returns:
            Compaction result from FsCompactor
        """
        self.update_llm_emb_api_envs()

        formatter = TimestampedDashScopeChatFormatter()
        if not messages_to_summarize and not turn_prefix_messages:
            return ""

        if messages_to_summarize:
            messages_to_summarize = await formatter.format(
                messages_to_summarize,
            )
        else:
            messages_to_summarize = []

        if turn_prefix_messages:
            turn_prefix_messages = await formatter.format(turn_prefix_messages)
        else:
            turn_prefix_messages = []

        previous_summary = await super().compact(
            messages_to_summarize=messages_to_summarize,
            turn_prefix_messages=turn_prefix_messages,
            previous_summary=previous_summary,
            language=self.language,
        )

        previous_summary = f"""
<previous-summary>
{previous_summary}
</previous-summary>
The above is a summary of our previous conversation.
Use it as context to maintain continuity.
        """.strip()

        return previous_summary

    async def summary_memory(
        self,
        messages: list[Msg],
        date: str,
        version: str = "default",
    ) -> str:
        """Generate a summary of the given messages."""
        self.update_llm_emb_api_envs()

        formatter = TimestampedDashScopeChatFormatter()
        messages = await formatter.format(messages)
        result = await super().summary(
            messages=messages,
            date=date,
            version=version,
            language=self.language,
        )
        return result

    async def memory_search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> ToolResponse:
        """
        Mandatory recall: semantically search MEMORY.md + memory/*.md
        (and optional session transcripts) before answering questions about
        prior work, decisions, dates, people, preferences, or todos;
        returns top snippets with path + lines.

        Args:
            query: The semantic search query to find relevant memory snippets
            max_results: Max search results to return (optional), default 5
            min_score: Min similarity score for results (optional), default 0.1

        Returns:
            Search results as formatted string
        """
        search_result: str = await super().memory_search(
            query=query,
            max_results=max_results,
            min_score=min_score,
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=search_result,
                ),
            ],
        )

    async def memory_get(
        self,
        path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> ToolResponse:
        """
        Safe snippet read from MEMORY.md, memory/*.md with optional
        offset/limit; use after memory_search to pull needed lines and
        keep context small.

        Args:
            path: Path to the memory file to read (relative or absolute)
            offset: Starting line number (1-indexed, optional)
            limit: Number of lines to read from the starting line (optional)

        Returns:
            Memory file content as string
        """
        get_result = await super().memory_get(
            path=path,
            offset=offset,
            limit=limit,
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=get_result,
                ),
            ],
        )
