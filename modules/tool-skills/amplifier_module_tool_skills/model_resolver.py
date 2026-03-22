"""Model resolver — 5-level precedence chain for model selection.

Resolves which model / provider to use when loading a skill, honouring an
explicit precedence order so that callers only need to supply whatever context
they have and the resolver picks the highest-priority signal automatically.

Precedence (highest wins):
1. provider_preferences — explicit provider chain
2. model_role           — Amplifier-native semantic role
3. model                — cross-platform model hint (haiku, sonnet, opus, …)
4. agent                — agent archetype (Explore, Plan, Code, Review, …)
5. Nothing              — inherit from parent context
"""

from __future__ import annotations

from typing import Any

# Cross-platform model hints → Amplifier semantic roles
MODEL_HINT_TO_ROLE: dict[str, str] = {
    "haiku": "fast",
    "sonnet": "coding",
    "opus": "reasoning",
    "flash": "fast",
    "mini": "fast",
    "turbo": "fast",
}

# Agent archetypes → Amplifier semantic roles
AGENT_ARCHETYPE_TO_ROLE: dict[str, str] = {
    "Explore": "fast",
    "Plan": "reasoning",
    "Code": "coding",
    "Review": "critique",
}


def resolve_skill_model(
    provider_preferences: list[dict[str, Any]] | None = None,
    model_role: str | list[str] | None = None,
    model: str | None = None,
    agent: str | None = None,
    config_model_hints: dict[str, str] | None = None,
    config_agent_archetypes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve the model selection using a 5-level precedence chain.

    Args:
        provider_preferences: Explicit provider chain (highest precedence).
            Passed through unchanged when present.
        model_role: Amplifier-native semantic role string, or a list of roles
            (first element is used).
        model: Cross-platform model hint (e.g. "haiku", "sonnet", "opus").
            Translated to a semantic role via MODEL_HINT_TO_ROLE merged with
            config_model_hints overrides.  Unknown hints fall back to "general".
        agent: Agent archetype name (e.g. "Explore", "Code").  Translated to a
            semantic role via AGENT_ARCHETYPE_TO_ROLE merged with
            config_agent_archetypes overrides.  Unknown archetypes fall back to
            "general".
        config_model_hints: Optional dict of model hint -> role overrides.
            Merged on top of MODEL_HINT_TO_ROLE (overrides win).
        config_agent_archetypes: Optional dict of archetype -> role overrides.
            Merged on top of AGENT_ARCHETYPE_TO_ROLE (overrides win).

    Returns:
        Dict with keys:
            source              — which level supplied the resolution
            model_role          — resolved semantic role (or None)
            provider_preferences — resolved provider chain (or None)
    """
    # Build effective lookup tables: config overrides win via spread.
    # Defaults are inserted first; config keys are appended at the end so they
    # win on exact-key overrides (same key → config value replaces default).
    # Note: the substring-match loop below iterates in insertion order, so
    # config-only hints (new keys not in defaults) are checked *after* all
    # default hints.  If a model name matches both a default hint and a new
    # config-only hint, the default hint wins.  Use config to *override* an
    # existing default key (e.g. "haiku" → "coding") rather than adding a new
    # hint whose substring also appears in a default key.
    effective_hints = {**MODEL_HINT_TO_ROLE, **(config_model_hints or {})}
    effective_archetypes = {
        **AGENT_ARCHETYPE_TO_ROLE,
        **(config_agent_archetypes or {}),
    }

    # Level 1 — provider_preferences (highest)
    if provider_preferences is not None:
        return {
            "source": "provider_preferences",
            "model_role": None,
            "provider_preferences": provider_preferences,
        }

    # Level 2 — model_role
    if model_role is not None:
        resolved_role = (
            model_role[0] if isinstance(model_role, list) and model_role else model_role
        )
        return {
            "source": "model_role",
            "model_role": resolved_role,
            "provider_preferences": None,
        }

    # Level 3 — model hint
    if model is not None:
        # Normalise: strip version suffixes, lower-case, then match substrings
        model_lower = model.lower()
        resolved_role = "general"
        for hint, role in effective_hints.items():
            if hint in model_lower:
                resolved_role = role
                break
        return {
            "source": "model",
            "model_role": resolved_role,
            "provider_preferences": None,
        }

    # Level 4 — agent archetype
    if agent is not None:
        resolved_role = effective_archetypes.get(agent, "general")
        return {
            "source": "agent",
            "model_role": resolved_role,
            "provider_preferences": None,
        }

    # Level 5 — inherit
    return {
        "source": "inherit",
        "model_role": None,
        "provider_preferences": None,
    }
