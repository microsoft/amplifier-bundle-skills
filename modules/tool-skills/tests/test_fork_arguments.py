"""Tests for fork-skill $ARGUMENTS delivery.

Locks down the fix for the council bug: a fork skill's sub-session cannot see
the parent conversation, so a /command's argument text must be threaded through
the load_skill tool -> _load_skill -> _execute_fork -> preprocess(arguments=...)
and substituted into the body's $ARGUMENTS. Before the fix, _execute_fork
hardcoded arguments=None, so $ARGUMENTS was always "" inside the fork and
council's "empty -> stop" guard fired on every invocation.

These tests run the REAL preprocess (not mocked), so they prove actual
$ARGUMENTS substitution end-to-end inside _execute_fork.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from amplifier_module_tool_skills import SkillsTool
from amplifier_module_tool_skills.discovery import SkillMetadata


def _make_skill(tmp_path: Path, *, body: str, context: str) -> SkillMetadata:
    skill_dir = tmp_path / "arg-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    # Frontmatter + body; extract_skill_body reads the body after frontmatter.
    skill_path.write_text(
        f"---\nname: arg-skill\ndescription: test\ncontext: {context}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return SkillMetadata(
        name="arg-skill",
        description="arg skill under test",
        path=skill_path,
        source=str(tmp_path),
        context=context,
    )


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


def _coordinator(spawn: AsyncMock) -> MagicMock:
    coordinator = MagicMock()
    coordinator.session = MagicMock()
    coordinator.config = {"agents": {}}
    coordinator.hooks = MagicMock()
    coordinator.hooks.emit = AsyncMock()
    coordinator.get = MagicMock(return_value=None)
    capabilities = {"model_role_resolver": None, "session.spawn": spawn}
    coordinator.get_capability = MagicMock(side_effect=capabilities.get)
    return coordinator


@pytest.mark.asyncio
async def test_fork_substitutes_arguments_into_body(tmp_path):
    """$ARGUMENTS in a fork body resolves to the passed argument string."""
    spawn = _spawn_fn()
    coordinator = _coordinator(spawn)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_skill(
        tmp_path, body="Review the target: $ARGUMENTS", context="fork"
    )

    await tool._execute_fork(
        "arg-skill", metadata, "Review the target: $ARGUMENTS", arguments="src/app.py"
    )

    instruction = spawn.await_args.kwargs["instruction"]
    assert "Review the target: src/app.py" in instruction
    assert "$ARGUMENTS" not in instruction


@pytest.mark.asyncio
async def test_fork_empty_arguments_yields_empty_substitution(tmp_path):
    """No arguments -> $ARGUMENTS becomes empty (historical behavior preserved)."""
    spawn = _spawn_fn()
    coordinator = _coordinator(spawn)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_skill(tmp_path, body="Target=[$ARGUMENTS]", context="fork")

    await tool._execute_fork("arg-skill", metadata, "Target=[$ARGUMENTS]")

    instruction = spawn.await_args.kwargs["instruction"]
    assert "Target=[]" in instruction


@pytest.mark.asyncio
async def test_load_skill_threads_arguments_to_fork(tmp_path):
    """execute(arguments=...) reaches the fork body via _load_skill -> _execute_fork."""
    spawn = _spawn_fn()
    coordinator = _coordinator(spawn)
    tool = SkillsTool(config={}, coordinator=coordinator, resolved_dirs=[])
    metadata = _make_skill(tmp_path, body="Do $ARGUMENTS", context="fork")
    # Register the skill so execute() can find it by name.
    tool.skills["arg-skill"] = metadata

    result = await tool.execute({"skill_name": "arg-skill", "arguments": "the thing"})

    assert result.success
    instruction = spawn.await_args.kwargs["instruction"]
    assert "Do the thing" in instruction
