"""Skills visibility hook - makes available skills visible to agents."""

import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amplifier_core import HookResult

from amplifier_module_tool_skills.discovery import parse_skill_frontmatter

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)

VALID_PLACEMENTS = ("request", "prefix")

# Default token budget for the regular-skills index (used when neither
# visibility_token_budget nor max_skills_visible is configured).
DEFAULT_VISIBILITY_TOKEN_BUDGET = 5000

# Header for the regular (model-invocable) skills section. Kept as a single
# constant so the budget renderer and the legacy count renderer emit identical
# text.
REGULAR_SKILLS_HEADER = "Available skills (use load_skill tool):"

# Detail tiers a regular skill can be rendered at, cheapest first.
_TIER_INDEX = 0  # name only (full-coverage floor)
_TIER_SUMMARY = 1  # name + one-line summary
_TIER_FULL = 2  # name + full description


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

        # Token-budget rendering (the new default). ``visibility_token_budget``
        # bounds how much DETAIL the regular-skills index spends while
        # GUARANTEEING that every regular skill still appears at least as a
        # name-only line (full coverage — no skill is ever silently dropped, the
        # defect the alphabetical ``max_skills_visible`` cap caused). The token
        # estimate is deterministic and dependency-free: ``len(text) // 4``. No
        # tokenizer, no network, no LLM calls. See ``_assemble_budgeted_regular``
        # for the tier algorithm.
        #
        # Mode selection (back-compat):
        #   * ``visibility_token_budget`` set -> budget mode (wins even when
        #     ``max_skills_visible`` is also present).
        #   * only ``max_skills_visible`` set -> legacy count-cap mode, behavior
        #     unchanged.
        #   * neither set -> budget mode with the default budget.
        budget_raw = config.get("visibility_token_budget")
        if budget_raw is not None:
            self._budget_mode = True
            self.token_budget = self._coerce_budget(
                budget_raw, DEFAULT_VISIBILITY_TOKEN_BUDGET
            )
        elif "max_skills_visible" in config:
            self._budget_mode = False
            self.token_budget = DEFAULT_VISIBILITY_TOKEN_BUDGET
        else:
            self._budget_mode = True
            self.token_budget = DEFAULT_VISIBILITY_TOKEN_BUDGET

        # Per-path cache of each skill's parsed ``visibility:`` frontmatter
        # mapping, so the renderer reads any given SKILL.md at most once per
        # session (frontmatter is static for a session's lifetime).
        self._visibility_cache: dict[str, dict[str, Any]] = {}
        # Placement of the skills index (default "prefix" — measured 32-39%
        # root-session cost reduction with identical quality and 100% skill
        # recall in controlled ablation; "request" remains a fully supported
        # explicit opt-out):
        #   "prefix"  — append the index to the SYSTEM PROMPT by wrapping the
        #       context module's system-prompt factory (the surface
        #       amplifier-foundation _prepared.py registers via
        #       context.set_system_prompt_factory; context-simple calls the
        #       factory on EVERY get_messages_for_request). Providers hoist
        #       role=system content into the stable cached prefix (anthropic:
        #       single system block, cache_control breakpoint #1), so the
        #       index is cached across requests and only re-billed when the
        #       skill catalog actually changes. Sessions without a factory
        #       surface fall back to request mode with a one-time WARNING.
        #   "request" — inject_context on every provider:request. The hook
        #       registry merges all same-event injections into one message
        #       (first hook's role/ephemeral win), so the index typically
        #       rides a per-request tail message and is re-sent every call.
        self.placement = config.get("placement", "prefix")
        if self.placement not in VALID_PLACEMENTS:
            raise ValueError(
                f"Invalid visibility.placement={self.placement!r}. "
                f"Valid values: {', '.join(VALID_PLACEMENTS)}."
            )
        self._is_forked_session = is_forked_session
        self.coordinator = coordinator
        self._tool = tool
        # Prefix-placement state: the wrapped factory we registered (identity
        # check for re-wrap detection), the catalog hash of the last render,
        # and the cached rendered block (re-rendered only on catalog change).
        self._prefix_factory: Any = None
        self._prefix_skills_hash: str | None = None
        self._prefix_rendered: str = ""
        self._prefix_unavailable_logged = False

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

        if self.placement == "prefix":
            # Prefix mode: the index lives in the system prompt (via the
            # wrapped factory below), never as a per-request injection —
            # returning continue here is what guarantees the two modes can
            # never double-inject.
            if await self._ensure_prefix_placement():
                return HookResult(action="continue")
            # Placement surface unavailable (no context module / no factory
            # support). Warn once per instance, then fall back to
            # request-mode injection so the agent is not silently blinded to
            # its skills. WARNING, not ERROR: prefix is the DEFAULT now, so
            # sessions that legitimately lack a factory surface (static
            # system prompts, minimal test coordinators) hit this path
            # without any user misconfiguration. The fallback is detectable:
            # the index appears as an injected message, not in the system
            # prompt.
            if not self._prefix_unavailable_logged:
                logger.warning(
                    "visibility.placement='prefix' (the default) but the "
                    "context module offers no system-prompt factory surface "
                    "(set_system_prompt_factory). Falling back to per-request "
                    "injection — the skills index will not ride the stable "
                    "cached prefix. Set visibility.placement='request' to "
                    "silence this warning."
                )
                self._prefix_unavailable_logged = True

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

    async def _ensure_prefix_placement(self) -> bool:
        """Ensure the skills index rides the system prompt (stable prefix).

        Wraps the context module's registered system-prompt factory so the
        factory output becomes ``base + "\\n\\n" + skills_block``. Providers
        hoist role=system content into their cached prefix (anthropic builds
        a single system content block with the cache_control breakpoint), so
        the index is billed once and cache-read afterwards — instead of
        re-sent as fresh input tokens on every request.

        Wrapping is LAZY (first provider:request) because the factory is
        registered during session preparation (amplifier-foundation
        _prepared.py -> context.set_system_prompt_factory) and mount order
        vs. that registration is not guaranteed. Re-checked on every request:
        if someone re-registered a new factory after us, we re-wrap around
        the new one (identity check against our own wrapper).

        Staleness: the factory contract is "called on EVERY
        get_messages_for_request" (context-simple), and the wrapper renders
        from the CURRENT effective skill catalog each call — so the prefix
        always holds exactly one, current copy of the index. A catalog change
        (e.g. mode overlays) changes the rendered text, which busts the
        provider cache once; change is rare, so the cache rides otherwise.

        Returns:
            True when the index is (now) riding the system prompt; False when
            the surface is unavailable and the caller should fall back.
        """
        # Defensive lookup: prefix is the DEFAULT path now, and minimal
        # coordinators (unit-test mocks, embedded hosts) may not expose
        # .get() at all — that is "no surface", not a crash.
        getter = getattr(self.coordinator, "get", None) if self.coordinator else None
        context: Any = getter("context") if callable(getter) else None
        if context is None or not hasattr(context, "set_system_prompt_factory"):
            return False

        current = getattr(context, "_system_prompt_factory", None)
        if current is None:
            # No factory registered (static-system-message session). Wrapping
            # would DROP the static system prompt (factory takes precedence
            # over stored system messages in context-simple), so refuse.
            return False
        if current is self._prefix_factory:
            return True  # already wrapped, still active

        base_factory = current

        async def _skills_prefixed_factory() -> str:
            base = await base_factory()
            block = self._render_prefix_block()
            return f"{base}\n\n{block}" if block else base

        await context.set_system_prompt_factory(_skills_prefixed_factory)
        self._prefix_factory = _skills_prefixed_factory
        logger.info(
            "Skills index placement: system-prompt prefix (wrapped the "
            "registered system-prompt factory)"
        )
        return True

    def _render_prefix_block(self) -> str:
        """Render the skills block for prefix placement, cached by catalog hash.

        Re-renders ONLY when the effective skill catalog changes (cheap hash
        over name/description/flags). A change means the system prompt text
        changes, which busts the provider's prefix cache once — acceptable,
        because catalog changes (mode overlays, runtime skill loads) are rare
        events, and the alternative is a permanently stale index.
        """
        effective = self._effective_skills()
        catalog_repr = repr(
            sorted(
                (
                    name,
                    meta.description,
                    bool(meta.disable_model_invocation),
                    getattr(meta, "context", None),
                )
                for name, meta in (effective or {}).items()
            )
        )
        catalog_hash = hashlib.sha256(catalog_repr.encode()).hexdigest()
        if catalog_hash != self._prefix_skills_hash:
            if self._prefix_skills_hash is not None:
                logger.info(
                    "Skill catalog changed — refreshing skills index in the "
                    "system prompt (one-time prefix cache bust)"
                )
            self._prefix_skills_hash = catalog_hash
            self._prefix_rendered = (
                self._format_skills_list(effective) if effective else ""
            )
        return self._prefix_rendered

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
            return not (is_forked and meta.context == "fork")

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

        # Build regular skills section.
        if regular_skills:
            if self._budget_mode:
                # Budget mode: full coverage, detail bounded by the token budget.
                lines.extend(self._assemble_budgeted_regular(regular_skills))
            else:
                # Legacy count-cap mode (unchanged): alphabetical, first N shown,
                # remainder summarized as a "(N more ...)" line.
                skills_items = sorted(regular_skills.items())[: self.max_visible]
                lines.append(REGULAR_SKILLS_HEADER)
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

    # ------------------------------------------------------------------
    # Token-budget tier assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_budget(value: Any, default: int) -> int:
        """Coerce a configured budget into a non-negative int.

        Falls back to ``default`` (with a warning) for non-numeric or negative
        values, so a typo in config degrades gracefully instead of crashing the
        request path.
        """
        try:
            budget = int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid visibility_token_budget=%r; falling back to %d.",
                value,
                default,
            )
            return default
        if budget < 0:
            logger.warning(
                "Negative visibility_token_budget=%r; falling back to %d.",
                value,
                default,
            )
            return default
        return budget

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Cheap, deterministic, dependency-free token estimate (~4 chars/token)."""
        return len(text) // 4

    def _skill_visibility(self, meta: Any) -> dict[str, Any]:
        """Return a skill's optional ``visibility:`` frontmatter mapping.

        Resolution order:
          1. A ``visibility`` attribute already present on the metadata object
             (lets discovery, overlays, or tests carry the mapping directly with
             no file I/O).
          2. The ``visibility:`` block parsed from the skill's SKILL.md
             frontmatter, cached per path so each file is read at most once.

        Returns an empty mapping when nothing is available, which yields the
        neutral defaults (priority 0, summary derived from the description).
        """
        direct = getattr(meta, "visibility", None)
        if isinstance(direct, dict):
            return direct

        path = getattr(meta, "path", None)
        if path is None:
            return {}
        key = str(path)
        cached = self._visibility_cache.get(key)
        if cached is not None:
            return cached

        mapping: dict[str, Any] = {}
        try:
            frontmatter = parse_skill_frontmatter(Path(path))
            if frontmatter:
                raw = frontmatter.get("visibility")
                if isinstance(raw, dict):
                    mapping = raw
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not read visibility frontmatter for %s: %s", key, exc)
        self._visibility_cache[key] = mapping
        return mapping

    def _skill_priority(self, meta: Any) -> int:
        """Render priority (default 0); higher sorts earlier."""
        raw = self._skill_visibility(meta).get("priority", 0)
        # bool is an int subclass — treat True/False as "no explicit priority".
        if isinstance(raw, bool) or not isinstance(raw, int):
            return 0
        return raw

    def _skill_summary(self, meta: Any) -> str:
        """One-line summary for the summary tier.

        Uses an explicit ``visibility.summary`` string when present, otherwise
        falls back to the first sentence of the description (truncated).
        """
        raw = self._skill_visibility(meta).get("summary")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return self._first_sentence(getattr(meta, "description", "") or "")

    @staticmethod
    def _first_sentence(description: str, limit: int = 140) -> str:
        """First sentence of ``description``, whitespace-collapsed and truncated
        to ``limit`` characters (ellipsis added when truncation occurs)."""
        text = " ".join(description.split())
        if not text:
            return ""
        match = re.search(r"[.!?](?:\s|$)", text)
        sentence = text[: match.start() + 1] if match else text
        if len(sentence) > limit:
            sentence = sentence[: limit - 3].rstrip() + "..."
        return sentence

    def _skill_line(self, name: str, meta: Any, tier: int) -> str:
        """Render one regular-skill line at the given detail tier."""
        if tier <= _TIER_INDEX:
            return f"- **{name}**"
        if tier == _TIER_SUMMARY:
            return f"- **{name}**: {self._skill_summary(meta)}"
        return f"- **{name}**: {meta.description}"

    def _regular_section_lines(
        self, ranked: list[tuple[str, Any]], tiers: dict[str, int]
    ) -> list[str]:
        """Assemble the regular-skills section (header + one line per skill)."""
        lines = [REGULAR_SKILLS_HEADER, ""]
        for name, meta in ranked:
            lines.append(self._skill_line(name, meta, tiers[name]))
        return lines

    def _assemble_budgeted_regular(
        self, regular_skills: dict[str, Any]
    ) -> list[str]:
        """Render the regular-skills section under the token budget.

        Invariant: every regular skill is present at least as a name-only index
        line. The budget bounds DETAIL, never coverage — no skill is dropped
        even if the index floor alone exceeds the budget.

        Assembly is deterministic:
          1. Reserve a name-only index line for every regular skill.
          2. Upgrade index -> one-line summary, in rank order, while the budget
             allows.
          3. Upgrade summary -> full description, in rank order, while the
             budget allows.

        Rank order is ``(-priority, name)``: higher priority first, ties broken
        alphabetically.
        """
        if not regular_skills:
            return []

        ranked: list[tuple[str, Any]] = sorted(
            regular_skills.items(),
            key=lambda item: (-self._skill_priority(item[1]), item[0]),
        )
        tiers: dict[str, int] = {name: _TIER_INDEX for name, _ in ranked}

        def within_budget() -> bool:
            text = "\n".join(self._regular_section_lines(ranked, tiers))
            return self._estimate_tokens(text) <= self.token_budget

        # Pass 1: index -> summary, in rank order, while the budget allows.
        for name, _meta in ranked:
            tiers[name] = _TIER_SUMMARY
            if not within_budget():
                tiers[name] = _TIER_INDEX
                break

        # Pass 2: summary -> full description, in rank order, while allowed.
        for name, _meta in ranked:
            if tiers[name] != _TIER_SUMMARY:
                continue
            tiers[name] = _TIER_FULL
            if not within_budget():
                tiers[name] = _TIER_SUMMARY
                break

        return self._regular_section_lines(ranked, tiers)
