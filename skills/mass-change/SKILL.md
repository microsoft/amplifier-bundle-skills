---
name: mass-change
description: "Research and plan a large-scale change, then execute it in parallel across isolated agents that each open a PR."
context: fork
disable-model-invocation: true
user-invocable: true
model_role: reasoning
allowed-tools: Read Grep Glob Bash
---

# Batch: Parallel Work Orchestration

You are orchestrating a large, parallelizable change across this codebase.

## User Instruction

$ARGUMENTS

---

## Guard Checks — Run These First

**Check 1 — Arguments present.**
If `$ARGUMENTS` is empty or was not provided, output exactly this and stop:

```
Provide an instruction describing the batch change you want to make.

Examples:
  /mass-change migrate from react to vue
  /mass-change replace all uses of lodash with native equivalents
  /mass-change add type annotations to all untyped function parameters
```

**Check 2 — Git repository.**
Run `git rev-parse --is-inside-work-tree` in the current directory. If it fails or returns an error, output exactly this and stop:

```
This is not a git repository. The /mass-change skill requires a git repo because it spawns agents in isolated branches and creates PRs from each. Initialize a repo first, or run this from inside an existing one.
```

If both checks pass, proceed with the three phases below.

---

## Phase 1: Research and Plan

1. **Understand the scope.** Launch one or more research agents (using the delegate tool, in the foreground — you need their results) to deeply research what this instruction touches. Find all the files, patterns, and call sites that need to change. Understand the existing conventions so the migration is consistent.

2. **Decompose into independent units.** Break the work into 5–30 self-contained units. Each unit must:
   - Be independently implementable in an isolated context (no shared state with sibling units)
   - Be mergeable on its own without depending on another unit's changes landing first
   - Be roughly uniform in size (split large units, merge trivial ones)

   Scale the count to the actual work: few files → closer to 5; hundreds of files → closer to 30. Prefer per-directory or per-module slicing over arbitrary file lists.

3. **Determine the verification recipe.** Figure out how a worker can verify its change actually works end-to-end — not just that unit tests pass. Look for:
   - Browser-automation tools (for UI changes: click through the affected flow, screenshot the result)
   - CLI verification (for CLI changes: launch the app interactively, exercise the changed behavior)
   - A dev-server + curl pattern (for API changes: start the server, hit the affected endpoints)
   - An existing e2e/integration test suite the worker can run

   If you cannot find a concrete e2e path, ask the user how to verify this change end-to-end. Offer 2–3 specific options based on what you found (e.g., "Screenshot via browser automation", "Run dev server and curl the endpoint", "No e2e — unit tests are sufficient"). Do not skip this — the workers cannot ask the user themselves.

   Write the recipe as a short, concrete set of steps that a worker can execute autonomously. Include any setup (start a dev server, build first) and the exact command/interaction to verify.

4. **Write the plan.** Present:
   - A summary of what you found during research
   - A numbered list of work units — for each: a short title, the list of files/directories it covers, and a one-line description of the change
   - The verification recipe (or "skip e2e because …" if the user chose that)
   - The exact worker instructions you will give each agent (the shared template)

5. Present the plan for user approval before proceeding.

---

## Phase 2: Spawn Workers (After Plan Approval)

Once the plan is approved, spawn one agent per work unit using the delegate tool. **Launch them all in a single message block so they run in parallel.**

For each agent, the prompt must be fully self-contained. Include:
- The overall goal (the user's instruction)
- This unit's specific task (title, file list, change description — copied verbatim from your plan)
- Any codebase conventions you discovered that the worker needs to follow
- The verification recipe from your plan (or "skip e2e because …")
- The worker instructions below, copied verbatim:

### Worker Instructions

After you finish implementing the change:
1. **Code Review** — Invoke the /code-review skill to review and clean up your changes.
2. **Run unit tests** — Run the project's test suite (check for package.json scripts, Makefile targets, or common commands like `npm test`, `bun test`, `pytest`, `go test`). If tests fail, fix them.
3. **Test end-to-end** — Follow the verification recipe from the coordinator's prompt. If the recipe says to skip e2e for this unit, skip it.
4. **Commit and push** — Commit all changes with a clear message, push the branch, and create a PR with `gh pr create`. Use a descriptive title. If `gh` is not available or the push fails, note it in your final message.
5. **Report** — End with a single line: `PR: <url>` so the coordinator can track it. If no PR was created, end with `PR: none — <reason>`.

---

## Phase 3: Track Progress

After launching all workers, render an initial status table:

| # | Unit | Status | PR |
|---|------|--------|----|
| 1 | \<title\> | running | — |
| 2 | \<title\> | running | — |

As agent completion notifications arrive, parse the `PR: <url>` line from each agent's result and re-render the table with updated status (`done` / `failed`) and PR links. Keep a brief failure note for any agent that did not produce a PR.

When all agents have reported, render the final table and a one-line summary (e.g., "22/24 units landed as PRs").
