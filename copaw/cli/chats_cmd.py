# -*- coding: utf-8 -*-
"""CLI commands for managing chats via HTTP API (/chats)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from .http import client, print_json
from ..app.channels.schema import DEFAULT_CHANNEL


def _base_url(ctx: click.Context, base_url: Optional[str]) -> str:
    """Resolve base_url with priority:
    1) command --base-url
    2) global --host/--port
        (already resolved in main.py, may come from config.json)
    """
    if base_url:
        return base_url.rstrip("/")
    host = (ctx.obj or {}).get("host", "127.0.0.1")
    port = (ctx.obj or {}).get("port", 8088)
    return f"http://{host}:{port}"


@click.group("chats")
def chats_group() -> None:
    """管理会话（Chat）——通过 HTTP API (/chats)。

    \b
    常用示例：
      copaw chats list                          # 列出所有会话
      copaw chats list --user-id alice           # 按用户筛选
      copaw chats get <chat_id>       # 查看详情
      copaw chats create --session-id s1 --user-id u1
      copaw chats delete <chat_id>               # 删除指定会话
    """


@chats_group.command("list")
@click.option(
    "--user-id",
    default=None,
    help="按用户 ID 筛选，如 alice",
)
@click.option(
    "--channel",
    default=None,
    help=("按渠道名称筛选，如 console" " / imessage / dingtalk / discord / qq"),
)
@click.option(
    "--base-url",
    default=None,
    help="覆盖 API 地址，如 http://127.0.0.1:8088",
)
@click.pass_context
def list_chats(
    ctx: click.Context,
    user_id: Optional[str],
    channel: Optional[str],
    base_url: Optional[str],
) -> None:
    """列出所有会话，支持按 user_id / channel 筛选。

    \b
    示例：
      copaw chats list
      copaw chats list --user-id alice
      copaw chats list --channel discord
      copaw chats list --user-id alice --channel discord
    """
    base_url = _base_url(ctx, base_url)
    params: dict[str, str] = {}
    if user_id:
        params["user_id"] = user_id
    if channel:
        params["channel"] = channel
    with client(base_url) as c:
        r = c.get("/chats", params=params)
        r.raise_for_status()
        print_json(r.json())


@chats_group.command("get")
@click.argument("chat_id")
@click.option("--base-url", default=None, help="覆盖 API 地址")
@click.pass_context
def get_chat(
    ctx: click.Context,
    chat_id: str,
    base_url: Optional[str],
) -> None:
    """查看指定会话的详细信息（含消息历史）。

    \b
    CHAT_ID  会话 UUID，可通过 `copaw chats list` 获取。

    \b
    示例：
      copaw chats get 823845fe-dd13-43c2-ab8b-d05870602fd8
    """
    base_url = _base_url(ctx, base_url)
    with client(base_url) as c:
        r = c.get(f"/chats/{chat_id}")
        if r.status_code == 404:
            raise click.ClickException(f"chat not found: {chat_id}")
        r.raise_for_status()
        print_json(r.json())


@chats_group.command("create")
@click.option(
    "-f",
    "--file",
    "file_",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="从 JSON 文件创建（与内联参数二选一）",
)
@click.option(
    "--name",
    default="New Chat",
    help="会话名称（默认 'New Chat'）",
)
@click.option(
    "--session-id",
    default=None,
    help=("会话标识，格式通常为" " channel:user_id（内联创建时必填）"),
)
@click.option(
    "--user-id",
    default=None,
    help="用户 ID（内联创建时必填）",
)
@click.option(
    "--channel",
    default=DEFAULT_CHANNEL,
    help=(
        "渠道名称，如 console / imessage / dingtalk"
        f" / discord / qq（默认 {DEFAULT_CHANNEL}）"
    ),
)
@click.option("--base-url", default=None, help="覆盖 API 地址")
@click.pass_context
def create_chat(
    ctx: click.Context,
    file_: Optional[Path],
    name: str,
    session_id: Optional[str],
    user_id: Optional[str],
    channel: str,
    base_url: Optional[str],
) -> None:
    """创建新会话。

    可用 -f 指定 JSON 文件，或用内联参数。

    \b
    内联创建示例：
      copaw chats create --session-id "discord:alice" \\
        --user-id alice --name "My Chat"
      copaw chats create --session-id s1 --user-id u1 --channel imessage

    \b
    JSON 文件创建示例：
      copaw chats create -f chat.json
    """
    base_url = _base_url(ctx, base_url)
    if file_ is not None:
        payload = json.loads(file_.read_text(encoding="utf-8"))
    else:
        if not session_id:
            raise click.UsageError("内联创建时 --session-id 为必填")
        if not user_id:
            raise click.UsageError("内联创建时 --user-id 为必填")
        payload = {
            "id": "",
            "name": name,
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "meta": {},
        }
    with client(base_url) as c:
        r = c.post("/chats", json=payload)
        r.raise_for_status()
        print_json(r.json())


@chats_group.command("update")
@click.argument("chat_id")
@click.option("--name", required=True, help="新的会话名称")
@click.option("--base-url", default=None, help="覆盖 API 地址")
@click.pass_context
def update_chat(
    ctx: click.Context,
    chat_id: str,
    name: str,
    base_url: Optional[str],
) -> None:
    """修改会话名称。

    \b
    CHAT_ID  会话 UUID，可通过 `copaw chats list` 获取。

    \b
    示例：
      copaw chats update <chat_id> --name "Renamed Chat"
    """
    base_url = _base_url(ctx, base_url)

    # Fetch existing spec, then patch name
    with client(base_url) as c:
        r = c.get("/chats")
        r.raise_for_status()
        specs = r.json()

    payload = next((s for s in specs if s.get("id") == chat_id), None)
    if payload is None:
        raise click.ClickException(f"chat not found: {chat_id}")

    payload["name"] = name

    with client(base_url) as c:
        r = c.put(f"/chats/{chat_id}", json=payload)
        if r.status_code == 404:
            raise click.ClickException(f"chat not found: {chat_id}")
        r.raise_for_status()
        print_json(r.json())


@chats_group.command("delete")
@click.argument("chat_id")
@click.option("--base-url", default=None, help="覆盖 API 地址")
@click.pass_context
def delete_chat(
    ctx: click.Context,
    chat_id: str,
    base_url: Optional[str],
) -> None:
    """删除指定会话。

    仅删除 Chat 元信息，不清除 Redis 中的会话状态。

    \b
    CHAT_ID  会话 UUID，可通过 `copaw chats list` 获取。

    \b
    示例：
      copaw chats delete 823845fe-dd13-43c2-ab8b-d05870602fd8
    """
    base_url = _base_url(ctx, base_url)
    with client(base_url) as c:
        r = c.delete(f"/chats/{chat_id}")
        if r.status_code == 404:
            raise click.ClickException(f"chat not found: {chat_id}")
        r.raise_for_status()
        print_json(r.json())
