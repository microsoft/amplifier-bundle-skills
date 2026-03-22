"""
Skill discovery and metadata parsing.
Shared utilities for finding and parsing SKILL.md files.
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Pattern for valid skill names per Agent Skills Spec
VALID_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _find_repo_root(path: Path) -> Path | None:
    """Walk up from path to find the git repository root."""
    current = path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


@dataclass
class SkillMetadata:
    """Metadata from a SKILL.md file's YAML frontmatter.

    Follows the Agent Skills Specification:
    https://agentskills.io/specification

    Required fields: name, description
    Optional fields: version, license, compatibility, allowed-tools, metadata, hooks, auto-load

    Hooks field follows Agent Skills hooks format for skill-scoped hooks that
    activate when the skill is loaded and deactivate when unloaded.
    """

    name: str
    description: str
    path: Path
    source: str  # Which directory/source this came from
    version: str | None = None
    license: str | None = None
    compatibility: str | None = (
        None  # Environment requirements (max 500 chars per spec)
    )
    allowed_tools: list[str] | None = None
    metadata: dict[str, Any] | None = None
    hooks: dict[str, Any] | None = None  # Agent Skills-compatible hooks config
    trusted: bool = True  # False for remote-source skills; blocks shell execution
    # Enhanced frontmatter fields (Amplifier extended format)
    context: str | None = None  # Execution context (e.g., 'fork')
    agent: str | None = None  # Agent to use (e.g., 'foundation:explorer')
    disable_model_invocation: bool = False  # Prevent LLM calls when loading
    user_invocable: bool = False  # Whether users can invoke this skill directly
    model: str | None = None  # Preferred model for this skill
    model_role: str | list[str] | None = None  # Model role or fallback chain
    provider_preferences: list[dict] | None = None  # Provider/model preferences
    auto_load: bool = False  # Emit skill:loaded at mount time (for hook-bearing skills)


def parse_skill_frontmatter(skill_path: Path) -> dict[str, Any] | None:
    """
    Parse YAML frontmatter from a SKILL.md file.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Dictionary of frontmatter fields, or None if invalid
    """
    try:
        content = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read {skill_path}: {e}")
        return None

    # Check for YAML frontmatter (--- ... ---)
    if not content.startswith("---"):
        logger.debug(f"No frontmatter in {skill_path}")
        return None

    # Split on --- markers
    parts = content.split("---", 2)
    if len(parts) < 3:
        logger.debug(f"Incomplete frontmatter in {skill_path}")
        return None

    # Parse YAML
    try:
        frontmatter = yaml.safe_load(parts[1])
        return frontmatter if isinstance(frontmatter, dict) else None
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {skill_path}: {e}")
        return None


def extract_skill_body(skill_path: Path) -> str | None:
    """
    Extract the markdown body from a SKILL.md file (without frontmatter).

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Markdown content after frontmatter, or None if invalid
    """
    try:
        content = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read {skill_path}: {e}")
        return None

    # Extract body after frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()

    # No frontmatter, return entire content
    return content.strip()


def discover_skills(skills_dir: Path) -> dict[str, SkillMetadata]:
    """
    Discover all skills in a directory.

    Args:
        skills_dir: Directory containing skill subdirectories

    Returns:
        Dictionary mapping skill names to metadata
    """
    skills = {}

    if not skills_dir.exists():
        logger.debug(f"Skills directory does not exist: {skills_dir}")
        return skills

    if not skills_dir.is_dir():
        logger.warning(f"Skills path is not a directory: {skills_dir}")
        return skills

    # Scan for SKILL.md files (recursive).
    # Use os.walk with followlinks=True to reliably traverse symlinked
    # subdirectories on all supported Python versions (3.12+).
    # Boundary checking prevents symlink traversal outside the allowed boundary.
    # When a git repo is detected, symlinks may resolve anywhere within the repo
    # root (enabling the cross-harness pattern: .amplifier/skills/my-skill ->
    # ../../skills/my-skill).  Outside a git repo, the strict skills_dir boundary
    # is enforced to prevent accidental traversal (e.g. a symlink evil -> /etc).
    base_resolved = skills_dir.resolve()
    repo_root = _find_repo_root(skills_dir)
    boundary = repo_root if repo_root is not None else base_resolved

    skill_files = []
    for root, _dirs, files in os.walk(skills_dir, followlinks=True):
        root_resolved = Path(root).resolve()
        if not root_resolved.is_relative_to(boundary):
            logger.warning(
                f"Skipping symlink that escapes "
                f"{'repository' if repo_root else 'skill directory'} boundary: "
                f"{root} (resolves to {root_resolved}, outside {boundary})"
            )
            continue
        if "SKILL.md" in files:
            skill_files.append(Path(root) / "SKILL.md")
    for skill_file in skill_files:
        try:
            # Parse frontmatter
            frontmatter = parse_skill_frontmatter(skill_file)
            if not frontmatter:
                logger.debug(f"Skipping {skill_file} - no valid frontmatter")
                continue

            # Extract required fields
            name = frontmatter.get("name")
            description = frontmatter.get("description")

            if not name or not description:
                logger.warning(
                    f"Skipping {skill_file} - missing required fields (name, description)"
                )
                continue

            # Validate field lengths (per Agent Skills Spec)
            if len(name) > 64:
                logger.warning(
                    f"Skill '{name}' at {skill_file} exceeds 64 character name limit "
                    f"({len(name)} chars). Continuing with discovery."
                )
            if len(description) > 1024:
                logger.warning(
                    f"Skill '{name}' at {skill_file} exceeds 1024 character description limit "
                    f"({len(description)} chars). Continuing with discovery."
                )

            # Validate name format (per Agent Skills Spec)
            if not VALID_NAME_PATTERN.match(name):
                logger.warning(
                    f"Skill '{name}' at {skill_file} has invalid name format. "
                    f"Names should be lowercase alphanumeric with hyphens (e.g., 'my-skill'). "
                    f"Continuing with discovery."
                )

            # Validate directory name matches skill name (per Agent Skills Spec)
            parent_dir_name = skill_file.parent.name
            if name != parent_dir_name:
                logger.warning(
                    f"Skill '{name}' at {skill_file} has mismatched directory name. "
                    f"Expected directory '{name}', but found '{parent_dir_name}'. "
                    f"Per Agent Skills Spec, the skill name should match the directory name. "
                    f"Continuing with discovery."
                )

            # Parse allowed-tools (note: YAML uses hyphen, Python uses underscore)
            # Can be list or space-delimited string per Agent Skills Spec
            allowed_tools_raw = frontmatter.get("allowed-tools")
            allowed_tools = None
            if allowed_tools_raw:
                if isinstance(allowed_tools_raw, list):
                    allowed_tools = [str(tool) for tool in allowed_tools_raw]
                elif isinstance(allowed_tools_raw, str):
                    # Support space-delimited string format per spec
                    allowed_tools = [tool.strip() for tool in allowed_tools_raw.split()]
                else:
                    logger.warning(
                        f"Invalid allowed-tools format in {skill_file}: {type(allowed_tools_raw)}"
                    )

            # Parse compatibility field (optional, max 500 chars per spec)
            compatibility = frontmatter.get("compatibility")
            if compatibility and len(compatibility) > 500:
                logger.warning(
                    f"Skill '{name}' at {skill_file} exceeds 500 character compatibility limit "
                    f"({len(compatibility)} chars). Continuing with discovery."
                )

            # Parse hooks field (Agent Skills-compatible format)
            # Skills can embed hooks that activate when the skill is loaded
            hooks_config = frontmatter.get("hooks")
            if hooks_config and not isinstance(hooks_config, dict):
                logger.warning(
                    f"Invalid hooks format in {skill_file}: expected dict, got {type(hooks_config)}"
                )
                hooks_config = None

            # Parse enhanced frontmatter fields (supports hyphen-case and snake_case)
            # context: only 'fork' is currently supported
            context_val = frontmatter.get("context")
            if context_val is not None:
                if context_val != "fork":
                    logger.warning(
                        f"Invalid context value '{context_val}' in {skill_file}. "
                        f"Only 'fork' is supported. Ignoring context field."
                    )
                    context_val = None

            agent_val = frontmatter.get("agent")

            # disable-model-invocation supports both hyphen and snake_case
            disable_model_invocation_val = frontmatter.get(
                "disable-model-invocation",
                frontmatter.get("disable_model_invocation", False),
            )
            if not isinstance(disable_model_invocation_val, bool):
                disable_model_invocation_val = bool(disable_model_invocation_val)

            # user-invocable supports both hyphen and snake_case
            user_invocable_val = frontmatter.get(
                "user-invocable",
                frontmatter.get("user_invocable", False),
            )
            if not isinstance(user_invocable_val, bool):
                user_invocable_val = bool(user_invocable_val)

            # auto-load supports both hyphen and snake_case
            # When True, skill:loaded is emitted at mount time (for hook-bearing skills)
            auto_load_val = frontmatter.get(
                "auto-load",
                frontmatter.get("auto_load", False),
            )
            if not isinstance(auto_load_val, bool):
                auto_load_val = bool(auto_load_val)

            model_val = frontmatter.get("model")

            # model_role supports both string and list (fallback chain)
            model_role_val = frontmatter.get("model_role") or frontmatter.get(
                "model-role"
            )
            if model_role_val is not None:
                if not isinstance(model_role_val, (str, list)):
                    logger.warning(
                        f"Invalid model_role format in {skill_file}: "
                        f"expected str or list, got {type(model_role_val)}. Ignoring."
                    )
                    model_role_val = None

            # provider_preferences must be a list of dicts
            provider_preferences_val = frontmatter.get(
                "provider_preferences"
            ) or frontmatter.get("provider-preferences")
            if provider_preferences_val is not None:
                if not isinstance(provider_preferences_val, list):
                    logger.warning(
                        f"Invalid provider_preferences format in {skill_file}: "
                        f"expected list, got {type(provider_preferences_val)}. Ignoring."
                    )
                    provider_preferences_val = None
                else:
                    # Validate each entry is a dict
                    valid_prefs = []
                    for pref in provider_preferences_val:
                        if isinstance(pref, dict):
                            valid_prefs.append(pref)
                        else:
                            logger.warning(
                                f"Invalid provider_preferences entry in {skill_file}: "
                                f"expected dict, got {type(pref)}. Skipping entry."
                            )
                    provider_preferences_val = valid_prefs if valid_prefs else None

            # Create metadata
            metadata = SkillMetadata(
                name=name,
                description=description,
                path=skill_file,
                source=str(skills_dir),
                version=frontmatter.get("version"),
                license=frontmatter.get("license"),
                compatibility=compatibility,
                allowed_tools=allowed_tools,
                metadata=frontmatter.get("metadata"),
                hooks=hooks_config,
                context=context_val,
                agent=agent_val,
                disable_model_invocation=disable_model_invocation_val,
                user_invocable=user_invocable_val,
                auto_load=auto_load_val,
                model=model_val,
                model_role=model_role_val,
                provider_preferences=provider_preferences_val,
            )

            skills[name] = metadata
            logger.debug(f"Discovered skill: {name} at {skill_file}")

        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Error processing {skill_file}: {e}")
            continue

    logger.info(f"Discovered {len(skills)} skills in {skills_dir}")
    return skills


def discover_skills_multi_source(
    skills_dirs: list[Path] | list[str],
) -> dict[str, SkillMetadata]:
    """
    Discover skills from multiple directories with priority.

    First-match-wins: If same skill name appears in multiple directories,
    the one from the earlier directory (higher priority) is used.

    Args:
        skills_dirs: List of directories to search, in priority order (highest first)

    Returns:
        Dictionary mapping skill names to metadata
    """
    all_skills: dict[str, SkillMetadata] = {}
    sources_checked = []

    for skills_dir in skills_dirs:
        dir_path = Path(skills_dir).expanduser().resolve()
        sources_checked.append(str(dir_path))

        if not dir_path.exists():
            logger.debug(f"Skills directory does not exist: {dir_path}")
            continue

        # Discover from this directory
        dir_skills = discover_skills(dir_path)

        # Merge with priority (first-match-wins)
        for name, metadata in dir_skills.items():
            if name not in all_skills:
                all_skills[name] = metadata
                logger.debug(f"Added skill '{name}' from {dir_path}")
            else:
                logger.debug(
                    f"Skipping duplicate skill '{name}' from {dir_path} (already have from {all_skills[name].source})"
                )

    logger.info(
        f"Discovered {len(all_skills)} skills from {len(sources_checked)} sources"
    )
    return all_skills


def get_default_skills_dirs() -> list[Path]:
    """
    Get default skills directory search paths with priority.

    Priority order:
    1. AMPLIFIER_SKILLS_DIR environment variable
    2. .amplifier/skills/ (workspace)
    3. ~/.amplifier/skills/ (user)

    Returns:
        List of paths to check, in priority order
    """
    dirs = []

    # 1. Environment variable override (highest priority)
    if env_dir := os.getenv("AMPLIFIER_SKILLS_DIR"):
        dirs.append(Path(env_dir))

    # 2. Workspace directory
    dirs.append(Path(".amplifier/skills"))

    # 3. User directory
    dirs.append(Path("~/.amplifier/skills").expanduser())

    return dirs
