"""Tests for enhanced skill discovery with new frontmatter fields."""

import pytest
from pathlib import Path

from amplifier_module_tool_skills.discovery import SkillMetadata, discover_skills


# ---------------------------------------------------------------------------
# Mock infrastructure for skill:loaded event tests
# ---------------------------------------------------------------------------


class MockHooks:
    """Mock hooks system that tracks registrations and emitted events."""

    def __init__(self):
        self.registered_hooks = []
        self.emitted_events = []

    def register(
        self, event: str, handler, priority: int = 10, name: str | None = None
    ):
        self.registered_hooks.append(
            {"event": event, "handler": handler, "priority": priority, "name": name}
        )

    async def emit(self, event_name: str, data):
        self.emitted_events.append((event_name, data))


class MockCoordinator:
    """Mock coordinator for testing event emission."""

    def __init__(self):
        self.capabilities = {}
        self.mounted_tools = {}
        self.hooks = MockHooks()
        self.config = {}

    def register_capability(self, name: str, value):
        self.capabilities[name] = value

    def get_capability(self, name: str):
        return self.capabilities.get(name)

    async def mount(self, category: str, tool, name: str):
        self.mounted_tools[name] = tool


def test_skill_metadata_enhanced_fields_defaults():
    """SkillMetadata has all 7 new fields with correct defaults."""
    metadata = SkillMetadata(
        name="test-skill",
        description="A test skill",
        path=Path("/skills/test-skill/SKILL.md"),
        source="/skills",
    )

    assert metadata.context is None
    assert metadata.agent is None
    assert metadata.disable_model_invocation is False
    assert metadata.user_invocable is False
    assert metadata.model is None
    assert metadata.model_role is None
    assert metadata.provider_preferences is None


def test_discover_skills_parses_enhanced_frontmatter(tmp_path: Path):
    """discover_skills() correctly parses enhanced frontmatter fields."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: my-skill
description: A skill with enhanced fields
context: fork
agent: foundation:explorer
disable-model-invocation: true
user-invocable: false
model: claude-opus-4-5
model_role: coding
provider_preferences:
  - provider: anthropic
    model: claude-opus-4-5
---
Body content
"""
    )

    skills = discover_skills(tmp_path)
    assert "my-skill" in skills

    skill = skills["my-skill"]
    assert skill.context == "fork"
    assert skill.agent == "foundation:explorer"
    assert skill.disable_model_invocation is True
    assert skill.user_invocable is False
    assert skill.model == "claude-opus-4-5"
    assert skill.model_role == "coding"
    assert skill.provider_preferences == [
        {"provider": "anthropic", "model": "claude-opus-4-5"}
    ]


def test_discover_skills_backward_compatible(tmp_path: Path):
    """Existing skills without enhanced fields still work."""
    skill_dir = tmp_path / "old-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: old-skill
description: A legacy skill without enhanced fields
version: 1.0.0
---
Body content
"""
    )

    skills = discover_skills(tmp_path)
    assert "old-skill" in skills

    skill = skills["old-skill"]
    assert skill.name == "old-skill"
    assert skill.description == "A legacy skill without enhanced fields"
    assert skill.version == "1.0.0"
    # Enhanced fields should have defaults
    assert skill.context is None
    assert skill.agent is None
    assert skill.disable_model_invocation is False
    assert skill.user_invocable is False
    assert skill.model is None
    assert skill.model_role is None
    assert skill.provider_preferences is None


def test_discover_skills_model_role_as_list(tmp_path: Path):
    """model_role can be a list (fallback chain)."""
    skill_dir = tmp_path / "multi-model-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: multi-model-skill
description: A skill with model_role as a list
model_role:
  - reasoning
  - coding
  - general
---
Body content
"""
    )

    skills = discover_skills(tmp_path)
    assert "multi-model-skill" in skills

    skill = skills["multi-model-skill"]
    assert isinstance(skill.model_role, list)
    assert skill.model_role == ["reasoning", "coding", "general"]


def test_discover_skills_snake_case_keys(tmp_path: Path):
    """discover_skills() supports both hyphen-case and snake_case keys."""
    skill_dir = tmp_path / "snake-case-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: snake-case-skill
description: A skill using snake_case keys
disable_model_invocation: true
user_invocable: false
---
Body content
"""
    )

    skills = discover_skills(tmp_path)
    assert "snake-case-skill" in skills

    skill = skills["snake-case-skill"]
    assert skill.disable_model_invocation is True
    assert skill.user_invocable is False


# ---------------------------------------------------------------------------
# Tests for enriched skill:loaded event (acceptance criteria for task-5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_loaded_event_includes_context(tmp_path: Path):
    """skill:loaded event includes context field from metadata."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "ctx-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: ctx-skill
description: Skill with context field
context: fork
---
Body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("ctx-skill")

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]
    assert "context" in event_data
    assert event_data["context"] == "fork"


@pytest.mark.asyncio
async def test_skill_loaded_event_includes_disable_model_invocation(tmp_path: Path):
    """skill:loaded event includes disable_model_invocation field from metadata."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "dmi-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: dmi-skill
description: Skill with disable-model-invocation
disable-model-invocation: true
---
Body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("dmi-skill")

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]
    assert "disable_model_invocation" in event_data
    assert event_data["disable_model_invocation"] is True


@pytest.mark.asyncio
async def test_skill_loaded_event_includes_user_invocable(tmp_path: Path):
    """skill:loaded event includes user_invocable field from metadata."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "ui-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: ui-skill
description: Skill with user-invocable false
user-invocable: false
---
Body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("ui-skill")

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]
    assert "user_invocable" in event_data
    assert event_data["user_invocable"] is False


@pytest.mark.asyncio
async def test_skill_loaded_event_includes_allowed_tools(tmp_path: Path):
    """skill:loaded event includes allowed_tools field from metadata."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "at-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: at-skill
description: Skill with allowed-tools
allowed-tools:
  - bash
  - read_file
---
Body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("at-skill")

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]
    assert "allowed_tools" in event_data
    assert event_data["allowed_tools"] == ["bash", "read_file"]


@pytest.mark.asyncio
async def test_skill_loaded_event_includes_slash_command(tmp_path: Path):
    """skill:loaded event includes slash_command field (derived from skill name)."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: my-skill
description: A test skill
---
Body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("my-skill")

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]
    assert "slash_command" in event_data
    assert event_data["slash_command"] == "my-skill"


@pytest.mark.asyncio
async def test_skill_loaded_event_all_enriched_fields_present(tmp_path: Path):
    """skill:loaded event includes all enriched fields with MockCoordinator/MockHooks."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "full-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: full-skill
description: Skill with all enhanced fields
version: 1.2.3
context: fork
disable-model-invocation: true
user-invocable: false
allowed-tools:
  - bash
  - write_file
---
Full skill body content
"""
    )

    coordinator = MockCoordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("full-skill")

    assert result.success is True

    events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(events) == 1
    event_data = events[0][1]

    # Existing fields still present
    assert event_data["skill_name"] == "full-skill"
    assert event_data["source"] is not None
    assert event_data["content_length"] > 0
    assert event_data["version"] == "1.2.3"
    assert event_data["skill_directory"] is not None
    assert "hooks" in event_data

    # New enriched fields
    assert event_data["context"] == "fork"
    assert event_data["disable_model_invocation"] is True
    assert event_data["user_invocable"] is False
    assert event_data["allowed_tools"] == ["bash", "write_file"]
    assert event_data["slash_command"] == "full-skill"


# ---------------------------------------------------------------------------
# Tests for preprocessing wiring in _load_skill() (acceptance criteria task-7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_skill_substitutes_skill_dir(tmp_path: Path):
    """${SKILL_DIR} is substituted in loaded inline skill content."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "dir-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: dir-skill
description: Skill with SKILL_DIR placeholder
---
The skill lives at ${SKILL_DIR} and has companion files there.
"""
    )

    tool = SkillsTool({}, None, resolved_dirs=[tmp_path])
    result = await tool._load_skill("dir-skill")

    assert result.success is True
    assert result.output is not None
    content = result.output["content"]
    # ${SKILL_DIR} should NOT appear in result
    assert "${SKILL_DIR}" not in content
    # Actual skill directory path should appear
    assert str(skill_dir) in content


@pytest.mark.asyncio
async def test_load_skill_skill_dir_placeholder_replaced_with_actual_path(
    tmp_path: Path,
):
    """The actual skill directory path appears in result content."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "path-skill"
    skill_dir.mkdir()
    expected_path = str(skill_dir)
    (skill_dir / "SKILL.md").write_text(
        """---
name: path-skill
description: Skill to verify path replacement
---
Reference: ${SKILL_DIR}/examples/code.py
"""
    )

    tool = SkillsTool({}, None, resolved_dirs=[tmp_path])
    result = await tool._load_skill("path-skill")

    assert result.success is True
    assert result.output is not None
    content = result.output["content"]
    assert f"{expected_path}/examples/code.py" in content


@pytest.mark.asyncio
async def test_load_skill_fork_skill_not_preprocessed(tmp_path: Path):
    """Fork skills (context: fork) are NOT preprocessed in _load_skill()."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "fork-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: fork-skill
description: Fork skill with SKILL_DIR placeholder
context: fork
---
Fork path: ${SKILL_DIR}/data
"""
    )

    tool = SkillsTool({}, None, resolved_dirs=[tmp_path])
    result = await tool._load_skill("fork-skill")

    assert result.success is True
    assert result.output is not None
    content = result.output["content"]
    # Fork skills should NOT have ${SKILL_DIR} substituted at this point
    assert "${SKILL_DIR}" in content


@pytest.mark.asyncio
async def test_load_skill_inline_skill_no_placeholders_unaffected(tmp_path: Path):
    """Inline skills without ${SKILL_DIR} are returned unchanged."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "plain-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: plain-skill
description: Plain skill without any placeholders
---
Just plain content here, no substitutions needed.
"""
    )

    tool = SkillsTool({}, None, resolved_dirs=[tmp_path])
    result = await tool._load_skill("plain-skill")

    assert result.success is True
    assert result.output is not None
    content = result.output["content"]
    assert "Just plain content here, no substitutions needed." in content


# ---------------------------------------------------------------------------
# Tests for context:fork execution via delegate (acceptance criteria task-8)
# ---------------------------------------------------------------------------


class MockCoordinatorWithSpawn(MockCoordinator):
    """Extended mock coordinator that includes session.spawn capability."""

    def __init__(self, spawn_fn=None):
        super().__init__()
        self.session = None  # Matches coordinator.session (parent session)
        self.session_id = "test-parent-session"
        self.config = {"agents": {}}  # Matches coordinator.config["agents"]
        if spawn_fn is not None:
            self.capabilities["session.spawn"] = spawn_fn


@pytest.mark.asyncio
async def test_fork_skill_calls_spawn_fn_with_preprocessed_instruction(
    tmp_path: Path,
):
    """Fork skill with session.spawn calls spawn_fn with preprocessed instruction."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "fork-exec-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: fork-exec-skill
description: Fork skill for testing spawn
context: fork
---
The skill lives at ${SKILL_DIR} and is a fork skill.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Delegate response",
            "session_id": "sess-123",
            "turn_count": 3,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("fork-exec-skill")

    # spawn_fn should have been called
    assert len(spawn_calls) == 1
    call = spawn_calls[0]

    # instruction should be the preprocessed body — ${SKILL_DIR} must be substituted
    instruction = call["instruction"]
    assert "${SKILL_DIR}" not in instruction
    assert str(skill_dir) in instruction


@pytest.mark.asyncio
async def test_fork_skill_spawn_fn_receives_correct_agent_name(tmp_path: Path):
    """spawn_fn receives agent_name='self' for fork execution."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "named-fork-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: named-fork-skill
description: Fork skill for agent_name test
context: fork
---
Body content here.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-abc",
            "turn_count": 1,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("named-fork-skill")

    assert len(spawn_calls) == 1
    assert spawn_calls[0]["agent_name"] == "self"


@pytest.mark.asyncio
async def test_fork_skill_result_contains_delegate_output(tmp_path: Path):
    """Result contains delegate output (response, session_id, status, context, turn_count)."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "delegate-result-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: delegate-result-skill
description: Fork skill for result test
context: fork
---
Body content.
"""
    )

    async def mock_spawn_fn(**kwargs):
        return {
            "output": "The delegate response text",
            "session_id": "delegate-session-456",
            "turn_count": 5,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("delegate-result-skill")

    assert result.success is True
    assert result.output is not None
    output = result.output
    assert output["response"] == "The delegate response text"
    assert output["session_id"] == "delegate-session-456"
    assert output["turn_count"] == 5
    assert output["status"] == "completed"
    assert output["skill_name"] == "delegate-result-skill"
    assert output["context"] == "fork"
    # message field frames the fork result for the parent LLM
    assert "message" in output
    assert "delegate-result-skill" in output["message"]
    assert "The delegate response text" in output["message"]


@pytest.mark.asyncio
async def test_fork_skill_without_spawn_falls_back_to_inline(tmp_path: Path):
    """Fork skill without session.spawn falls back to inline injection."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "inline-fallback-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: inline-fallback-skill
description: Fork skill that falls back to inline
context: fork
---
Body content without spawn.
"""
    )

    # Coordinator without session.spawn capability
    coordinator = MockCoordinatorWithSpawn(spawn_fn=None)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("inline-fallback-skill")

    # Should fall back to inline — result has 'content' key
    assert result.success is True
    assert result.output is not None
    assert "content" in result.output
    assert "inline-fallback-skill" in result.output["content"]


@pytest.mark.asyncio
async def test_fork_skill_model_resolver_called_with_metadata_fields(tmp_path: Path):
    """Model resolver is called with metadata's provider_preferences/model_role/model/agent."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "model-resolve-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: model-resolve-skill
description: Fork skill with model fields
context: fork
model_role: reasoning
---
Body content.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-xyz",
            "turn_count": 2,
            "status": "completed",
        }

    # Set up routing matrix that resolves 'reasoning' to provider_preferences
    class MockRoutingMatrix:
        def resolve(self, model_role: str):
            if model_role == "reasoning":
                return [{"provider": "anthropic", "model": "claude-opus-*"}]
            return None

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    coordinator.capabilities["routing_matrix"] = MockRoutingMatrix()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("model-resolve-skill")

    assert result.success is True
    assert len(spawn_calls) == 1
    # routing matrix should have resolved model_role → provider_preferences
    assert spawn_calls[0]["provider_preferences"] == [
        {"provider": "anthropic", "model": "claude-opus-*"}
    ]


@pytest.mark.asyncio
async def test_fork_skill_provider_preferences_passed_directly(tmp_path: Path):
    """provider_preferences from metadata is passed directly to spawn_fn (no routing needed)."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "prefs-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: prefs-skill
description: Fork skill with explicit provider_preferences
context: fork
provider_preferences:
  - provider: openai
    model: gpt-4o
---
Body content.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-prefs",
            "turn_count": 1,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("prefs-skill")

    assert result.success is True
    assert len(spawn_calls) == 1
    # provider_preferences should be passed directly from metadata
    assert spawn_calls[0]["provider_preferences"] == [
        {"provider": "openai", "model": "gpt-4o"}
    ]


@pytest.mark.asyncio
async def test_fork_skill_exception_returns_error_toolresult(tmp_path: Path):
    """Exceptions in spawn_fn are caught and returned as error ToolResult."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "exception-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: exception-skill
description: Fork skill that raises an exception
context: fork
---
Body content.
"""
    )

    async def failing_spawn_fn(**kwargs):
        raise RuntimeError("Spawn failed: connection refused")

    coordinator = MockCoordinatorWithSpawn(spawn_fn=failing_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("exception-skill")

    assert result.success is False
    assert result.error is not None
    assert "Fork execution failed" in result.error["message"]


# ---------------------------------------------------------------------------
# Tests for allowed-tools enforcement in _execute_fork() (task-10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_skill_with_allowed_tools_passes_tool_inheritance(
    tmp_path: Path,
):
    """Fork skill with allowed-tools passes tool_inheritance to spawn_fn."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "allowed-tools-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: allowed-tools-skill
description: Fork skill with allowed-tools
context: fork
allowed-tools:
  - bash
  - read_file
  - grep
---
Body content.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-at",
            "turn_count": 1,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    result = await tool._load_skill("allowed-tools-skill")

    assert result.success is True
    assert len(spawn_calls) == 1
    # tool_inheritance must be passed
    assert "tool_inheritance" in spawn_calls[0]
    # tool_inheritance must contain allowed_tools key with the list
    tool_inheritance = spawn_calls[0]["tool_inheritance"]
    assert "allowed_tools" in tool_inheritance
    assert tool_inheritance["allowed_tools"] == ["bash", "read_file", "grep"]


@pytest.mark.asyncio
async def test_fork_skill_tool_inheritance_exact_allowed_tools_list(
    tmp_path: Path,
):
    """spawn_fn receives tool_inheritance={'allowed_tools': ['bash', 'read_file', 'grep']}."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "exact-tools-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: exact-tools-skill
description: Fork skill to verify exact tool_inheritance value
context: fork
allowed-tools:
  - bash
  - read_file
  - grep
---
Body content.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-exact",
            "turn_count": 1,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("exact-tools-skill")

    assert len(spawn_calls) == 1
    assert spawn_calls[0]["tool_inheritance"] == {
        "allowed_tools": ["bash", "read_file", "grep"]
    }


@pytest.mark.asyncio
async def test_fork_skill_without_allowed_tools_passes_empty_tool_inheritance(
    tmp_path: Path,
):
    """Fork skill without allowed-tools passes empty tool_inheritance dict to spawn_fn."""
    from amplifier_module_tool_skills import SkillsTool

    skill_dir = tmp_path / "no-tools-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: no-tools-skill
description: Fork skill without allowed-tools
context: fork
---
Body content.
"""
    )

    spawn_calls = []

    async def mock_spawn_fn(**kwargs):
        spawn_calls.append(kwargs)
        return {
            "output": "Result",
            "session_id": "sess-no-tools",
            "turn_count": 1,
            "status": "completed",
        }

    coordinator = MockCoordinatorWithSpawn(spawn_fn=mock_spawn_fn)
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])  # type: ignore[arg-type]
    await tool._load_skill("no-tools-skill")

    assert len(spawn_calls) == 1
    # tool_inheritance must be passed but empty
    assert "tool_inheritance" in spawn_calls[0]
    assert spawn_calls[0]["tool_inheritance"] == {}
