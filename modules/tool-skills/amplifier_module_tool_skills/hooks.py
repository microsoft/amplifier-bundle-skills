"""Skills visibility hook - makes available skills visible to agents."""

import logging
from typing import TYPE_CHECKING, Any

from amplifier_core import HookResult

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


class SkillsVisibilityHook:
    """Hook that injects available skills list into context before each LLM call.

    This follows the Agent Skills specification recommendation to inject
    skill metadata into context, enabling progressive disclosure:
    - Level 1 (Always visible): Metadata via this hook
    - Level 2 (On demand): Full content via load_skill tool
    - Level 3 (References): Companion files via read_file
    """

    def __init__(
        self,
        skills: dict[str, Any],
        config: dict[str, Any],
        is_forked_session: bool = False,
        coordinator: "ModuleCoordinator | None" = None,
        tool: Any = None,
    ):
        """Initialize hook with skills data from tool.

        Args:
            skills: Dictionary of discovered skills (from SkillsTool.skills).
                Used as fallback when ``tool`` is not provided (e.g. legacy
                callers and unit tests).
            config: Hook configuration from visibility section
            is_forked_session: When True, fork-context skills are omitted from the
                injected list.  This prevents the LLM inside a forked sub-session
                from seeing (and attempting to invoke) other fork skills, which
                would cause infinite recursion.
            coordinator: Optional module coordinator for capability-based fallback
                detection of forked session state (defense-in-depth).
            tool: Optional ``SkillsTool`` reference. When provided, the hook
                uses ``tool.get_effective_skills()`` to obtain the merged static
                + runtime-overlay catalog on every request, so mode-contributed
                skills become visible while the contributing mode is active.
                When omitted, the hook falls back to ``skills`` (a static dict
                with no overlay merge). Production mount path supplies it; some
                unit tests do not.
        """
        self.skills = skills  # Reference to tool's skills dict (legacy/fallback path)
        self.enabled = config.get("enabled", True)
        self.inject_role = config.get("inject_role", "system")
        self.max_visible = config.get("max_skills_visible", 50)
        self.ephemeral = config.get("ephemeral", True)
        self.priority = config.get("priority", 20)
        self._is_forked_session = is_forked_session
        self.coordinator = coordinator
        self._tool = tool

        logger.debug(
            f"Initialized SkillsVisibilityHook: enabled={self.enabled}, "
            f"max_visible={self.max_visible}, ephemeral={self.ephemeral}, "
            f"is_forked_session={self._is_forked_session}, "
            f"tool_attached={self._tool is not None}"
        )

    def _effective_skills(self) -> dict[str, Any]:
        """Return the catalog the hook should render on this request.

        Prefers ``tool.get_effective_skills()`` (static + overlay merge) when
        a tool reference is attached; falls back to the static ``self.skills``
        dict otherwise so legacy callers and unit tests keep working.
        """
        if self._tool is not None and hasattr(self._tool, "get_effective_skills"):
            try:
                return self._tool.get_effective_skills()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "tool.get_effective_skills() raised %s; falling back to static catalog",
                    exc,
                )
        return self.skills

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        """Inject skills list before LLM request.

        Event: provider:request (before each LLM call)

        Args:
            event: Event name (should be "provider:request")
            data: Event data dictionary

        Returns:
            HookResult with action="inject_context" if skills should be shown,
            or action="continue" if disabled or no skills available
        """
        if not self.enabled:
            return HookResult(action="continue")

        effective = self._effective_skills()
        if not effective:
            return HookResult(action="continue")

        skills_text = self._format_skills_list(effective)

        if not skills_text:
            return HookResult(action="continue")

        return HookResult(
            action="inject_context",
            context_injection=skills_text,
            context_injection_role=self.inject_role,
            ephemeral=self.ephemeral,
            suppress_output=True,
        )

    def _format_skills_list(self, skills: dict[str, Any] | None = None) -> str:
        """Format skills list as markdown with XML boundaries.

        Partitions skills into two sections:
        - Regular skills (disable_model_invocation=False): shown under 'Available skills'
          with max_visible cap
        - User-invoked skills (disable_model_invocation=True): shown under 'User-invoked
          skills' with no cap

        Args:
            skills: Optional catalog dict to render. Defaults to the
                effective-skills view (static + overlay merge). Passing
                an explicit dict supports legacy test callers that
                exercise the formatter in isolation.

        Returns:
            Formatted skills list string, or empty string if no skills
        """
        if skills is None:
            skills = self._effective_skills()
        if not skills:
            return ""

        # Partition skills into regular and user-invoked.
        # When running inside a forked skill sub-session, omit fork-context skills
        # from both partitions so the child LLM cannot see (and attempt to invoke)
        # them — the primary trigger for infinite fork recursion.
        def _keep(meta: Any) -> bool:
            """Return True if this skill should be visible in the current context."""
            is_forked = self._is_forked_session
            # Defense-in-depth: also check coordinator capability if available and
            # the constructor flag wasn't already set.
            if not is_forked and self.coordinator is not None:
                is_forked = bool(self.coordinator.get_capability("skills.fork_context"))
            if is_forked and meta.context == "fork":
                return False
            return True

        regular_skills = {
            name: meta
            for name, meta in skills.items()
            if not meta.disable_model_invocation and _keep(meta)
        }
        user_invoked_skills = {
            name: meta
            for name, meta in skills.items()
            if meta.disable_model_invocation and _keep(meta)
        }

        lines = []

        # Build regular skills section (with max_visible cap)
        if regular_skills:
            skills_items = sorted(regular_skills.items())[: self.max_visible]
            lines.append("Available skills (use load_skill tool):")
            lines.append("")
            for name, metadata in skills_items:
                lines.append(f"- **{name}**: {metadata.description}")
            # Show truncation if applicable
            if len(regular_skills) > self.max_visible:
                remaining = len(regular_skills) - self.max_visible
                lines.append("")
                lines.append(
                    f"_({remaining} more - use load_skill(list=true) to see all)_"
                )

        # Build user-invoked skills section (no cap)
        if user_invoked_skills:
            if lines:
                lines.append("")
            lines.append("User-invoked skills (available via /command):")
            lines.append("")
            for name, metadata in sorted(user_invoked_skills.items()):
                lines.append(f"- **{name}**: {metadata.description}")

        if not lines:
            return ""

        skills_content = "\n".join(lines)

        # Wrap in system-reminder tag with source attribution
        return f'<system-reminder source="hooks-skills-visibility">\n{skills_content}\n</system-reminder>'
