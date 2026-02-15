# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import json
import logging
import os
import asyncio
from pathlib import Path
from copy import deepcopy

from agentscope.mcp import StdIOStatefulClient
from agentscope.pipeline import stream_printing_messages
from agentscope.session import JSONSession
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.memory import MemoryManager
from ...agents.react_agent import CoPawAgent
from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._tavily_search_client = None
        self._pending_messages: dict[
            tuple[str, str],
            dict[str, object],
        ] = {}
        self._pending_lock = asyncio.Lock()

        self.memory_manager: MemoryManager | None = None

    async def add_pending_messages(
        self,
        session_id: str,
        user_id: str,
        msgs,
    ) -> list[str]:
        """Save current user messages for UI history fallback."""
        pending_ids: list[str] = []
        if not msgs:
            return pending_ids
        if not isinstance(msgs, (list, tuple)):
            msgs = [msgs]

        key = (session_id, user_id)
        async with self._pending_lock:
            slot = self._pending_messages.setdefault(key, {})
            for msg in msgs:
                msg_id = getattr(msg, "id", None)
                if not msg_id:
                    continue
                slot[msg_id] = deepcopy(msg)
                pending_ids.append(msg_id)
        return pending_ids

    async def remove_pending_messages(
        self,
        session_id: str,
        user_id: str,
        msg_ids: list[str],
    ) -> None:
        """Remove messages from pending store after session is persisted."""
        if not msg_ids:
            return
        key = (session_id, user_id)
        async with self._pending_lock:
            slot = self._pending_messages.get(key)
            if not slot:
                return
            for msg_id in msg_ids:
                slot.pop(msg_id, None)
            if not slot:
                self._pending_messages.pop(key, None)

    async def get_pending_messages(
        self,
        session_id: str,
        user_id: str,
    ) -> list:
        """Get current pending messages for the given session/user."""
        key = (session_id, user_id)
        async with self._pending_lock:
            slot = self._pending_messages.get(key, {})
            return [deepcopy(msg) for msg in slot.values()]

    def set_chat_manager(self, chat_manager):
        """Set chat manager for auto-registration.

        Args:
            chat_manager: ChatManager instance
        """
        self._chat_manager = chat_manager

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle agent query.
        """
        session_id = request.session_id
        user_id = request.user_id
        channel = getattr(request, "channel", DEFAULT_CHANNEL)
        pending_id_set = set(
            await self.add_pending_messages(
                session_id=session_id,
                user_id=user_id,
                msgs=msgs,
            ),
        )
        pending_ids = list(pending_id_set)

        logger.info(
            "Handle agent query:\n%s",
            json.dumps(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "channel": channel,
                    "msgs_len": len(msgs) if msgs else 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        env_context = build_env_context(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            working_dir=str(WORKING_DIR),
        )
        mcp_clients = []
        if self._tavily_search_client is not None:
            mcp_clients.append(self._tavily_search_client)

        agent = CoPawAgent(
            env_context=env_context,
            mcp_clients=mcp_clients,
            memory_manager=self.memory_manager,
        )
        await agent.register_mcp_clients()
        agent.set_console_output_enabled(enabled=False)

        try:
            logger.debug(
                f"Agent Query msgs {msgs}",
            )

            name = "New Chat"
            if len(msgs) > 0:
                content = msgs[0].get_text_content()
                if content:
                    name = msgs[0].get_text_content()[:10]
                else:
                    name = "多媒体消息"

            if self._chat_manager is not None:
                chat = await self._chat_manager.get_or_create_chat(
                    session_id,
                    user_id,
                    channel,
                    name=name,
                )

            await self.session.load_session_state(
                session_id=session_id,
                user_id=user_id,
                agent=agent,
            )

            # Rebuild system prompt so it always reflects the latest
            # AGENTS.md / SOUL.md / PROFILE.md, not the stale one saved
            # in the session state.
            agent.rebuild_sys_prompt()

            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(msgs),
            ):
                new_pending_ids = await self.add_pending_messages(
                    session_id=session_id,
                    user_id=user_id,
                    msgs=msg,
                )
                if new_pending_ids:
                    pending_id_set.update(new_pending_ids)
                    pending_ids = list(pending_id_set)
                yield msg, last

            await self.session.save_session_state(
                session_id=session_id,
                user_id=user_id,
                agent=agent,
            )

            if self._chat_manager is not None:
                await self._chat_manager.update_chat(chat)
        except Exception as e:
            logger.exception("Error in query handler: %s", e)
            raise
        finally:
            await self.remove_pending_messages(
                session_id=session_id,
                user_id=user_id,
                msg_ids=pending_ids,
            )

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        # Load environment variables from .env file
        env_path = Path(__file__).resolve().parents[4] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment variables from {env_path}")
        else:
            logger.debug(
                f".env file not found at {env_path}, "
                "using existing environment variables",
            )

        session_dir = str(WORKING_DIR / "sessions")
        self.session = JSONSession(save_dir=session_dir)

        tavily_search_client = StdIOStatefulClient(
            name="tavily_mcp",
            command="npx",
            args=["-y", "tavily-mcp@latest"],
            env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
        )
        try:
            await tavily_search_client.connect()
            self._tavily_search_client = tavily_search_client
        except Exception as e:
            logger.debug(f"tavily-mcp connect failed: {e}")

        try:
            if self.memory_manager is None:
                self.memory_manager = MemoryManager(
                    working_dir=str(WORKING_DIR),
                )
            await self.memory_manager.start()
        except Exception as e:
            logger.exception(f"MemoryManager start failed: {e}")

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """

        for client in (self._tavily_search_client,):
            if client is None:
                continue
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing MCP client: {e}")
        self._tavily_search_client = None

        try:
            await self.memory_manager.close()
        except Exception as e:
            logger.warning(f"MemoryManager stop failed: {e}")
