# -*- coding: utf-8 -*-
# CoPawAgent is lazy-loaded so that importing agents.skills_manager (e.g.
# from CLI init_cmd/skills_cmd) does not pull react_agent, agentscope, tools.
# pylint: disable=undefined-all-variable
__all__ = ["CoPawAgent"]


def __getattr__(name: str):
    if name == "CoPawAgent":
        from .react_agent import CoPawAgent

        return CoPawAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
