---
name: per-repo-conventions
description: >
  Use when starting work in any repository. Auto-surface when an agent is about
  to write code, create a PR, or verify work. Teaches the discovery pattern for
  finding and applying per-repo conventions (AGENTS.md, PR templates,
  CONTRIBUTING.md) before acting.
---

# Per-Repo Conventions

## The Principle

When you work in a repo, you're a guest. The repo's owners maintain conventions
that encode their experience — including bugs they have already paid for. Read
those conventions before you act.

The foundation/kernel layer defines philosophy. Individual repos define
specifics. The kernel does not know what a particular repo's smoke test
command is, what its PR checklist requires, or which gates its maintainers
consider non-negotiable. The repo does. Honor it.

## The Discovery Pattern

At the start of any task that touches a repo, before writing code, walk this
checklist:

1. **`AGENTS.md`** — check the repo root first, then walk up from the current
   working directory if you're working in a subdirectory. This is the
   highest-signal file for agent behavior in this ecosystem.
2. **`.github/PULL_REQUEST_TEMPLATE.md`** — check at repo root. This is the
   checklist your PR must honor.
3. **`CONTRIBUTING.md`** — check at repo root. General contribution
   conventions.

Skim each file that exists. Apply the relevant conventions to your work.

## Phase-specific files (JIT)

Some repos add files that are read only at specific phases of work, not at task
start. When `AGENTS.md` points to one of these, treat the trigger as binding:
load the referenced file when the phase fires, not before.

- **`PRINCIPLES.md`** — read at **design / planning phase**, before writing
  code. Captures philosophical context, architectural invariants, upstream-spec
  linkage, intentional deltas, and pointers to deeper material (ADRs, design
  docs). If present, `AGENTS.md` should point to it.
- **`SMOKE_TESTS.md`** — read at **verification phase**, before declaring done.
  Names the repo's smoke runnable(s) and any cross-repo smokes to run when
  changes affect dependents. If present, `AGENTS.md` and the PR template should
  point to it.

Force-loading these files at task start defeats the purpose — they exist
because their content is only sometimes relevant. If neither exists in the
repo, default behavior applies; the repo owner has chosen not to formalize
design or verification context separately yet.

## What Each File Contains

- **`AGENTS.md`** — agent-facing conventions. Test commands, common pitfalls,
  build steps, environment requirements, areas to avoid touching, and the
  shape of "done" in this repo. Often the only place where tribal knowledge
  is written down.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — the checklist that auto-populates
  every PR body. Treat each checkbox as a required action, not a suggestion.
- **`CONTRIBUTING.md`** — broader contributor guidance. Style, branching,
  review process, sign-off requirements.

## Applying Conventions

- When the repo says "run X before merging," run X.
- When the repo says "test with Y," use Y.
- When your defaults contradict the repo, the repo wins.
- Your PR body should reflect the repo's checklist — items checked, evidence
  linked, not blank boxes.

## What It Looks Like in Practice

```
I'm about to fix a bug in some-repo. Before writing code, I read:
- some-repo/AGENTS.md
    → "Smoke test required: ./scripts/smoke-test.sh on a fresh DTU"
    → "Engine changes require a live pipeline run, not just unit tests"
- some-repo/.github/PULL_REQUEST_TEMPLATE.md
    → "[ ] Smoke test passed (link log)"
    → "[ ] Live run exercising changed code path (link events.jsonl)"

My plan:
1. Implement the fix.
2. Run unit tests (necessary, not sufficient).
3. Run ./scripts/smoke-test.sh on a fresh DTU per AGENTS.md. Capture log.
4. Run a live pipeline exercising the changed path. Capture events.jsonl.
5. PR body addresses each checklist item explicitly with links to evidence.
```

The cost of this discovery pass is minutes. The cost of skipping it is the
integration-blocking bug the repo's conventions were written to prevent.

## Anti-Patterns

- **Skipping AGENTS.md because "I know how to fix this."** You may know the
  fix. You don't know the repo's gates. Read the file.
- **Filling out the PR template with empty checkboxes.** An unchecked box on
  a merged PR is a documented gap. Either do the work or remove the line.
- **Treating the repo's gates as optional suggestions.** The gate is there
  because someone already paid for the bug it prevents.
- **Re-discovering bugs the repo's conventions were designed to prevent.**
  If the checklist says "smoke test on fresh DTU" and you ship without one,
  you will discover why the line exists.
- **Working only from kernel/foundation docs.** Foundation can't name a
  specific repo's gates. The repo can.

## Cross-References

- `foundation:docs/PER_REPO_CONVENTIONS.md` — canonical statement of the
  principle.
- `skills/verification-discipline/` — the complementary skill that explains
  *why* per-repo gates (especially smoke and integration tests) matter and
  what "verified" actually means.
