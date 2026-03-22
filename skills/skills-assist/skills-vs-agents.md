# Skills vs Agents: Decision Guide

When you have something valuable to teach an AI coding assistant, you face a fundamental choice: package it as a **skill** (a portable SKILL.md file) or build it as an **agent** (a bundle with custom tools and orchestration). This guide walks you through that decision, traces the converging boundary between the two, and shows what carries forward when you graduate a skill to an agent.

---

## Start With a Skill When

Most packaged expertise belongs in a skill first. Skills load fast, travel across harnesses, and need no infrastructure. Start here unless you hit one of the agent criteria below.

### 6 Criteria for Choosing a Skill

**1. Packaged expertise that loads on demand**
Your knowledge is stable, reference-like, and doesn't need to execute code to be useful. Style guides, architectural patterns, API usage patterns, team conventions, domain vocabulary — these are all packaged expertise. A skill injects them into context exactly when the model needs them, without requiring a separate process or tool call overhead.

**2. Portable across harnesses**
You want the same knowledge to work in Amplifier, Claude Code, GitHub Copilot, and other Agent Skills-compatible tools. Skills written against the base spec (name, description, and SKILL.md body) travel without modification. Add companion files for depth; keep frontmatter to standard fields for maximum portability.

**3. User-invocable as a slash command**
The capability is something users consciously invoke: `/python-standards`, `/code-review`, `/explain-architecture`. The `user-invocable: true` frontmatter field promotes the skill to a named command. This is the right pattern for on-demand guidance, not for background automation.

**4. Lightweight — context injection without tool overhead**
You don't need to run tools, call APIs, or maintain state. The value is purely in what the model knows while answering. Skills are context sinks: they add knowledge to the model's working memory without spawning processes. If your capability is "tell the model how to do X," that's a skill.

**5. Auto-activate via hooks without user intervention**
The expertise should silently load when relevant conditions are detected — e.g., load Python standards whenever a `.py` file is opened, or load security guidelines whenever auth-related files are touched. Amplifier's `hooks` frontmatter field wires a skill to session lifecycle events. The user gets the expertise without remembering to invoke it.

**6. Community-shareable as a standalone artifact**
You want to publish this to a skill registry, share it in a README, or drop it into any project's `.amplifier/skills/` directory without configuration. Skills are self-contained: one directory, one SKILL.md, optional companion files. There's no bundle YAML to author, no module registry to update, no installation step. The portability of the skill format is what makes community sharing viable.

### Examples

1. **`python-standards`** — Loads PEP 8, type annotation patterns, and project-specific linting rules. User-invocable and auto-loads on `.py` file hooks. Portable to any harness.

2. **`api-design`** — REST naming conventions, pagination patterns, error response shapes. A context sink that loads when the model is writing route handlers or OpenAPI specs.

3. **`commit-conventions`** — Conventional Commits spec plus team-specific scopes. Auto-loads via a pre-commit hook trigger. Zero infrastructure; travels in the repo.

4. **`security-checklist`** — OWASP Top 10 reminders, input validation patterns, secrets hygiene. User-invocable before code review. Community-shareable as a standalone skill package.

5. **`domain-vocabulary`** — Ubiquitous language for a bounded context (DDD terms, business entity names, process names). Auto-loads when the model touches domain model files. Portable and lightweight.

---

## Graduate to an Agent When

A skill becomes limiting when it needs to *do* things, not just *know* things. Agents have tool composition, session memory, and bundle integration. Graduate when you hit these walls.

### 6 Criteria for Choosing an Agent

**1. Custom tool composition**
Your capability requires calling specific tools in a specific order — not just any tool, but a curated set with configured behavior. Agents declare their tool composition in bundle YAML: which tools are available, which are restricted, and how they interact. A skill can hint at tool usage in its body, but it cannot enforce or configure tool availability.

**2. Multi-turn session resumption**
The work spans multiple turns and must be resumable: a code-review workflow that pauses for human approval, a migration assistant that checkpoints progress, a multi-step refactoring that can be interrupted and continued. Agents run as sessions with `session_id` tracking. Session resumption is a first-class agent capability with no skill equivalent.

**3. Precise context inheritance**
You need fine-grained control over what context the capability receives: only the last N turns, only conversation text (no tool results), or a completely clean slate. Skills inject into the caller's existing context. Agents use `context_depth` and `context_scope` delegation parameters to receive exactly the context they need — no more, no less.

**4. Custom orchestrator config**
Your capability needs non-default model routing (a reasoning model for planning, a fast model for extraction, a vision model for screenshot analysis), custom provider preferences, or per-task model switching. Agents configure their orchestrator in bundle YAML. Skills can declare a `model_role` preference, but cannot configure provider preferences or dynamic routing.

**5. Recursive sub-agent delegation**
The capability itself needs to spawn sub-agents — parallel workers, specialized sub-investigators, or staged pipelines. An agent can delegate to other agents with full context control. A skill cannot spawn agents; it has no delegation mechanism.

**6. Deep bundle integration**
The capability is a first-class member of a bundle's agent roster: it appears in `delegate` tool output, it has a named description surfaced to the orchestrator, it integrates with other agents in the bundle through shared context files and coordinated orchestration. Bundle integration requires bundle membership; skills live outside the bundle hierarchy.

### Examples

1. **`parallax-discovery:code-tracer`** — Needs LSP tool composition, must write artifacts to disk, runs as part of a multi-agent triplicate team. Recursive delegation and precise context inheritance make this an agent, not a skill.

2. **`dev-machine:operator-advisor`** — Carries 60K tokens of operational documentation as a context sink *and* performs multi-turn recovery workflows with session resumption. The stateful recovery workflow is what makes it an agent.

3. **`recipes:recipe-author`** — Interactive multi-turn session with approval gates, custom model routing for schema validation, and sub-delegation to `result-validator`. Conversational stateful authoring needs agent infrastructure.

4. **`foundation:bug-hunter`** — Orchestrates hypothesis-driven debugging across multiple files, runs tests, interprets output, and iterates. Tool composition (bash, grep, LSP) and multi-turn iteration make this an agent.

---

## Decision Flowchart

Use this flowchart when you're unsure which to build:

```
                    ┌─────────────────────────────────┐
                    │  Do you need to run tools,       │
                    │  call APIs, or execute code?     │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                   YES                        NO
                    │                         │
                    ▼                         ▼
     ┌──────────────────────────┐   ┌──────────────────────────┐
     │ Does it need session     │   │ Is it just packaged       │
     │ resumption or stateful   │   │ knowledge/expertise?      │
     │ multi-turn interaction?  │   └────────────┬─────────────┘
     └──────────┬───────────────┘                │
                │                    ┌───────────┴──────────┐
     ┌──────────┴──────────┐         │                      │
     │                     │        YES                      NO
    YES                    NO        │                      │
     │                     │         ▼                      ▼
     ▼                     │  ┌──────────────┐   ┌──────────────────┐
  AGENT                    │  │    SKILL     │   │ Reconsider scope: │
                           │  └──────────────┘   │ maybe two steps  │
          ┌────────────────┴────────────────┐     └──────────────────┘
          │ Does it need sub-agent          │
          │ delegation or custom            │
          │ orchestrator config?            │
          └──────────────┬─────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
             YES                    NO
              │                     │
              ▼                     ▼
           AGENT          ┌──────────────────────┐
                          │ Does it need bundle  │
                          │ integration or       │
                          │ tool composition?    │
                          └──────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                         YES                    NO
                          │                     │
                          ▼                     ▼
                       AGENT                  SKILL
```

**Quick rule of thumb:**
- Knows things → **Skill**
- Does things → **Agent**
- Both, but knowledge comes first → **Skill with companion files**, graduate later if needed

---

## The Convergence Path

Skills and agents are converging. The boundary between them is narrowing as both formats gain capabilities. Understanding the convergence path helps you build for where the ecosystem is heading, not just where it is today.

### 4 Convergence Observations

**1. Anthropic merged commands into skills**
Claude Code originally had two separate primitives: `/commands` (user-invocable CLAUDE.md files) and skills (SKILL.md files loaded as context). Anthropic merged these into a single format — a SKILL.md with `user-invocable: true` is now a slash command. This convergence eliminated a redundant primitive. Watch for similar consolidations elsewhere in the spec.

**2. context:fork gives agent-like isolation**
The `context: fork` frontmatter field gives skills a clean, isolated context window — the same benefit that previously required spawning a full agent. A skill with `context: fork` runs in its own forked session, accumulates its own tool results, and returns a clean summary to the caller. This is architecturally equivalent to a lightweight agent delegation. The isolation boundary that used to require full agent infrastructure is now available to skills.

**3. Skills gain more capabilities over time**
`allowed-tools` lets skills declare which tools they can use. `model_role` lets skills request a specific model class. `auto-load` and `hooks` give skills lifecycle awareness. Each capability addition narrows the gap. A skill today with `context: fork`, `allowed-tools`, and `model_role` looks a lot like a thin agent. The trajectory is toward parity for lightweight use cases.

**4. The portable standard grows**
The Agent Skills base spec is evolving toward a richer portable standard. Features that started as Amplifier extensions (like `user-invocable`) are being adopted by other harnesses. The community skill registry model rewards portability. As the standard grows, more agent-like capabilities become available to all skills, not just Amplifier-specific bundles.

### Practical Implication

Today, this means: **start with a skill and graduate only when you hit a hard wall**. The walls are getting farther away. If you're adding `context: fork`, `allowed-tools`, and `model_role` to a skill, you have a lightweight agent already — you just haven't committed to full bundle infrastructure yet. That's fine; it's the right intermediate state. Graduate to a full agent when you need session resumption, sub-agent delegation, or deep bundle integration. For everything else, the skill format will get you there.

---

## What Carries Forward

When a skill graduates to an agent, nothing is thrown away. Every component of the skill maps directly to an agent equivalent. Understanding this mapping makes the migration straightforward.

### Component Mapping Table

| Skill Component | Agent Equivalent | Notes |
|-----------------|------------------|-------|
| `SKILL.md` body | Instruction prompt (`instruction:` in bundle.md or inline) | The prose instructions become the agent's system prompt. Migrate verbatim; refine for agent affordances. |
| Companion files | Context files (loaded via `read_file` or bundle context) | Companion files become context files loaded in the agent's forked session. Same content, different loading mechanism. |
| `description:` frontmatter | Agent `description:` in bundle agent roster | The description surfaces in `delegate` tool output. Write it to answer "when should I use this?" |
| `model_role:` frontmatter | `model_role` in delegation or bundle config | Model role preference maps directly. Agents can additionally configure `provider_preferences` and dynamic routing. |
| `allowed-tools:` frontmatter | Tool composition in bundle YAML | Tool allowlist becomes an explicit tool composition declaration. Agents can additionally configure per-tool settings. |
| `context: fork` | `context_depth` + `context_scope` in delegation | Fork isolation maps to clean-slate delegation (`context_depth: none`). Agents get richer control: recent N turns, conversation-only, full with tool results. |

### What You Gain by Becoming an Agent

When you graduate from a skill to an agent, you gain:

- **Session identity** — a `session_id` that callers can resume, track, and reference across turns
- **Multi-turn statefulness** — the ability to pause, checkpoint, and continue long-running workflows
- **Sub-agent delegation** — spawn parallel workers, specialized investigators, or staged pipelines
- **Precise context control** — choose exactly what context each sub-task receives (none, recent N turns, conversation-only, full with tool results)
- **Bundle membership** — appear in the `delegate` tool's agent roster, coordinate with sibling agents via shared context, and participate in bundle-level orchestration
- **Dynamic model routing** — switch models mid-task based on what each step requires (reasoning for planning, fast for extraction, vision for screenshots)
- **Approval gates** — pause execution for human review before committing to irreversible actions

You give up:
- **Portability** — agents are Amplifier-specific; skills work across harnesses
- **Zero-infrastructure simplicity** — agents require bundle YAML, roster entries, and potentially module configuration
- **Community shareability** — publishing an agent requires publishing a bundle; publishing a skill requires dropping a directory into `.amplifier/skills/`

The right graduation moment is when the gains outweigh the costs — and with `context: fork`, `allowed-tools`, and `model_role` all available to skills, that moment comes later than it used to.
