"""Remote download ownership is independent from shared local resources."""

import amplifier_module_tool_skills as module
import pytest
from amplifier_module_tool_skills.sources import (
    configured_skills_cache_dir,
    default_skills_cache_dir,
)


@pytest.mark.parametrize('value', ['', '  ', 42, []])
def test_invalid_configured_cache_is_rejected(value):
    with pytest.raises(ValueError, match='nonempty filesystem path'):
        configured_skills_cache_dir({'cache_dir': value})


def test_default_cache_and_shared_home_are_unchanged(tmp_path, monkeypatch):
    shared = tmp_path / 'shared'
    monkeypatch.setenv('AMPLIFIER_HOME', str(shared))
    assert configured_skills_cache_dir({}) is None
    assert default_skills_cache_dir() == shared / 'cache/skills'
    assert configured_skills_cache_dir({'cache_dir': tmp_path / 'owned'}) == tmp_path / 'owned'
    assert default_skills_cache_dir() == shared / 'cache/skills'


@pytest.mark.asyncio
@pytest.mark.parametrize('configured', [False, True])
async def test_startup_and_dynamic_remote_sources_use_same_cache(tmp_path, monkeypatch, configured):
    remote = 'git+https://example.invalid/skills@main'
    owned = tmp_path / 'owned'
    config = {'skills': [remote]}
    if configured:
        config['cache_dir'] = str(owned)
    calls = []

    async def bulk(sources, **kwargs):
        calls.append(kwargs)
        assert sources == [remote]
        return [owned]

    async def single(source, **kwargs):
        calls.append(kwargs)
        assert source == remote
        return owned

    monkeypatch.setattr(module, 'resolve_skill_sources', bulk)
    monkeypatch.setattr(module, 'resolve_skill_source', single)
    resolved, pending = await module._resolve_skill_sources(config, None)
    assert resolved == [owned] and pending == []
    tool = module.SkillsTool(config=config, resolved_dirs=[])
    assert await tool._resolve_source(remote) == owned
    for call in calls:
        if configured:
            assert call['cache_dir'] == owned
        else:
            assert 'cache_dir' not in call
    local = tmp_path / 'local'
    local.mkdir()
    assert await tool._resolve_source(str(local)) == local
    assert len(calls) == 2  # Local skills never enter remote resolution.
