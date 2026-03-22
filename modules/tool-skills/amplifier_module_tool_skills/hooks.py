"""Skills visibility hook - makes available skills visible to agents."""

import logging
from typing import Any

from amplifier_core import HookResult

logger = logging.getLogger(__name__)


class SkillsVisibilityHook:
    """Hook that injects available skills list into context before each LLM call.

    This follows the Agent Skills specification recommendation to inject
    skill metadata into context, enabling progressive disclosure:
    - Level 1 (Always visible): Metadata via this hook
    - Level 2 (On demand): Full content via load_skill tool
    - Level 3 (References): Companion files via read_file
    """

    def __init__(self, skills: dict[str, Any], config: dict[str, Any]):
        """Initialize hook with skills data from tool.

        Args:
            skills: Dictionary of discovered skills (from SkillsTool.skills)
            config: Hook configuration from visibility section
        """
        self.skills = skills  # Reference to tool's skills dict
        self.enabled = config.get("enabled", True)
        self.inject_role = config.get("inject_role", "system")
        self.max_visible = config.get("max_skills_visible", 50)
        self.ephemeral = config.get("ephemeral", True)
        self.priority = config.get("priority", 20)

        logger.debug(
            f"Initialized SkillsVisibilityHook: enabled={self.enabled}, "
            f"max_visible={self.max_visible}, ephemeral={self.ephemeral}"
        )

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
        if not self.enabled or not self.skills:
            return HookResult(action="continue")

        skills_text = self._format_skills_list()

        if not skills_text:
            return HookResult(action="continue")

        return HookResult(
            action="inject_context",
            context_injection=skills_text,
            context_injection_role=self.inject_role,
            ephemeral=self.ephemeral,
            suppress_output=True,
        )

    def _format_skills_list(self) -> str:
        """Format skills list as markdown with XML boundaries.

        Partitions skills into two sections:
        - Regular skills (disable_model_invocation=False): shown under 'Available skills'
          with max_visible cap
        - User-invoked skills (disable_model_invocation=True): shown under 'User-invoked
          skills' with no cap

        Returns:
            Formatted skills list string, or empty string if no skills
        """
        if not self.skills:
            return ""

        # Partition skills into regular and user-invoked
        regular_skills = {
            name: meta
            for name, meta in self.skills.items()
            if not meta.disable_model_invocation
        }
        user_invoked_skills = {
            name: meta
            for name, meta in self.skills.items()
            if meta.disable_model_invocation
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

        skills_content = "\n".join(lines)

        # Wrap in system-reminder tag with source attribution
        return f'<system-reminder source="hooks-skills-visibility">\n{skills_content}\n</system-reminder>'
