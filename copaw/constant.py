# -*- coding: utf-8 -*-
import os
from pathlib import Path

WORKING_DIR = (
    Path(os.environ.get("COPAW_WORKING_DIR", "~/.copaw"))
    .expanduser()
    .resolve()
)

JOBS_FILE = os.environ.get("COPAW_JOBS_FILE", "jobs.json")

CHATS_FILE = os.environ.get("COPAW_CHATS_FILE", "chats.json")

CONFIG_FILE = os.environ.get("COPAW_CONFIG_FILE", "config.json")

HEARTBEAT_FILE = os.environ.get("COPAW_HEARTBEAT_FILE", "HEARTBEAT.md")
HEARTBEAT_DEFAULT_EVERY = "30m"
HEARTBEAT_DEFAULT_TARGET = "main"
HEARTBEAT_TARGET_LAST = "last"

# Env key for app log level (used by CLI and app load for reload child).
LOG_LEVEL_ENV = "COPAW_LOG_LEVEL"

# When True, expose /docs, /redoc, /openapi.json
# (dev only; keep False in prod).
DOCS_ENABLED = os.environ.get("COPAW_OPENAPI_DOCS", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Skills directories
# Active skills directory (activated skills that agents use)
ACTIVE_SKILLS_DIR = WORKING_DIR / "active_skills"
# Customized skills directory (user-created skills)
CUSTOMIZED_SKILLS_DIR = WORKING_DIR / "customized_skills"

# Memory directory
MEMORY_DIR = WORKING_DIR / "memory"

# Memory compaction configuration
MEMORY_COMPACT_THRESHOLD = int(
    os.environ.get("COPAW_MEMORY_COMPACT_THRESHOLD", "100000"),
)

MEMORY_COMPACT_KEEP_RECENT = int(
    os.environ.get("COPAW_MEMORY_COMPACT_KEEP_RECENT", "5"),
)

DASHSCOPE_BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# ---------------------------------------------------------------------------
# Channel availability — controlled by COPAW_ENABLED_CHANNELS env var.
# When unset / empty, ALL channels are available (wheel / local dev).
# Set to a comma-separated list to restrict, e.g.
#   COPAW_ENABLED_CHANNELS=dingtalk,feishu,qq,console
# ---------------------------------------------------------------------------
ALL_CHANNELS = ("imessage", "discord", "dingtalk", "feishu", "qq", "console")


def get_available_channels() -> tuple[str, ...]:
    """Return the tuple of channel keys that are enabled for this build/run.

    Reads ``COPAW_ENABLED_CHANNELS`` env var.  If unset or empty, all
    channels are available.
    """
    raw = os.environ.get("COPAW_ENABLED_CHANNELS", "").strip()
    if not raw:
        return ALL_CHANNELS
    enabled = tuple(ch.strip() for ch in raw.split(",") if ch.strip())
    return enabled or ALL_CHANNELS
