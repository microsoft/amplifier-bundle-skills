"""Amplifier tool for loading domain knowledge from skills.

Provides explicit skill discovery and loading capabilities.
Supports local directories and git URL sources for skills.
"""

from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from amplifier_core import ToolResult

try:
    from amplifier_foundation import RUNTIME_SKILL_OVERLAY_CAPABILITY
except ImportError:  # foundation not installed in all deployment configs
    RUNTIME_SKILL_OVERLAY_CAPABILITY = "runtime_skill_overlay"  # type: ignore[assignment]

from amplifier_module_tool_skills import context_inheritance as ctx_inherit
from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import discover_skills_multi_source
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import get_default_skills_dirs
from amplifier_module_tool_skills.discovery import parse_skill_frontmatter
from amplifier_module_tool_skills.model_resolver import resolve_skill_model
from amplifier_module_tool_skills.preprocessing import preprocess
from amplifier_module_tool_skills.sources import is_remote_source
from amplifier_module_tool_skills.sources import resolve_skill_source
from amplifier_module_tool_skills.sources import resolve_skill_sources

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


def _detect_fork_session(coordinator: "ModuleCoordinator") -> bool:
    """Detect whether this session is a forked-skill child session.

    Two paths, reflecting the two contexts the question can be asked in:

    * In-session (capability): set on this coordinator by a previous mount,
      a sibling module, or a test harness.
    * Cross-session (config): set by the parent's ``_execute_fork`` into
      ``session.metadata``, which ``spawn_sub_session`` copies verbatim into
      the child's config. Capabilities do NOT cross the spawn boundary — each
      child coordinator starts fresh by design — so metadata is the only
      propagation mechanism parent → child.

    ``session.metadata`` is expected to be a dict but user-supplied config can
    put anything there, so a cheap ``isinstance`` guard keeps this robust.
    """
    if coordinator.get_capability("skills.fork_context"):
        return True
    metadata = coordinator.config.get("session", {}).get("metadata", {})
    return isinstance(metadata, dict) and bool(
        metadata.get("is_forked_skill_session", False)
    )


async def _resolve_skill_sources(
    config: dict[str, Any], coordinator: "ModuleCoordinator"
) -> list[Path]:
    """Resolve skill sources from config, handling both local paths and git URLs.

    Priority order:
    1. 'skills' config (new format - supports git URLs)
    2. 'skills_dirs' config (legacy - local paths only)
    3. 'skills_dir' config (legacy - single local path)
    4. Global settings via coordinator.config
    5. Default directories

    Args:
        config: Tool configuration dict.
        coordinator: Module coordinator for accessing global config.

    Returns:
        List of resolved local directory paths.
    """
    sources: list[str] = []

    # 1. Check 'skills' config (new format - supports git URLs)
    if "skills" in config:
        skills_config = config["skills"]
        if isinstance(skills_config, str):
            sources = [skills_config]
        elif isinstance(skills_config, list):
            sources = list(skills_config)

    # 2. Check legacy 'skills_dirs' config
    elif "skills_dirs" in config:
        dirs = config["skills_dirs"]
        if isinstance(dirs, str):
            sources = [dirs]
        else:
            sources = list(dirs)

    # 3. Check legacy 'skills_dir' config
    elif "skills_dir" in config:
        sources = [config["skills_dir"]]

    # 4. Check global/project settings via coordinator
    elif coordinator:
        global_skills = coordinator.config.get("skills", {})
        if isinstance(global_skills, list):
            # Direct list format: skills: [url1, url2, ...]
            sources = list(global_skills)
        elif isinstance(global_skills, dict):
            # Dict format: skills: {sources: [...]} or skills: {dirs: [...]}
            if "sources" in global_skills:
                src = global_skills["sources"]
                sources = [src] if isinstance(src, str) else list(src)
            elif "dirs" in global_skills:
                dirs = global_skills["dirs"]
                sources = [dirs] if isinstance(dirs, str) else list(dirs)

    # 5. Fall back to defaults if no sources configured
    if not sources:
        logger.debug("No skill sources configured, using defaults")
        return get_default_skills_dirs()

    # Check if any sources are remote (need async resolution)
    has_remote = any(is_remote_source(s) for s in sources)

    if has_remote:
        # Resolve all sources (handles both local and remote)
        logger.info(f"Resolving {len(sources)} skill sources (includes remote)")
        return await resolve_skill_sources(sources)
    else:
        # All local - just expand paths
        resolved = []
        for source in sources:
            path = Path(source).expanduser().resolve()
            if path.exists():
                resolved.append(path)
            else:
                logger.debug(f"Local skill source does not exist: {path}")
        return resolved if resolved else get_default_skills_dirs()


async def mount(
    coordinator: "ModuleCoordinator", config: dict[str, Any] | None = None
) -> Callable[[], Coroutine[Any, Any, None]] | None:
    """Mount the skills tool.

    Args:
        coordinator: Module coordinator
        config: Tool configuration

    Configuration options:
        skills: List of skill sources (local paths or git URLs)
            Example: ["~/.amplifier/skills", "git+https://github.com/org/skills@main"]
        skills_dirs: Legacy alias for skills (local paths only)
        skills_dir: Legacy single directory option

    Returns:
        Async cleanup function that emits skill:unloaded events
    """
    config = config or {}
    logger.info(f"Mounting SkillsTool with config: {config}")

    # Declare observable events for hooks-logging auto-discovery
    obs_events = coordinator.get_capability("observability.events") or []
    obs_events.extend(
        [
            "skills:discovered",  # When skills are found during mount
            "skill:loaded",  # When skill loaded successfully (includes hooks config)
            "skill:unloaded",  # When skill is unloaded (for hook cleanup)
        ]
    )
    coordinator.register_capability("observability.events", obs_events)

    # Resolve skill sources (handles both local paths and git URLs)
    resolved_dirs = await _resolve_skill_sources(config, coordinator)

    tool = SkillsTool(config, coordinator, resolved_dirs)

    # Detect whether this session is a forked-skill child session. See the
    # _detect_fork_session helper docstring for why the marker lives in
    # session.metadata rather than in orchestrator_config or a capability.
    _is_forked_session = _detect_fork_session(coordinator)
    tool._is_forked_session = _is_forked_session
    if _is_forked_session:
        # Register as a capability so in-session observers/hooks can detect it cleanly.
        coordinator.register_capability("skills.fork_context", True)
        logger.debug(
            "SkillsTool: detected forked skill session — fork-context skills will be blocked"
        )

    await coordinator.mount("tools", tool, name=tool.name)
    logger.info(
        f"Mounted SkillsTool with {len(tool.skills)} skills from {len(tool.skills_dirs)} sources"
    )

    # Mount skills visibility hook if enabled
    visibility_config = config.get("visibility", {})
    unregister_visibility = None
    if visibility_config.get("enabled", True):  # Default: enabled
        from amplifier_module_tool_skills.hooks import SkillsVisibilityHook

        hook = SkillsVisibilityHook(
            tool.skills,
            visibility_config,
            is_forked_session=_is_forked_session,
            coordinator=coordinator,
            tool=tool,
        )

        # Register hook on provider:request event; capture unregister callable
        unregister_visibility = coordinator.hooks.register(
            event="provider:request",
            handler=hook.on_provider_request,
            priority=hook.priority,
            name="skills-visibility",
        )

        logger.info(f"Mounted skills visibility hook with {len(tool.skills)} skills")

    # Register SkillsDiscovery as a kernel capability (before discovery event emission)
    coordinator.register_capability("skills_discovery", SkillsDiscovery(tool.skills))
    logger.debug("Registered SkillsDiscovery via register_capability")

    # Emit discovery event
    await coordinator.hooks.emit(
        "skills:discovered",
        {
            "skill_count": len(tool.skills),
            "skill_names": list(tool.skills.keys()),
            "sources": [str(d) for d in tool.skills_dirs],
        },
    )

    # Auto-load skills that request it (e.g., skills with embedded hooks).
    # Only skills with BOTH auto_load: true AND hooks in frontmatter are auto-loaded.
    # Skills with auto_load but no hooks don't need auto-loading since their content
    # would just be injected into context, which is the agent's job via load_skill().
    for name, metadata in tool.skills.items():
        if getattr(metadata, "auto_load", False) and metadata.hooks:
            body = extract_skill_body(metadata.path)
            if body:
                tool.loaded_skills.add(name)
                await coordinator.hooks.emit(
                    "skill:loaded",
                    {
                        "skill_name": name,
                        "source": metadata.source,
                        "content_length": len(body),
                        "version": metadata.version,
                        "skill_directory": str(metadata.path.parent),
                        "hooks": metadata.hooks,
                        "context": metadata.context,
                        "allowed_tools": metadata.allowed_tools,
                        "disable_model_invocation": metadata.disable_model_invocation,
                        "user_invocable": metadata.user_invocable,
                        "slash_command": name,
                        "auto_loaded": True,
                    },
                )
                logger.info(f"Auto-loaded skill '{name}' (has embedded hooks)")

    # Return cleanup function that emits skill:unloaded for each loaded skill
    async def cleanup() -> None:
        """Cleanup function that emits skill:unloaded events."""
        for skill_name in tool.loaded_skills:
            metadata = tool.skills.get(skill_name)
            if metadata:
                await coordinator.hooks.emit(
                    "skill:unloaded",
                    {
                        "skill_name": skill_name,
                        "source": metadata.source,
                        "hooks": metadata.hooks,
                    },
                )
                logger.debug(f"Emitted skill:unloaded for {skill_name}")
        tool.loaded_skills.clear()

        # Unregister the visibility hook to prevent it persisting after cleanup
        if unregister_visibility is not None:
            try:
                unregister_visibility()
            except Exception:
                logger.warning(
                    "Failed to unregister skills-visibility hook during cleanup"
                )

    return cleanup


class SkillsDiscovery:
    """Provides discovery interface for skills.

    Wraps the skills dict and provides list, find, and shortcut methods.
    Registered as a capability via coordinator.register_capability().
    """

    def __init__(self, skills: dict[str, SkillMetadata]):
        """Initialize with skills dict.

        Args:
            skills: Dict mapping skill names to SkillMetadata.
        """
        self._skills = skills

    def list_skills(self) -> list[tuple[str, str]]:
        """Return (name, description) pairs sorted alphabetically.

        Returns:
            List of (name, description) tuples sorted by name.
        """
        return [
            (name, metadata.description)
            for name, metadata in sorted(self._skills.items())
        ]

    def find(self, name: str) -> SkillMetadata | None:
        """Find a skill by name.

        Args:
            name: Skill name to look up.

        Returns:
            SkillMetadata if found, None otherwise.
        """
        return self._skills.get(name)

    def get_shortcuts(self) -> dict[str, dict[str, Any]]:
        """Return dispatch entries for all user-invocable skills.

        Each user-invocable skill gets an entry under its canonical name.
        If the skill has a shortcut alias that differs from the canonical
        name, the same entry is also registered under the alias.

        Returns:
            Dict mapping slash-command names (canonical + aliases) to
            dispatch entry dicts with 'name', 'description', and 'context'.
        """
        shortcuts: dict[str, dict[str, Any]] = {}
        for name, metadata in self._skills.items():
            if not metadata.user_invocable:
                continue
            entry = {
                "name": name,
                "description": metadata.description,
                "context": metadata.context,
            }
            shortcuts[name] = entry
            if metadata.shortcut and metadata.shortcut != name:
                shortcuts[metadata.shortcut] = entry
        return shortcuts


class SkillsTool:
    """Tool for loading domain knowledge from skills."""

    name = "load_skill"
    description = """
Load domain knowledge from an available skill. Skills provide specialized knowledge, workflows, 
best practices, and standards. Use when you need domain expertise, coding guidelines, or 
architectural patterns.

Operations:

**List all skills:**
  load_skill(list=True)
  Returns a formatted list of all available skills with descriptions.

**Search for skills:**
  load_skill(search="pattern")
  Filters skills by name or description matching the search term.

**Get skill metadata:**
  load_skill(info="skill-name")
  Returns metadata (name, description, version, license, path) without loading full content.
  Use this to check details before loading or when you just need basic information.

**Load full skill content:**
  load_skill(skill_name="skill-name")
  Loads the complete skill content into context. Returns skill_directory path for accessing
  companion files referenced in the skill.

Usage Guidelines:
- Start tasks by listing or searching skills to discover relevant domain knowledge
- Use info operation to check skills before loading to conserve context
- Skills may reference companion files - use the returned skill_directory path with read_file tool
  Example: If skill returns skill_directory="/path/to/skill", you can read companion files with
  read_file(skill_directory + "/examples/code.py")
- Skills complement but don't replace documentation or web search - use for standardized workflows
  and best practices specific to the skill domain

Skill Discovery:
- Skills are discovered from configured directories (workspace, user, or custom paths)
- First-match-wins priority if same skill exists in multiple directories
- Workspace skills (.amplifier/skills/) override user skills (~/.amplifier/skills/)
"""

    def __init__(
        self,
        config: dict[str, Any],
        coordinator: "ModuleCoordinator | None" = None,
        resolved_dirs: list[Path] | None = None,
    ):
        """Initialize skills tool.

        Args:
            config: Tool configuration
            coordinator: Module coordinator for event emission (optional)
            resolved_dirs: Pre-resolved skill directories (from mount)
        """
        self.config = config
        self.coordinator = coordinator
        self.loaded_skills: set[str] = set()  # Track which skills have been loaded
        # Set to True by mount() when running inside a forked skill sub-session.
        # Prevents fork-from-fork infinite recursion.
        self._is_forked_session: bool = False

        # Use pre-resolved dirs if provided, otherwise discover from config or defaults
        if resolved_dirs is not None:
            self.skills_dirs = resolved_dirs
            self.skills = discover_skills_multi_source(resolved_dirs)
            logger.info(
                f"Discovered {len(self.skills)} skills from {len(resolved_dirs)} sources"
            )
        else:
            # Fallback for direct instantiation (testing, etc.)
            # First check for cached skills from capability registry
            if coordinator:
                cached_skills = coordinator.get_capability("skills.registry")
                cached_dirs = coordinator.get_capability("skills.directories")
                if cached_skills is not None and cached_dirs is not None:
                    self.skills = cached_skills
                    self.skills_dirs = cached_dirs
                    logger.info(
                        f"Reusing {len(self.skills)} skills from capability registry"
                    )
                    return

            # Check config for skills directories
            dirs_from_config = self._get_dirs_from_config()
            if dirs_from_config:
                self.skills_dirs = dirs_from_config
                self.skills = discover_skills_multi_source(dirs_from_config)
                logger.info(
                    f"Discovered {len(self.skills)} skills from config directories"
                )
            else:
                self.skills_dirs = get_default_skills_dirs()
                self.skills = discover_skills_multi_source(self.skills_dirs)
                logger.info(
                    f"Discovered {len(self.skills)} skills from default directories"
                )

    def _get_dirs_from_config(self) -> list[Path] | None:
        """Extract skills directories from config for direct instantiation.

        Returns:
            List of paths if found in config, None otherwise.
        """
        # Check 'skills_dirs' config
        if "skills_dirs" in self.config:
            dirs = self.config["skills_dirs"]
            if isinstance(dirs, str):
                dirs = [dirs]
            return [Path(d).expanduser().resolve() for d in dirs]

        # Check 'skills_dir' config (legacy single directory)
        if "skills_dir" in self.config:
            return [Path(self.config["skills_dir"]).expanduser().resolve()]

        return None

    @property
    def input_schema(self) -> dict:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of skill to load (e.g., 'design-patterns', 'python-standards')",
                },
                "list": {
                    "type": "boolean",
                    "description": "If true, return list of all available skills",
                },
                "search": {
                    "type": "string",
                    "description": "Search term to filter skills by name or description",
                },
                "info": {
                    "type": "string",
                    "description": "Get metadata for a specific skill without loading full content",
                },
                "source": {
                    "type": "string",
                    "description": "Register a new skill source. Accepts @namespace:path, git+https:// URLs, or local paths.",
                },
                "arguments": {
                    "type": "string",
                    "description": (
                        "User argument string for the skill, substituted into the "
                        "skill body wherever it uses $ARGUMENTS (and positional $0, $1, ...). "
                        "This is how a /command invocation's text (e.g. the target in "
                        "`/council <target>`) reaches the skill. REQUIRED to pass through for "
                        "fork skills: a forked sub-session cannot see the parent conversation, "
                        "so without this its $ARGUMENTS is empty. When the user supplies "
                        "argument text for a skill, always forward it here."
                    ),
                },
                "context_depth": {
                    "type": "string",
                    "enum": ["none", "recent", "all"],
                    "description": (
                        "FORK SKILLS ONLY. Controls HOW MUCH of the parent conversation "
                        "the forked sub-session inherits. 'none' (DEFAULT) = clean slate, "
                        "the sub-session sees only the skill body; 'recent' = the last N "
                        "turns (N set by context_turns); 'all' = the full parent history. "
                        "Ignored for non-fork (inline) skills, which already run in the "
                        "current context. Default 'none' preserves the historical fork "
                        "behavior, so omit it unless the forked skill genuinely needs "
                        "parent context."
                    ),
                },
                "context_turns": {
                    "type": "integer",
                    "description": (
                        "FORK SKILLS ONLY. Number of recent turns to inherit when "
                        "context_depth='recent' (default: 5). Ignored otherwise."
                    ),
                },
                "context_scope": {
                    "type": "string",
                    "enum": ["conversation", "agents", "full"],
                    "description": (
                        "FORK SKILLS ONLY. Controls WHICH parent content is inherited when "
                        "context_depth is not 'none'. 'conversation' (DEFAULT) = user/"
                        "assistant text only; 'agents' = + delegate/task agent results; "
                        "'full' = + all tool results (truncated). Ignored for non-fork skills."
                    ),
                },
            },
        }

    async def _resolve_source(self, source: str) -> Path | None:
        """Resolve a source string to a local directory path.

        Handles @namespace:path (via mention_resolver), git+https:// URLs
        (via sources.py), and local filesystem paths.

        Args:
            source: Source string to resolve.

        Returns:
            Resolved local Path, or None if resolution fails.
        """
        # @namespace:path — use mention resolver
        if source.startswith("@"):
            if self.coordinator:
                resolver = self.coordinator.get_capability("mention_resolver")
                if resolver:
                    return resolver.resolve(source)
            return None

        # git+https:// or https:// — use existing sources.py
        if is_remote_source(source):
            return await resolve_skill_source(source)

        # Local path
        path = Path(source).expanduser().resolve()
        return path if path.exists() else None

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        Execute skill tool operation.

        Args:
            input: Tool parameters

        Returns:
            Tool result with skill content or list
        """
        # Source registration — resolve, discover, merge
        source_str = input.get("source")
        source_summary = None
        if source_str:
            resolved_path = await self._resolve_source(source_str)
            if resolved_path is None:
                return ToolResult(
                    success=False,
                    output=f"Could not resolve source: {source_str}",
                )

            new_skills = discover_skills(resolved_path)

            # Merge with first-match-wins: existing skills take priority
            added = []
            for name, metadata in new_skills.items():
                if name not in self.skills:
                    self.skills[name] = metadata
                    added.append(name)

            source_summary = (
                f"Source '{source_str}' resolved to {resolved_path}. "
                f"Found {len(new_skills)} skill(s), {len(added)} new: {', '.join(sorted(added)) if added else 'none (all duplicates)'}."
            )

            # Emit discovery event
            if self.coordinator:
                await self.coordinator.hooks.emit(
                    "skills:discovered",
                    {
                        "skill_count": len(new_skills),
                        "skill_names": list(new_skills.keys()),
                        "sources": [str(resolved_path)],
                    },
                )

            # If no other params, return the summary
            has_other_params = any(
                input.get(k) for k in ("skill_name", "list", "search", "info")
            )
            if not has_other_params:
                return ToolResult(success=True, output=source_summary)

        # List mode
        if input.get("list"):
            return self._list_skills()

        # Search mode
        if search_term := input.get("search"):
            return self._search_skills(search_term)

        # Info mode
        if skill_name := input.get("info"):
            return self._get_skill_info(skill_name)

        # Load mode
        skill_name = input.get("skill_name")
        if not skill_name:
            return ToolResult(
                success=False,
                error={
                    "message": "Must provide skill_name, list=true, search='term', or info='name'"
                },
            )

        # User arguments for $ARGUMENTS / positional substitution. Critical for
        # fork skills: a fork sub-session cannot see the parent conversation, so
        # this is the only channel through which a /command's argument text
        # (e.g. the target in `/council <target>`) reaches the forked body.
        arguments = input.get("arguments") or None

        # Parent-context inheritance (fork skills only). Defaults to a clean
        # slate ("none") so non-fork skills and unaware callers are unaffected.
        context_depth = input.get("context_depth", ctx_inherit.DEFAULT_DEPTH)
        context_scope = input.get("context_scope", ctx_inherit.DEFAULT_SCOPE)
        context_turns = input.get("context_turns", ctx_inherit.DEFAULT_TURNS)

        return await self._load_skill(
            skill_name,
            arguments=arguments,
            context_depth=context_depth,
            context_scope=context_scope,
            context_turns=context_turns,
        )

    def get_effective_skills(self) -> dict[str, SkillMetadata]:
        """Return the merged static + runtime-overlay skill catalog.

        Local (mount-time discovered) skills shadow overlay skills
        (first-match-wins). Safe to call any time — overlay resolution
        happens at call time, so the returned dict reflects the
        coordinator's current `runtime_skill_overlay` capability state.

        All entry points (load, info, list, search, visibility hook)
        should resolve through this method so contributed skills are
        consistently discoverable while the contributing mode is active.
        """
        return {**self.skills, **self._get_overlay_skill_metadata()}

    def _get_overlay_skill_metadata(self) -> dict[str, SkillMetadata]:
        """Resolve runtime-overlay skills into searchable metadata.

        Reads the `runtime_skill_overlay` coordinator capability — a producer-
        neutral contract. Any bundle that wants to overlay additional skills at
        runtime writes to it. tool-skills doesn't need to know who's writing.

        Per-URI failures are logged at DEBUG; one bad URI never blocks the
        others. Local skills shadow overlay skills (first-match-wins). Among
        overlay URIs, first match also wins.

        Issue #233: contributes.skills from active modes propagate via this
        capability; propagation to sub-sessions happens in spawn_sub_session.
        """
        if not self.coordinator:
            return {}
        uris = self.coordinator.get_capability(RUNTIME_SKILL_OVERLAY_CAPABILITY) or []
        if not uris:
            return {}
        resolver = self.coordinator.get_capability("mention_resolver")
        if resolver is None:
            return {}
        overlay: dict[str, SkillMetadata] = {}
        for uri in uris:
            try:
                resolved = resolver.resolve(uri)
                if resolved is None:
                    continue
                resolved_path = Path(resolved)
                skill_file = resolved_path / "SKILL.md"
                if not skill_file.exists():
                    continue
                fm = parse_skill_frontmatter(skill_file)
                if not fm:
                    continue
                name, description = fm.get("name"), fm.get("description")
                if not name or not description:
                    continue
                # Local skills shadow overlay; first overlay wins on conflict.
                if name in self.skills or name in overlay:
                    continue
                overlay[name] = SkillMetadata(
                    name=name,
                    description=description,
                    path=skill_file,
                    source=str(resolved_path),
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to resolve overlay skill URI %r: %s", uri, exc)
        return overlay

    def _list_skills(self) -> ToolResult:
        """List all available skills (local + runtime overlay)."""
        effective_skills = self.get_effective_skills()
        if not effective_skills:
            sources = ", ".join(str(d) for d in self.skills_dirs)
            return ToolResult(
                success=True, output={"message": f"No skills found in {sources}"}
            )

        skills_list = []
        for name, metadata in sorted(effective_skills.items()):
            skills_list.append({"name": name, "description": metadata.description})

        lines = ["Available Skills:", ""]
        for skill in skills_list:
            lines.append(f"**{skill['name']}**: {skill['description']}")

        return ToolResult(
            success=True, output={"message": "\n".join(lines), "skills": skills_list}
        )

    def _search_skills(self, search_term: str) -> ToolResult:
        """Search skills by name or description (across local + overlay)."""
        effective_skills = self.get_effective_skills()
        matches = {}
        for name, metadata in effective_skills.items():
            if (
                search_term.lower() in name.lower()
                or search_term.lower() in metadata.description.lower()
            ):
                matches[name] = metadata

        if not matches:
            return ToolResult(
                success=True, output={"message": f"No skills matching '{search_term}'"}
            )

        lines = [f"Skills matching '{search_term}':", ""]
        results = []
        for name, metadata in sorted(matches.items()):
            lines.append(f"**{name}**: {metadata.description}")
            results.append({"name": name, "description": metadata.description})

        return ToolResult(
            success=True, output={"message": "\n".join(lines), "matches": results}
        )

    def _get_skill_info(self, skill_name: str) -> ToolResult:
        """Get metadata for a skill without loading full content.

        Consults both local and runtime-overlay skills via
        get_effective_skills(); contributed skills from active modes
        are discoverable here.
        """
        effective_skills = self.get_effective_skills()
        if skill_name not in effective_skills:
            available = ", ".join(sorted(effective_skills.keys()))
            return ToolResult(
                success=False,
                error={
                    "message": f"Skill '{skill_name}' not found. Available: {available}"
                },
            )

        metadata = effective_skills[skill_name]
        info = {
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "license": metadata.license,
            "compatibility": metadata.compatibility,
            "allowed_tools": metadata.allowed_tools,
            "path": str(metadata.path),
        }

        if metadata.metadata:
            info["metadata"] = metadata.metadata

        return ToolResult(success=True, output=info)

    async def _load_skill(
        self,
        skill_name: str,
        arguments: str | None = None,
        context_depth: str = ctx_inherit.DEFAULT_DEPTH,
        context_scope: str = ctx_inherit.DEFAULT_SCOPE,
        context_turns: int = ctx_inherit.DEFAULT_TURNS,
    ) -> ToolResult:
        """Load full skill content.

        Consults both local and runtime-overlay skills via
        get_effective_skills(); contributed skills from active modes
        are loadable here.

        ``arguments`` is the user's argument string ($ARGUMENTS / positional
        substitution). It is applied for both inline and fork skills. For fork
        skills it is the ONLY channel by which a /command's argument text reaches
        the forked body, since the fork cannot see the parent conversation.

        The context_* parameters only take effect for fork skills (see
        _execute_fork); inline skills ignore them because they already load
        into the parent's live context.
        """
        effective_skills = self.get_effective_skills()
        if skill_name not in effective_skills:
            available = ", ".join(sorted(effective_skills.keys()))
            return ToolResult(
                success=False,
                error={
                    "message": f"Skill '{skill_name}' not found. Available: {available}"
                },
            )

        metadata = effective_skills[skill_name]
        body = extract_skill_body(metadata.path)

        if not body:
            return ToolResult(
                success=False,
                error={"message": f"Failed to load content from {metadata.path}"},
            )

        if metadata.context != "fork":
            body = await preprocess(
                body,
                skill_dir=metadata.path.parent,
                arguments=arguments,
                execute_shell=False,
            )

        logger.info(f"Loaded skill: {skill_name}")
        self.loaded_skills.add(skill_name)  # Track for cleanup

        # Guard: prevent fork-from-fork infinite recursion.
        # Forked skill sub-sessions may only load inline (non-fork) skills.
        if metadata.context == "fork" and self._is_forked_session:
            return ToolResult(
                success=False,
                error={
                    "message": (
                        "Forked skills cannot invoke other forked skills. "
                        "This prevents infinite recursion. You can still use "
                        "load_skill() to load non-forked (inline) skills."
                    )
                },
            )

        # Emit skill loaded event (hooks-shell module listens for this to activate skill-scoped hooks)
        if self.coordinator:
            await self.coordinator.hooks.emit(
                "skill:loaded",
                {
                    "skill_name": skill_name,
                    "source": metadata.source,
                    "content_length": len(body),
                    "version": metadata.version,
                    "skill_directory": str(metadata.path.parent),
                    "hooks": metadata.hooks,  # Agent Skills-compatible hooks config (or None)
                    # Enriched fields for hooks-shell skill-scoped hook activation
                    "context": metadata.context,
                    "allowed_tools": metadata.allowed_tools,
                    "disable_model_invocation": metadata.disable_model_invocation,
                    "user_invocable": metadata.user_invocable,
                    "slash_command": metadata.name,
                },
            )

        # Fork detection: check if this skill should be executed via delegate
        if metadata.context == "fork" and self.coordinator:
            spawn_fn = self.coordinator.get_capability("session.spawn")
            if spawn_fn is not None:
                return await self._execute_fork(
                    skill_name,
                    metadata,
                    body,
                    arguments=arguments,
                    context_depth=context_depth,
                    context_scope=context_scope,
                    context_turns=context_turns,
                )
            else:
                logger.warning(
                    f"Fork skill '{skill_name}' loaded inline (session.spawn not available)"
                )

        return ToolResult(
            success=True,
            output={
                "content": f"# {skill_name}\n\n{body}",
                "skill_name": skill_name,
                "skill_directory": str(
                    metadata.path.parent
                ),  # Actual skill folder for companion files
                "loaded_from": metadata.source,  # Source directory for context
            },
        )

    async def _get_parent_messages(self) -> list[dict[str, Any]] | None:
        """Fetch the parent session's full message history, or None if unavailable.

        Mirrors the delegate tool: reads the mounted context manager and returns
        its messages. Returns None (no inheritance) when context is unavailable
        or errors — a legitimate "clean slate" state, not a masked failure.
        """
        if not self.coordinator:
            return None
        parent_context = self.coordinator.get("context")
        if not parent_context or not hasattr(parent_context, "get_messages"):
            logger.debug("No parent context available for fork inheritance")
            return None
        try:
            messages = await parent_context.get_messages()
            return messages if messages else None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to get parent messages for fork: {e}")
            return None

    async def _execute_fork(
        self,
        skill_name: str,
        metadata: Any,
        body: str,
        arguments: str | None = None,
        context_depth: str = ctx_inherit.DEFAULT_DEPTH,
        context_scope: str = ctx_inherit.DEFAULT_SCOPE,
        context_turns: int = ctx_inherit.DEFAULT_TURNS,
    ) -> ToolResult:
        """Execute a fork skill by delegating to a sub-session via spawn.

        Args:
            skill_name: Name of the skill being executed.
            metadata: Skill metadata containing model/agent configuration.
            body: Raw (unpreprocessed) skill body content.
            arguments: User argument string substituted into the body's
                $ARGUMENTS / positional placeholders. This is the ONLY channel by
                which a /command's argument text reaches the fork, since the fork
                cannot see the parent conversation.
            context_depth: Parent-context inheritance amount ("none" | "recent" |
                "all"). Defaults to "none" (clean slate — the historical fork
                behavior).
            context_scope: Which parent content to inherit ("conversation" |
                "agents" | "full"). Only used when context_depth != "none".
            context_turns: Number of recent turns when context_depth == "recent".

        Returns:
            ToolResult containing the delegate response, or an error ToolResult
            if execution fails.
        """
        try:
            # _execute_fork() is only called when coordinator is confirmed non-None
            assert self.coordinator is not None

            # 1. Preprocess body with skill_dir and arguments. Passing
            # `arguments` here is what makes $ARGUMENTS (and positional $0/$1...)
            # resolve inside the fork — the fork cannot see the parent
            # conversation, so this is its only line to the user's intent.
            # Remote-source skills are untrusted — block shell execution.
            is_trusted = not is_remote_source(metadata.source)
            processed_body = await preprocess(
                body,
                skill_dir=metadata.path.parent,
                arguments=arguments,
                trusted=is_trusted,
            )

            # 1b. Optionally inherit parent-conversation context. By default
            # (context_depth == "none") a fork starts with a clean slate. When a
            # caller opts in, we select+sanitize parent messages exactly like the
            # delegate tool and prepend them to the body as a text preamble, so
            # the sub-session sees them in its first user turn.
            instruction = processed_body
            if context_depth != "none":
                parent_messages = await self._get_parent_messages()
                inherited = ctx_inherit.build_inherited_context(
                    parent_messages, context_depth, context_turns, context_scope
                )
                if inherited:
                    context_block = ctx_inherit.format_parent_context(inherited)
                    instruction = f"{context_block}\n\n[YOUR TASK]\n{processed_body}"

            # 2. Resolve model selection via resolve_skill_model() using metadata fields
            model_resolution = resolve_skill_model(
                provider_preferences=metadata.provider_preferences,
                model_role=metadata.model_role,
                model=metadata.model,
                agent=metadata.agent,
            )

            provider_preferences = model_resolution.get("provider_preferences")
            resolved_model_role = model_resolution.get("model_role")

            # 3. Resolve model_role via the model_role_resolver capability when
            # provider_preferences was not explicitly set. Generic capability
            # name (any routing strategy may register an implementation:
            # matrix-based, cost-aware, latency-aware, etc.). Duck-typed
            # contract:
            #     async def resolve(model_role) -> list[ProviderPreference]
            #
            # Pre-fix bug: this site looked up the capability under the wrong
            # name ("routing_matrix") that was never registered, and called
            # .resolve() synchronously. Fork skills declaring model_role
            # silently fell through to the parent's default provider.
            if resolved_model_role is not None and provider_preferences is None:
                resolver = self.coordinator.get_capability("model_role_resolver")
                if resolver is not None:
                    resolved = await resolver.resolve(resolved_model_role)
                    if resolved:
                        # Resolver returns list[ProviderPreference] (foundation
                        # public type); spawn_fn accepts that shape directly.
                        provider_preferences = list(resolved)
                else:
                    logger.debug(
                        "Fork skill %r has model_role %r but no model_role_resolver "
                        "capability is registered; falling through to parent default provider",
                        skill_name,
                        resolved_model_role,
                    )

            # 4. Get spawn function and related context (matching delegate tool pattern)
            spawn_fn = self.coordinator.get_capability("session.spawn")
            parent_session = self.coordinator.session
            agent_configs = self.coordinator.config.get("agents", {})
            sub_session_id = None
            session_metadata = {
                "skill_name": skill_name,
                "context": "fork",
                "is_forked_skill_session": True,
            }

            # 5. Build tool_inheritance from metadata.allowed_tools.
            # NOTE: session_spawner._filter_tools() reads the "inherit_tools" key —
            # using "allowed_tools" here would silently drop the allowlist.
            tool_inheritance: dict[str, Any] = {}
            if metadata.allowed_tools:
                tool_inheritance["inherit_tools"] = metadata.allowed_tools

            # 6. Call spawn_fn with assembled arguments.
            # The fork-session marker travels exclusively via session_metadata
            # (see step 4 above, "is_forked_skill_session": True). The child's
            # SkillsTool.mount() reads it through _detect_fork_session() and
            # refuses to execute further fork-context skills, preventing
            # infinite recursion. No orchestrator_config marker needed.
            result = await spawn_fn(
                agent_name="self",
                instruction=instruction,
                parent_session=parent_session,
                agent_configs=agent_configs,
                sub_session_id=sub_session_id,
                provider_preferences=provider_preferences,
                session_metadata=session_metadata,
                tool_inheritance=tool_inheritance,
            )

            # 7. Return ToolResult with delegate output fields
            # spawn_fn returns the subagent's output under the "output" key (not "response")
            response_text = result.get("output", "")
            return ToolResult(
                success=True,
                output={
                    "response": response_text,
                    "message": (
                        f"The /{skill_name} skill executed successfully as a forked subagent. "
                        f"Here are the results:\n\n{response_text}"
                        if response_text
                        else f"The /{skill_name} skill completed but returned no output."
                    ),
                    "session_id": result.get("session_id"),
                    "skill_name": skill_name,
                    "context": "fork",
                    "turn_count": result.get("turn_count"),
                    "status": result.get("status"),
                },
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Fork execution failed for skill '{skill_name}': {exc}")
            return ToolResult(
                success=False,
                error={
                    "message": f"Fork execution failed: {exc}",
                    "skill_name": skill_name,
                },
            )
