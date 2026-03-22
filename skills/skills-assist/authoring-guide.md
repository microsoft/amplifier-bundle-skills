# Skills Authoring Guide

Reference for writing Amplifier skills. Read this file when users ask how to create, structure, or improve skills.

---

## Directory Structure

Skills live in a named directory containing a `SKILL.md` file. Optional companion files (scripts, guides, examples) can be placed alongside it.

```
skills/
└── my-skill/
    ├── SKILL.md           # Required — frontmatter + body instructions
    ├── setup.md           # Optional companion: setup instructions
    ├── patterns.md        # Optional companion: usage patterns
    └── examples/          # Optional companion: example files
        └── example.py
```

### Discovery Paths

Amplifier searches for skills in this order (first match wins):

| Priority | Path | Notes |
|----------|------|-------|
| 1 (highest) | `.amplifier/skills/` | Workspace-scoped, project-specific skills |
| 2 | `~/.amplifier/skills/` | User-scoped skills available in all sessions |
| 3 | `AMPLIFIER_SKILLS_DIR` | Environment variable override for custom locations |
| 4 | Bundle skills dirs | Skills shipped with installed bundles |

### Git URL Sources

Skills can also be loaded from git repositories:

```yaml
# In settings.yaml or amplifier config
skills_sources:
  - git+https://github.com/org/skills-repo.git
  - git+https://github.com/org/skills-repo.git@v1.2.0  # pin a tag
```

Git sources are cloned locally and searched the same way as local directories.

---

## SKILL.md Format

### Minimal Example

```yaml
---
name: my-skill
description: "Brief, specific description of what this skill does and when to invoke it."
---

# My Skill

Instructions for the LLM go here.
```

The `name` and `description` fields are the only required frontmatter fields. Everything else is optional.

### Complete Frontmatter Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | — | **Required.** Unique identifier, kebab-case. Used as the `/shortcut` command name when `user-invocable: true`. |
| `description` | string | — | **Required.** What the skill does and when to invoke it. Used in system prompt context. Write for the agent reading it, not a human menu. |
| `context` | enum: `fork` | `null` (none) | When set to `fork`, the skill runs in a fresh context window that does not inherit the caller's conversation history. Ideal for context-sink patterns where you want a clean slate. |
| `model_role` | string | `general` | Preferred model role for executing this skill. Matched against the active routing matrix. Common values: `general`, `reasoning`, `coding`, `critique`. Only applies when `context: fork`. |
| `user-invocable` | boolean | `false` | When `true`, registers the skill as a `/name` shortcut that users can invoke directly. Also lists the skill in `/skills` output. |
| `allowed-tools` | string | all tools | Space-separated list of tool names the forked context is allowed to use. Example: `Read Grep Glob Bash`. Restricts the tool surface for security or focus. Only applies when `context: fork`. |
| `disable-model-invocation` | boolean | `false` | When `true`, the skill body is loaded as a system prompt and the model is NOT called in the root context — it is expected to delegate immediately. Used for orchestrator patterns that spawn workers via `delegate`. |
| `auto-load` | boolean | `false` | When `true`, the skill's body is automatically injected into the system prompt at session startup. Use sparingly — only for skills that must always be active. |
| `license` | string | — | SPDX license identifier for the skill (e.g., `MIT`, `Apache-2.0`). Informational only. |
| `version` | string | — | Skill version string (e.g., `1.0.0`). Informational only. |

---

## Progressive Disclosure Levels

Skills are loaded lazily to conserve context. The skill loading system has three disclosure levels:

| Level | What is Loaded | Token Cost | When |
|-------|---------------|------------|------|
| **Metadata** | `name`, `description`, frontmatter fields only | ~100 tokens | Always — at session startup, Amplifier loads all skill metadata to populate the routing context |
| **Content** | Full `SKILL.md` body (instructions, examples, workflow) | ~1–5K tokens | On demand — when the skill is invoked by name or matched to a user request |
| **References** | Companion files (`setup.md`, `patterns.md`, `examples/`) | 0 until read | Explicit — companion files are never auto-loaded; the skill body must call `read_file` to pull them in |

**Design implication:** Put the minimum required instructions in `SKILL.md`. Move large reference material, examples, and setup docs to companion files. The forked context window only pays the cost of what it reads.

---

## Best Practices

### From the Agent Skills Specification

1. **Write descriptions for agents, not humans.** The description field is injected into system prompt context — it tells a routing agent when and why to invoke this skill. Be specific about use cases: "Use when tasks require analyzing images" is better than "Image analysis skill."

2. **Keep the body focused.** A skill body should do one thing well. Avoid combining multiple unrelated workflows in a single SKILL.md. If your skill has three distinct phases, those phases should be documented in order within the body — not split across three skills.

3. **Use `$ARGUMENTS` for user input.** When a skill accepts parameters (file paths, topic names, feature descriptions), reference them via `$ARGUMENTS` in the body. The harness substitutes the user's input at invocation time. Guard against empty arguments with an explicit check.

4. **Companion files over inline content.** Large reference tables, setup instructions, code examples, and troubleshooting guides belong in companion files, not inline in SKILL.md. This keeps the skill body readable and avoids loading large content into every invocation context.

### Amplifier-Specific Best Practices

5. **Use `context: fork` for context-sink patterns.** When your skill is a knowledge consultant, orchestrator, or debugging tool that should not see the user's conversation history, set `context: fork`. This gives the forked agent a clean context window with only the skill body and the user's arguments.

6. **Set `model_role` to match the task.** Amplifier routes forked contexts to specialized model roles. Use `reasoning` for architecture decisions, `critique` for code review, `coding` for implementation work, `general` for broad consultation. Incorrect role selection wastes model capacity.

7. **Use `allowed-tools` to restrict surface area.** Orchestrator skills that only need to read files should set `allowed-tools: Read Grep Glob`. This prevents accidental writes and makes the skill's capability boundary explicit and auditable.

8. **Validate `$ARGUMENTS` at the top of the body.** If your skill requires arguments, add a guard check as the first step: check whether `$ARGUMENTS` is empty, and if so output a usage example and stop. Worker agents spawned from orchestrators cannot ask the user for missing information — the orchestrator must ensure arguments are complete before delegating.

---

## Examples

### Example 1: Simple Information Skill

A static reference skill that loads companion files on demand. No fork, no delegation — just inline instructions.

```yaml
---
name: git-conventions
description: "Reference for this project's git commit conventions, branch naming, and PR workflow. Use when creating commits, naming branches, or preparing pull requests."
---

# Git Conventions

This project follows conventional commits and trunk-based development.

## Commit Format

```
type(scope): short description

Body explaining why, not what. 72 char limit.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Branch Naming

`type/short-description` — e.g., `feat/user-auth`, `fix/login-timeout`

## PR Checklist

- Tests pass locally
- CHANGELOG updated if user-visible change
- Description explains the why
```

**Key features:** No frontmatter beyond `name` and `description`. No companion files needed — the convention is short enough to inline. Invoked when the agent needs commit guidance.

---

### Example 2: Fork Skill / Context-Sink Expert

A knowledge consultant that forks a clean context, loads reference material, and synthesizes answers. This is the context-sink pattern.

```yaml
---
name: api-design-expert
description: "Authoritative consultant for REST API design questions. Use when designing new endpoints, reviewing API contracts, or deciding between REST and GraphQL patterns."
context: fork
model_role: reasoning
user-invocable: true
---

# API Design Expert

You are the authoritative expert on REST API design, HTTP semantics, and API versioning strategies.

## Question

$ARGUMENTS

If no question was provided, ask the user what API design topic they need help with.

## Instructions

1. **Load relevant reference files** based on the question topic:
   - `read_file("skills/api-design-expert/rest-patterns.md")` — for REST endpoint design
   - `read_file("skills/api-design-expert/versioning.md")` — for versioning strategies
   - `read_file("skills/api-design-expert/graphql-comparison.md")` — for REST vs GraphQL decisions

2. **Synthesize an authoritative answer** from the loaded material. Do not guess — if the answer is not in the reference files, say so.

3. **Provide concrete examples** with HTTP method + path + response shape.

4. **Flag tradeoffs** between approaches when multiple valid designs exist.
```

**Key features:** `context: fork` for clean slate, `model_role: reasoning` for architectural decisions, `user-invocable: true` to register as `/api-design-expert`, `$ARGUMENTS` for the question, companion files loaded on demand via `read_file`.

---

### Example 3: Auto-Load Hook Skill

A skill that injects persistent context at session startup. Use sparingly — only for always-relevant conventions.

```yaml
---
name: project-context
description: "Core project context: tech stack, architecture decisions, coding conventions. Auto-loaded at startup to keep every agent session oriented."
auto-load: true
---

# Project Context

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0
- **Database:** PostgreSQL 15 with Alembic migrations
- **Frontend:** React 18, TypeScript, Vite
- **Testing:** pytest (backend), Vitest (frontend)
- **CI:** GitHub Actions, deploys on merge to main

## Architecture Decisions

- All API endpoints must be async
- Use repository pattern for data access — no direct ORM queries in handlers
- Feature flags via LaunchDarkly, not environment variables

## Coding Conventions

- Backend: black + ruff, type annotations required on all public functions
- Frontend: ESLint + Prettier, no `any` types without a comment explaining why
- Commits: conventional commits required (see `/git-conventions`)
```

**Key features:** `auto-load: true` injects this into every session's system prompt. No `context: fork` — auto-load skills always run in the root context. Keep auto-load skills short; they are paid at every session start.

---

### Example 4: User-Invocable Power Skill

A full orchestrator skill that spawns parallel agents, restricts its tool surface, and requires arguments.

```yaml
---
name: security-audit
description: "Run a parallel security audit across the codebase. Spawns specialized agents for OWASP Top 10, dependency vulnerabilities, secrets detection, and auth/authz review. Use before releasing to production or after major refactors touching auth or data handling."
context: fork
model_role: security-audit
user-invocable: true
allowed-tools: Read Grep Glob Bash
---

# Security Audit

Run a comprehensive parallel security audit across the codebase.

## Scope

$ARGUMENTS

If no scope was provided, audit the entire codebase. If a path was provided (e.g., `/security-audit src/auth/`), focus on that directory.

## Guard Check

Confirm git status is clean or note which files are uncommitted. Unstaged changes are included in the audit.

## Parallel Audit Agents

Launch all four agents concurrently in a single message:

1. **OWASP Top 10 Review** — Check for injection vulnerabilities, broken auth, insecure deserialization, security misconfiguration, XSS, CSRF.
2. **Dependency Audit** — Run `pip audit` or `npm audit`. Flag high/critical CVEs. Suggest pinned upgrades.
3. **Secrets Detection** — Search for hardcoded credentials, API keys, tokens, and passwords using grep patterns.
4. **Auth/AuthZ Review** — Trace authentication flows, check for privilege escalation paths, verify session management.

## Report

Aggregate findings into a severity-ordered report:
- CRITICAL: Immediate fix required before release
- HIGH: Fix within 24 hours
- MEDIUM: Fix in current sprint
- LOW: Track in backlog

Include file:line citations for every finding.
```

**Key features:** `context: fork` + `model_role: security-audit` for specialized routing, `user-invocable: true` for `/security-audit`, `allowed-tools: Read Grep Glob Bash` to restrict to read-only filesystem access, `$ARGUMENTS` with a guard check, parallel agent dispatch pattern.

---

## Working Examples in This Bundle

Five production skills in this bundle demonstrate the full range of patterns:

| Skill | Pattern | Key Features |
|-------|---------|-------------|
| **image-vision** | Reference / Tool Wrapper | Static body with companion files (`setup.md`, `patterns.md`, `examples/`); no fork; provides bash scripts for non-LLM work; `license: MIT` |
| **code-review** | Fork + Parallel Agents | `context: fork`, `model_role: critique`, `disable-model-invocation: true`; launches 3 parallel review agents via `delegate`; `$ARGUMENTS` for focus areas |
| **mass-change** | Fork + Orchestrator | `context: fork`, `model_role: reasoning`, `allowed-tools: Read Grep Glob Bash`; 3-phase workflow (research → plan → parallel workers); each worker creates a PR |
| **session-debug** | Fork + Specialist Delegation | `context: fork`, `model_role: general`, `disable-model-invocation: true`; immediately delegates to `session-analyst` agent; checks session config paths |
| **skills-assist** | Fork + Context-Sink Expert | `context: fork`, `model_role: general`, `user-invocable: true`; 4 companion reference files loaded on demand; synthesizes answers without inventing content |
