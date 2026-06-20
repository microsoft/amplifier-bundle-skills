"""Tests for fork-skill parent-conversation context inheritance.

Locks down the feature that lets a caller opt a fork skill into inheriting
parent-conversation context using the same two-axis model as the delegate
tool (context_depth + context_scope), while defaulting to a clean slate
("none") so existing fork skills are unaffected.

Two layers are proven here:
  1. The pure transforms in context_inheritance (depth/scope filtering, format).
  2. The wiring in SkillsTool._execute_fork — that the selected context is
     actually prepended to the instruction handed to spawn_fn, and that the
     default ("none") changes nothing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifier_module_tool_skills import SkillsTool
from amplifier_module_tool_skills import context_inheritance as ci
from amplifier_module_tool_skills.discovery import SkillMetadata

# --- Sample parent history shared across transform tests -------------------

PARENT_MESSAGES = [
    {"role": "user", "content": "first question"},
    {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "internal reasoning"},
            {"type": "text", "text": "first answer"},
        ],
    },
    {"role": "user", "content": "second question"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
    {"role": "tool", "name": "delegate", "content": "agent findings"},
    {"role": "tool", "name": "bash", "content": "raw bash output"},
    {"role": "assistant", "content": "second answer"},
    {"role": "user", "content": "third question"},
]


# --- Layer 1: pure transforms ----------------------------------------------


def test_depth_none_returns_clean_slate():
    assert ci.build_inherited_context(PARENT_MESSAGES, "none", 5, "conversation") is None


def test_no_messages_returns_none():
    assert ci.build_inherited_context(None, "all", 5, "conversation") is None
    assert ci.build_inherited_context([], "all", 5, "conversation") is None


def test_scope_conversation_strips_tool_and_thinking():
    out = ci.build_inherited_context(PARENT_MESSAGES, "all", 5, "conversation")
    joined = " ".join(m["content"] for m in out)
    assert "first answer" in joined
    assert "internal reasoning" not in joined  # thinking stripped
    assert "agent findings" not in joined  # tool result stripped
    assert "raw bash output" not in joined
    # The pure tool-call assistant turn produced no text -> dropped.
    assert [m["role"] for m in out] == [
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]


def test_scope_agents_includes_delegate_but_not_bash():
    out = ci.build_inherited_context(PARENT_MESSAGES, "all", 5, "agents")
    joined = " ".join(m["content"] for m in out)
    assert "agent findings" in joined
    assert "raw bash output" not in joined


def test_scope_full_includes_all_tool_results():
    out = ci.build_inherited_context(PARENT_MESSAGES, "all", 5, "full")
    joined = " ".join(m["content"] for m in out)
    assert "agent findings" in joined
    assert "raw bash output" in joined


def test_depth_recent_limits_to_last_turn():
    out = ci.build_inherited_context(PARENT_MESSAGES, "recent", 1, "conversation")
    assert out == [{"role": "user", "content": "third question"}]


def test_format_block_has_markers():
    out = ci.build_inherited_context(PARENT_MESSAGES, "recent", 1, "conversation")
    block = ci.format_parent_context(out)
    assert block.startswith("[PARENT CONVERSATION CONTEXT]")
    assert block.rstrip().endswith("[END PARENT CONTEXT]")
    assert "USER: third question" in block


# --- Layer 2: wiring in _execute_fork --------------------------------------


def _make_fork_metadata(tmp_path: Path) -> SkillMetadata:
    skill_dir = tmp_path / "fork-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("# stub\n", encoding="utf-8")
    return SkillMetadata(
        name="fork-skill",
        description="Fork skill under test",
        path=skill_path,
        source=str(tmp_path),
        context="fork",
    )


def _make_coordinator(spawn_fn: AsyncMock, parent_messages=None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.session = MagicMock()
    coordinator.config = {"agents": {}}
    coordinator.hooks = MagicMock()
    coordinator.hooks.emit = AsyncMock()

    # _get_parent_messages() calls coordinator.get("context").get_messages()
    if parent_messages is not None:
        context_mgr = MagicMock()
        context_mgr.get_messages = AsyncMock(return_value=parent_messages)
    else:
        context_mgr = None
    coordinator.get = MagicMock(return_value=context_mgr)

    capabilities = {
        "model_role_resolver": None,
        "session.spawn": spawn_fn,
    }
    coordinator.get_capability = MagicMock(side_effect=capabilities.get)
    return coordinator


def _spawn_fn() -> AsyncMock:
    return AsyncMock(
        return_value={
            "output": "child-output",
            "session_id": "child-1",
            "status": "success",
            "turn_count": 1,
            "metadata": {},
        }
    )


@pytest.mark.asyncio
async def test_default_none_does_not_inject_context(tmp_path):
    """Default fork behavior: instruction == processed body, no context block."""
    spawn = _spawn_fn()
    coordinator = _make_coordinator(spawn, parent_messages=PARENT_MESSAGES)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_fork_metadata(tmp_path)

    with patch(
        "amplifier_module_tool_skills.preprocess",
        new=AsyncMock(return_value="PROCESSED BODY"),
    ):
        await tool._execute_fork("fork-skill", metadata, "raw body")

    instruction = spawn.await_args.kwargs["instruction"]
    assert instruction == "PROCESSED BODY"
    assert "PARENT CONVERSATION CONTEXT" not in instruction


@pytest.mark.asyncio
async def test_depth_all_prepends_parent_context(tmp_path):
    """Opting in: parent context block is prepended before the task body."""
    spawn = _spawn_fn()
    coordinator = _make_coordinator(spawn, parent_messages=PARENT_MESSAGES)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_fork_metadata(tmp_path)

    with patch(
        "amplifier_module_tool_skills.preprocess",
        new=AsyncMock(return_value="PROCESSED BODY"),
    ):
        await tool._execute_fork(
            "fork-skill",
            metadata,
            "raw body",
            context_depth="all",
            context_scope="conversation",
        )

    instruction = spawn.await_args.kwargs["instruction"]
    assert "[PARENT CONVERSATION CONTEXT]" in instruction
    assert "[YOUR TASK]" in instruction
    assert instruction.endswith("PROCESSED BODY")
    assert "first answer" in instruction
    # Context precedes the task.
    assert instruction.index("PARENT CONVERSATION CONTEXT") < instruction.index(
        "[YOUR TASK]"
    )


@pytest.mark.asyncio
async def test_optin_but_no_parent_context_is_clean(tmp_path):
    """Opting in with no available parent context falls back to a clean body."""
    spawn = _spawn_fn()
    coordinator = _make_coordinator(spawn, parent_messages=None)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_fork_metadata(tmp_path)

    with patch(
        "amplifier_module_tool_skills.preprocess",
        new=AsyncMock(return_value="PROCESSED BODY"),
    ):
        await tool._execute_fork(
            "fork-skill", metadata, "raw body", context_depth="all"
        )

    instruction = spawn.await_args.kwargs["instruction"]
    assert instruction == "PROCESSED BODY"
