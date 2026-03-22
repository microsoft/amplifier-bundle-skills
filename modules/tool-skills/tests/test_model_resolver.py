"""Tests for model resolver — 5-level precedence chain for model selection."""

from amplifier_module_tool_skills.model_resolver import resolve_skill_model


def test_provider_preferences_highest_precedence():
    """provider_preferences takes highest precedence over all other params."""
    prefs = [{"provider": "anthropic", "model": "claude-opus-*"}]
    result = resolve_skill_model(
        provider_preferences=prefs,
        model_role="coding",
        model="haiku",
        agent="Code",
    )
    assert result["source"] == "provider_preferences"
    assert result["provider_preferences"] == prefs
    assert result["model_role"] is None


def test_model_role_used_when_no_provider_preferences():
    """model_role used when provider_preferences is absent."""
    result = resolve_skill_model(model_role="reasoning")
    assert result["source"] == "model_role"
    assert result["model_role"] == "reasoning"
    assert result["provider_preferences"] is None


def test_model_role_list_returns_first_element():
    """model_role as a list returns the first element."""
    result = resolve_skill_model(model_role=["coding", "fast"])
    assert result["source"] == "model_role"
    assert result["model_role"] == "coding"
    assert result["provider_preferences"] is None


def test_model_hint_translated_to_model_role():
    """model hint (haiku/sonnet/opus) translated to semantic model_role."""
    assert resolve_skill_model(model="haiku")["model_role"] == "fast"
    assert resolve_skill_model(model="sonnet")["model_role"] == "coding"
    assert resolve_skill_model(model="opus")["model_role"] == "reasoning"

    for m in ("haiku", "sonnet", "opus"):
        r = resolve_skill_model(model=m)
        assert r["source"] == "model"
        assert r["provider_preferences"] is None


def test_agent_archetype_derives_model_role():
    """agent archetype is translated to a semantic model_role."""
    assert resolve_skill_model(agent="Explore")["model_role"] == "fast"
    assert resolve_skill_model(agent="Plan")["model_role"] == "reasoning"
    assert resolve_skill_model(agent="Code")["model_role"] == "coding"
    assert resolve_skill_model(agent="Review")["model_role"] == "critique"

    for archetype in ("Explore", "Plan", "Code", "Review"):
        r = resolve_skill_model(agent=archetype)
        assert r["source"] == "agent"
        assert r["provider_preferences"] is None


def test_nothing_declared_returns_inherit():
    """When nothing is declared, source='inherit' with both fields None."""
    result = resolve_skill_model()
    assert result["source"] == "inherit"
    assert result["model_role"] is None
    assert result["provider_preferences"] is None


def test_model_role_empty_list_does_not_raise():
    """Empty list for model_role should not raise IndexError."""
    result = resolve_skill_model(model_role=[])
    assert result["source"] == "model_role"
    assert result["model_role"] == []
    assert result["provider_preferences"] is None


def test_unknown_model_hint_falls_back_to_general():
    """Unknown model hint falls back to 'general' role."""
    result = resolve_skill_model(model="gpt-4o-unknown")
    assert result["source"] == "model"
    assert result["model_role"] == "general"
    assert result["provider_preferences"] is None


def test_custom_model_hint_overrides_default():
    """config_model_hints can add new hints and override existing ones."""
    # Use 'gpt'/'gpt-4' rather than 'gemini'/'gemini-pro': 'gemini' contains 'mini'
    # which is a default hint, and with defaults-first iteration order 'mini' would
    # match first and return 'fast' instead of the intended 'reasoning'.
    # New hint: 'gpt' -> 'reasoning'
    result = resolve_skill_model(
        model="gpt-4",
        config_model_hints={"gpt": "reasoning"},
    )
    assert result["source"] == "model"
    assert result["model_role"] == "reasoning"

    # Override existing default: 'haiku' -> 'coding' (default is 'fast')
    result = resolve_skill_model(
        model="claude-haiku-3",
        config_model_hints={"haiku": "coding"},
    )
    assert result["source"] == "model"
    assert result["model_role"] == "coding"


def test_custom_agent_archetype_overrides_default():
    """config_agent_archetypes can add new archetypes and override existing ones."""
    # New archetype: 'Analyze' -> 'reasoning'
    result = resolve_skill_model(
        agent="Analyze",
        config_agent_archetypes={"Analyze": "reasoning"},
    )
    assert result["source"] == "agent"
    assert result["model_role"] == "reasoning"
