# -*- coding: utf-8 -*-
import asyncio
import datetime
import logging
import os
from typing import Optional, Type, List, Sequence, Tuple, Any

from agentscope.agent import ReActAgent
from agentscope.agent._react_agent import _MemoryMark
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg, TextBlock
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit
from pydantic import BaseModel

from .prompt import (
    build_system_prompt_from_working_dir,
    build_bootstrap_guidance,
)
from .skills_manager import (
    ensure_skills_initialized,
    get_working_skills_dir,
    list_available_skills,
)
from .tools import (
    execute_shell_command,
    read_file,
    write_file,
    edit_file,
    send_file_to_user,
    desktop_screenshot,
    browser_use,
    create_memory_search_tool,
    get_current_time,
)
from .utils import (
    process_file_and_media_blocks_in_message,
    count_message_tokens,
    check_valid_messages,
    is_first_user_interaction,
    prepend_to_message_content,
)
from ..agents.memory import MemoryManager
from ..config import load_config
from ..constant import (
    MEMORY_COMPACT_THRESHOLD,
    MEMORY_COMPACT_KEEP_RECENT,
    WORKING_DIR,
)
from ..providers import get_active_llm_config

logger = logging.getLogger(__name__)


def create_file_block_support_formatter(base_formatter_class):
    """Factory function to add file block support to any Formatter class."""

    class FileBlockSupportFormatter(base_formatter_class):
        @staticmethod
        def convert_tool_result_to_string(
            output: str | List[dict],
        ) -> tuple[str, Sequence[Tuple[str, dict]]]:
            """Extend parent class to support file blocks.

            Uses try-first strategy for compatibility.
            """
            if isinstance(output, str):
                return output, []

            # Try parent class method first
            try:
                return base_formatter_class.convert_tool_result_to_string(
                    output,
                )
            except ValueError as e:
                if "Unsupported block type: file" not in str(e):
                    raise

                # Handle output containing file blocks
                textual_output = []
                multimodal_data = []

                for block in output:
                    if not isinstance(block, dict) or "type" not in block:
                        raise ValueError(
                            f"Invalid block: {block}, "
                            "expected a dict with 'type' key",
                        ) from e

                    if block["type"] == "file":
                        file_path = block.get("path", "") or block.get(
                            "url",
                            "",
                        )
                        file_name = block.get("name", file_path)

                        textual_output.append(
                            f"The returned file '{file_name}' "
                            f"can be found at: {file_path}",
                        )
                        multimodal_data.append((file_path, block))
                    else:
                        # Delegate other block types to parent class
                        (
                            text,
                            data,
                        ) = base_formatter_class.convert_tool_result_to_string(
                            [block],
                        )
                        textual_output.append(text)
                        multimodal_data.extend(data)

                if len(textual_output) == 0:
                    return "", multimodal_data
                elif len(textual_output) == 1:
                    return textual_output[0], multimodal_data
                else:
                    return (
                        "\n".join("- " + _ for _ in textual_output),
                        multimodal_data,
                    )

    FileBlockSupportFormatter.__name__ = (
        f"FileBlockSupport{base_formatter_class.__name__}"
    )
    return FileBlockSupportFormatter


# Create formatter with file block support
CoPawAgentFormatter = create_file_block_support_formatter(
    OpenAIChatFormatter,
)


class CoPawInMemoryMemory(InMemoryMemory):
    """bugfix"""

    async def get_memory(
        self,
        mark: str | None = None,
        exclude_mark: str | None = _MemoryMark.COMPRESSED,
        prepend_summary: bool = True,
        **kwargs: Any,
    ) -> list[Msg]:
        """Get the messages from the memory by mark (if provided)."""
        return await super().get_memory(
            mark=mark,
            exclude_mark=exclude_mark,
            prepend_summary=prepend_summary,
            **kwargs,
        )

    def get_compressed_summary(self) -> str:
        """Get the compressed summary of the memory."""
        return self._compressed_summary

    def state_dict(self) -> dict:
        """Get the state dictionary for serialization."""
        return {
            "content": [[msg.to_dict(), marks] for msg, marks in self.content],
            "_compressed_summary": self._compressed_summary,
        }

    def load_state_dict(self, state_dict: dict, strict: bool = True) -> None:
        """Load the state dictionary for deserialization."""
        if strict and "content" not in state_dict:
            raise KeyError(
                "The state_dict does not contain 'content' key required for "
                "InMemoryMemory.",
            )

        self.content = []
        for item in state_dict.get("content", []):
            if isinstance(item, (tuple, list)) and len(item) == 2:
                msg_dict, marks = item
                msg = Msg.from_dict(msg_dict)
                self.content.append((msg, marks))

            elif isinstance(item, dict):
                # For compatibility with older versions
                msg = Msg.from_dict(item)
                self.content.append((msg, []))

            else:
                raise ValueError(
                    "Invalid item format in state_dict for InMemoryMemory.",
                )

        self._compressed_summary = state_dict.get("_compressed_summary", "")


class CoPawAgent(ReActAgent):
    def __init__(
        self,
        env_context: Optional[str] = None,
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List[Any]] = None,
        memory_manager: MemoryManager | None = None,
    ):
        """Initialize CoPawAgent.

        Args:
            env_context: Optional environment context
            enable_memory_manager: Whether to enable memory manager
        """
        toolkit = Toolkit()
        self._mcp_clients = mcp_clients or []
        self._env_context = env_context
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(read_file)
        toolkit.register_tool_function(write_file)
        toolkit.register_tool_function(edit_file)
        toolkit.register_tool_function(browser_use)
        # toolkit.register_tool_function(append_file)
        toolkit.register_tool_function(desktop_screenshot)
        toolkit.register_tool_function(send_file_to_user)
        toolkit.register_tool_function(get_current_time)

        # Check skills initialization
        ensure_skills_initialized()

        working_skills_dir = get_working_skills_dir()
        available_skills = list_available_skills()

        for skill_name in available_skills:
            skill_dir = working_skills_dir / skill_name
            if skill_dir.exists():
                try:
                    toolkit.register_agent_skill(str(skill_dir))
                    logger.debug("Registered skill: %s", skill_name)
                except Exception as e:
                    logger.error(
                        "Failed to register skill '%s': %s",
                        skill_name,
                        e,
                    )

        sys_prompt = self._build_sys_prompt()

        # Resolve model / api_key / base_url from the active LLM slot
        llm_cfg = get_active_llm_config()
        if llm_cfg and llm_cfg.api_key:
            model_name = llm_cfg.model or "qwen3-max"
            api_key = llm_cfg.api_key
            base_url = llm_cfg.base_url
        else:
            logger.warning(
                "No active LLM configured — "
                "falling back to DASHSCOPE_API_KEY env var",
            )
            model_name = "qwen3-max"
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        super().__init__(
            name="Friday",
            model=OpenAIChatModel(
                model_name,
                api_key=api_key,
                stream=True,
                client_kwargs={"base_url": base_url},
            ),
            sys_prompt=sys_prompt,
            toolkit=toolkit,
            memory=CoPawInMemoryMemory(),
            formatter=CoPawAgentFormatter(),
        )
        self.memory_manager = memory_manager

        # Register memory_search tool if memory_manager is available
        if self.memory_manager is not None:
            memory_search_tool = create_memory_search_tool(self.memory_manager)
            self.toolkit.register_tool_function(memory_search_tool)
            logger.debug("Registered memory_search tool")

        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="bootstrap_hook",
            hook=CoPawAgent._pre_reasoning_bootstrap_hook,
        )
        logger.debug("Registered bootstrap hook")

        if enable_memory_manager and self.memory_manager is not None:
            self.register_instance_hook(
                hook_type="pre_reasoning",
                hook_name="memory_compact_hook",
                hook=CoPawAgent._pre_reasoning_compact_hook,
            )
            logger.debug("Registered memory compaction hook")

        self.summary_tasks: list[asyncio.Task] = []
        self._bootstrap_checked = False

    def _build_sys_prompt(self) -> str:
        """Build system prompt from working dir files and env context."""
        sys_prompt = build_system_prompt_from_working_dir()
        if self._env_context is not None:
            sys_prompt = self._env_context + "\n\n" + sys_prompt
        return sys_prompt

    def rebuild_sys_prompt(self) -> None:
        """Rebuild and replace the system prompt.

        Useful after load_session_state to ensure the prompt reflects
        the latest AGENTS.md / SOUL.md / PROFILE.md on disk.

        Updates both ``self._sys_prompt`` and the first system-role
        message stored in ``self.memory.content`` (if one exists).
        """
        self._sys_prompt = self._build_sys_prompt()

        # Also update the first system prompt message in memory
        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            # Stop after inspecting the first message regardless
            break

    async def register_mcp_clients(self) -> None:
        """Register MCP clients on this agent's toolkit after construction."""
        for client in self._mcp_clients:
            await self.toolkit.register_mcp_client(client)

    async def _pre_reasoning_bootstrap_hook(  # pylint: disable=unused-argument
        self,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check and load BOOTSTRAP.md on first user interaction."""
        if self._bootstrap_checked:
            return None

        self._bootstrap_checked = True

        try:
            bootstrap_path = WORKING_DIR / "BOOTSTRAP.md"
            if not bootstrap_path.exists():
                return None

            messages = await self.memory.get_memory()
            if not is_first_user_interaction(messages):
                return None

            config = load_config()
            language = config.agents.language
            bootstrap_content = bootstrap_path.read_text(encoding="utf-8")
            bootstrap_guidance = build_bootstrap_guidance(
                bootstrap_content,
                language,
            )

            logger.debug(
                "Found BOOTSTRAP.md [%s], prepending guidance",
                language,
            )

            system_prompt_count = sum(
                1 for msg in messages if msg.role == "system"
            )
            for msg in messages[system_prompt_count:]:
                if msg.role == "user":
                    prepend_to_message_content(msg, bootstrap_guidance)
                    break

            logger.debug("Bootstrap guidance prepended to first user message")

        except Exception as e:
            logger.error(
                "Failed to process bootstrap: %s",
                e,
                exc_info=True,
            )

        return None

    async def _pre_reasoning_compact_hook(  # pylint: disable=unused-argument
        self,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Pre-reasoning hook to check and compact memory if needed.

        This hook is called before each reasoning step. It extracts system
        prompt messages (consecutive system messages at the start) and recent
        messages, then counts tokens for the middle compactable messages only.
        If the token count exceeds the threshold, it triggers compaction.

        Memory structure:
            [System Prompt (preserved)] + [Compactable (counted)] +
            [Recent (preserved)]

        Args:
            kwargs: Input arguments to the _reasoning method (not modified)

        Returns:
            None
        """
        # Only compact if memory manager is enabled
        if self.memory_manager is None:
            return None

        try:
            messages = await self.memory.get_memory(
                exclude_mark=_MemoryMark.COMPRESSED,
                prepend_summary=False,
            )

            logger.debug(f"===last message===: {messages[-1]}")

            # Extract system prompt (consecutive system messages at start)
            system_prompt_messages = []
            for msg in messages:
                if msg.role == "system":
                    system_prompt_messages.append(msg)
                else:
                    break

            # Get remaining messages after system prompt
            remaining_messages = messages[len(system_prompt_messages) :]

            # Skip if not enough messages to compact
            if len(remaining_messages) <= MEMORY_COMPACT_KEEP_RECENT:
                return None

            # ensure the messages_to_keep is valid
            keep_length = MEMORY_COMPACT_KEEP_RECENT
            while keep_length > 0 and not check_valid_messages(
                remaining_messages[-keep_length:],
            ):
                keep_length -= 1

            # Split into compactable and recent messages
            if keep_length > 0:
                messages_to_compact = remaining_messages[:-keep_length]
                messages_to_keep = remaining_messages[-keep_length:]
            else:
                messages_to_compact = remaining_messages
                messages_to_keep = []

            # Count tokens for compactable messages only
            prompt = await self.formatter.format(msgs=messages_to_compact)
            try:
                estimated_tokens: int = await count_message_tokens(prompt)
            except Exception as e:
                estimated_tokens = len(str(prompt)) // 4
                logger.exception(
                    f"Failed to count tokens: {e}\n"
                    f"using estimated_tokens={estimated_tokens}",
                )

            # Check if the compactable part exceeds threshold
            if estimated_tokens > MEMORY_COMPACT_THRESHOLD:
                logger.info(
                    "Memory compaction triggered: estimated %d tokens "
                    "(threshold: %d), system_prompt_msgs: %d, "
                    "compactable_msgs: %d, keep_recent_msgs: %d",
                    estimated_tokens,
                    MEMORY_COMPACT_THRESHOLD,
                    len(system_prompt_messages),
                    len(messages_to_compact),
                    len(messages_to_keep),
                )

                self.summary_tasks.append(
                    asyncio.create_task(
                        self.memory_manager.summary_memory(
                            messages=messages_to_compact,
                            date=datetime.datetime.now().strftime("%Y-%m-%d"),
                        ),
                    ),
                )

                compact_content: str = (
                    await self.memory_manager.compact_memory(
                        messages_to_summarize=messages_to_compact,
                        previous_summary=self.memory.get_compressed_summary(),
                    )
                )

                await self.memory.update_compressed_summary(compact_content)
                updated_count = await self.memory.update_messages_mark(
                    new_mark=_MemoryMark.COMPRESSED,
                    msg_ids=[msg.id for msg in messages_to_compact],
                )
                logger.debug(
                    "Marked %d messages as compacted",
                    updated_count,
                )

        except Exception as e:
            # todo: handle the exception
            logger.error(
                "Failed to compact memory in pre_reasoning hook: %s",
                e,
                exc_info=True,
            )

        return None

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """Override reply to process file and media blocks."""
        if msg is not None:
            await process_file_and_media_blocks_in_message(msg)

        # Clean up completed summary tasks
        remaining_tasks = []
        for task in self.summary_tasks:
            if task.done():
                exc = task.exception()
                if exc is not None:
                    logger.error(f"Summary task failed: {exc}")
                else:
                    result = task.result()
                    logger.info(f"Summary task completed: {result}")
            else:
                remaining_tasks.append(task)
        self.summary_tasks = remaining_tasks

        if isinstance(msg, list):
            query = msg[-1].get_text_content()
        elif isinstance(msg, Msg):
            query = msg.get_text_content()
        else:
            query = None

        if isinstance(query, str) and query.strip() in [
            "/compact",
            "/new",
            "/clear",
            "/history",
        ]:
            return await self.system_process(query)

        return await super().reply(msg=msg, structured_model=structured_model)

    async def system_process(self, query: str):
        messages = await self.memory.get_memory(
            exclude_mark=_MemoryMark.COMPRESSED,
            prepend_summary=False,
        )

        async def get_msg(text: str):
            _msg = Msg(
                name=self.name,
                role="assistant",
                content=[TextBlock(type="text", text=text)],
            )
            logger.debug(f"return msg: {_msg}")
            await self.print(_msg)
            return _msg

        if not messages:
            return await get_msg(
                "**No messages to process.**\n\n"
                "- Current memory is empty\n"
                "- No action taken",
            )

        logger.debug(f"Enter received command: {query}")
        if query == "/compact":
            self.summary_tasks.append(
                asyncio.create_task(
                    self.memory_manager.summary_memory(
                        messages=messages,
                        date=datetime.datetime.now().strftime("%Y-%m-%d"),
                    ),
                ),
            )

            compact_content: str = await self.memory_manager.compact_memory(
                messages_to_summarize=messages,
                previous_summary=self.memory.get_compressed_summary(),
            )

            await self.memory.update_compressed_summary(compact_content)
            updated_count = await self.memory.update_messages_mark(
                new_mark=_MemoryMark.COMPRESSED,
                msg_ids=[msg.id for msg in messages],
            )
            logger.info(
                f"Marked %d messages as compacted with:\n{compact_content}",
                updated_count,
            )
            return await get_msg(
                f"**Compact Complete!**\n\n"
                f"- Messages compacted: {updated_count}\n"
                f"**Compressed Summary:**\n{compact_content}\n"
                f"- Summary task started in background\n",
            )

        elif query == "/new":
            self.summary_tasks.append(
                asyncio.create_task(
                    self.memory_manager.summary_memory(
                        messages=messages,
                        date=datetime.datetime.now().strftime("%Y-%m-%d"),
                    ),
                ),
            )
            await self.memory.update_compressed_summary("")
            updated_count = await self.memory.update_messages_mark(
                new_mark=_MemoryMark.COMPRESSED,
                msg_ids=[msg.id for msg in messages],
            )
            logger.debug(
                "Marked %d messages as compacted",
                updated_count,
            )
            return await get_msg(
                "**New Conversation Started!**\n\n"
                "- Summary task started in background\n"
                "- Ready for new conversation",
            )

        elif query == "/clear":
            self.memory.content.clear()
            await self.memory.update_compressed_summary("")
            return await get_msg(
                "**History Cleared!**\n\n"
                "- Compressed summary reset\n"
                "- Memory is now empty",
            )

        elif query.startswith("/history"):

            def format_msg(idx: int, msg: Msg) -> str:
                try:
                    text = msg.get_text_content() or ""
                    preview = text[:100] + "..." if len(text) > 100 else text
                    return f"[{idx}] **{msg.role}**: {preview}"
                except Exception as e:
                    return f"[{idx}] **{msg.role}**: <error: {e}>"

            return await get_msg(
                f"**Conversation History**\n\n"
                f"- Total messages: {len(messages)}\n\n"
                + "\n".join(
                    format_msg(i + 1, msg) for i, msg in enumerate(messages)
                ),
            )

        else:
            raise RuntimeError(f"Unknown command: {query}")
