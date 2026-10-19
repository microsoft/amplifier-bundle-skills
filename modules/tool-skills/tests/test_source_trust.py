"""Source provenance must survive remote-to-cache resolution before preprocessing.

No network or provider calls: cloned directories and the child spawner are fake,
while discovery, loading, and harmless printf preprocessing run normally.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from amplifier_module_tool_skills import SkillsTool, mount
from amplifier_module_tool_skills.sources import resolve_skill_sources

REMOTE = "git+https://example.invalid/skills@main"
BLOCKED = "[untrusted skill — shell command blocked]"
MARKER = "<shell-output>PROVENANCE_PROBE</shell-output>"


def _skill(root: Path, name: str = "probe") -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test only\ncontext: fork\n---\n"
        "!`printf PROVENANCE_PROBE`\n",
        encoding="utf-8",
    )


def _coordinator():
    spawn = AsyncMock(return_value={"output": "synthetic child"})
    capabilities = {"session.spawn": spawn}
    coordinator = MagicMock()
    coordinator.config = {}
    coordinator.hooks.emit = AsyncMock()
    coordinator.hooks.register.return_value = lambda: None
    coordinator.get_capability.side_effect = capabilities.get
    coordinator.register_capability.side_effect = capabilities.__setitem__
    coordinator.mount = AsyncMock()
    return coordinator, capabilities, spawn


@pytest.mark.asyncio
@pytest.mark.parametrize("configuration", ["skills", "skills_dirs", "global"])
async def test_configured_remote_fork_blocks_shell_after_cache_resolution(
    tmp_path, monkeypatch, configuration
):
    _skill(tmp_path)
    remote_resolver = AsyncMock(return_value=tmp_path)
    monkeypatch.setattr(
        "amplifier_module_tool_skills.sources.resolve_skill_source", remote_resolver
    )
    coordinator, _, spawn = _coordinator()
    config = {"visibility": {"enabled": False}}
    if configuration == "global":
        coordinator.config["skills"] = {"sources": [REMOTE]}
    else:
        config[configuration] = [REMOTE]

    await mount(coordinator, config)
    tool = coordinator.mount.await_args.args[1]
    result = await tool.execute({"skill_name": "probe"})

    assert result.success
    assert tool.skills["probe"].source == REMOTE
    assert tool.skills["probe"].trusted is False
    assert BLOCKED in spawn.await_args.kwargs["instruction"]
    assert MARKER not in spawn.await_args.kwargs["instruction"]


@pytest.mark.asyncio
@pytest.mark.parametrize("combined_invocation", [False, True])
async def test_source_parameter_retains_remote_trust_for_immediate_or_later_load(
    tmp_path, monkeypatch, combined_invocation
):
    _skill(tmp_path)
    monkeypatch.setattr(
        "amplifier_module_tool_skills.resolve_skill_source",
        AsyncMock(return_value=tmp_path),
    )
    coordinator, _, spawn = _coordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[])
    request = {"source": REMOTE}
    if combined_invocation:
        request["skill_name"] = "probe"
    result = await tool.execute(request)
    assert result.success
    if not combined_invocation:
        assert not spawn.called
        result = await tool.execute({"skill_name": "probe"})
        assert result.success

    assert tool.skills["probe"].source == REMOTE
    assert tool.skills["probe"].trusted is False
    assert BLOCKED in spawn.await_args.kwargs["instruction"]
    assert MARKER not in spawn.await_args.kwargs["instruction"]


@pytest.mark.asyncio
async def test_source_origins_preserve_priority_and_failed_source_alignment(
    tmp_path, monkeypatch
):
    local = tmp_path / "local"
    cached = tmp_path / "cached"
    local.mkdir()
    cached.mkdir()
    failed = "git+https://example.invalid/missing@main"

    async def resolve(source, cache_dir=None):
        return None if source == failed else cached

    monkeypatch.setattr(
        "amplifier_module_tool_skills.sources.resolve_skill_source", resolve
    )
    origins = {}
    paths = await resolve_skill_sources(
        [str(local), failed, REMOTE, str(cached)], source_origins=origins
    )
    assert paths == [local, cached, cached]
    assert origins == {local.resolve(): str(local), cached.resolve(): REMOTE}

    origins = {}
    await resolve_skill_sources([str(cached), REMOTE], source_origins=origins)
    assert origins == {cached.resolve(): str(cached)}


@pytest.mark.asyncio
async def test_local_override_is_not_reclassified_by_shadowed_remote_skill(
    tmp_path, monkeypatch
):
    local, remote = tmp_path / "local", tmp_path / "cached"
    _skill(local)
    _skill(remote)
    monkeypatch.setattr(
        "amplifier_module_tool_skills.sources.resolve_skill_source",
        AsyncMock(return_value=remote),
    )
    coordinator, _, spawn = _coordinator()
    await mount(
        coordinator,
        {"skills": [str(local), REMOTE], "visibility": {"enabled": False}},
    )
    tool = coordinator.mount.await_args.args[1]
    result = await tool.execute({"skill_name": "probe"})
    assert result.success
    assert tool.skills["probe"].source == str(local.resolve())
    assert tool.skills["probe"].trusted is True
    assert MARKER in spawn.await_args.kwargs["instruction"]


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution", ["eager", "deferred", "source"])
async def test_bundle_namespace_retains_existing_authored_shell_behavior(
    tmp_path, resolution
):
    _skill(tmp_path)
    coordinator, capabilities, spawn = _coordinator()
    mention_resolver = MagicMock()
    mention_resolver.resolve.return_value = tmp_path
    if resolution != "deferred":
        capabilities["mention_resolver"] = mention_resolver

    if resolution == "source":
        tool = SkillsTool({}, coordinator, resolved_dirs=[])
        result = await tool.execute({"source": "@example:skills"})
        assert result.success
    else:
        await mount(
            coordinator,
            {"skills": ["@example:skills"], "visibility": {"enabled": False}},
        )
        tool = coordinator.mount.await_args.args[1]
        if resolution == "deferred":
            assert not tool.skills
            capabilities["mention_resolver"] = mention_resolver
            await tool.resolve_pending_mention_sources()

    result = await tool.execute({"skill_name": "probe"})
    assert result.success
    assert MARKER in spawn.await_args.kwargs["instruction"]


@pytest.mark.asyncio
async def test_explicit_untrusted_metadata_blocks_even_with_local_path(tmp_path):
    _skill(tmp_path)
    coordinator, _, spawn = _coordinator()
    tool = SkillsTool({}, coordinator, resolved_dirs=[tmp_path])
    tool.skills["probe"].trusted = False
    result = await tool.execute({"skill_name": "probe"})
    assert result.success
    assert BLOCKED in spawn.await_args.kwargs["instruction"]
    assert MARKER not in spawn.await_args.kwargs["instruction"]


@pytest.mark.asyncio
async def test_rescan_after_mount_keeps_remote_skill_untrusted(tmp_path, monkeypatch):
    remote_resolver = AsyncMock(return_value=tmp_path)
    monkeypatch.setattr(
        "amplifier_module_tool_skills.sources.resolve_skill_source", remote_resolver
    )
    coordinator, _, spawn = _coordinator()
    await mount(coordinator, {"visibility": {"enabled": False}, "skills": [REMOTE]})
    tool = coordinator.mount.await_args.args[1]
    assert "probe" not in tool.skills

    # The remote source's cache gains a skill after mount (a later update).
    _skill(tmp_path)
    result = await tool.execute({"skill_name": "probe"})

    assert result.success
    assert tool.skills["probe"].source == REMOTE
    assert tool.skills["probe"].trusted is False
    assert BLOCKED in spawn.await_args.kwargs["instruction"]
    assert MARKER not in spawn.await_args.kwargs["instruction"]
