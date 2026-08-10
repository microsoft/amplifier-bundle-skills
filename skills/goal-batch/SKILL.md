---
name: goal-batch
description: >
  Plan a batch of independent work into isolated lanes, get your approval, then
  run each lane as its own autonomous /goal session — one git worktree, one
  branch, one tmux session each — and verify and merge the results yourself.
  Use when work decomposes into pieces that can run at the same time: "run these
  in parallel", "goal-batch", "launch lanes for these", "work these N tasks
  simultaneously", "batch these as goals". Nothing launches until you have seen
  the lane split and said go. This is NOT fire-and-forget: the orchestrating
  session re-runs the full test suite itself after every merge and never accepts
  a lane's own claim that it finished. NOT for bounded edits that each end in
  their own PR — use mass-change for that. Requires git, tmux, the amplifier CLI
  on PATH, and the goalify and monitor skills.
user-invocable: true
argument-hint: "<the work to batch, or where it is enumerated>"
allowed-tools: [bash, read_file, write_file, edit_file, grep, glob, delegate, load_skill, todo]
model_role: general
---

# Goal Batch

Split large work into lanes that cannot collide, run each as an autonomous
`/goal` session in its own worktree, and land the results through a merge pass
you verify yourself.

You are the ORCHESTRATOR. You plan, launch, watch, verify, merge, report. You do
not do the lanes' work — if you catch yourself editing a lane's code mid-flight,
stop and fix the goal file or relaunch instead.

Every rule here was bought with a real failure across ~33 lanes of production
use. **The rules are field-tested; this file's exact sequencing is not — it has
driven few batches. Report what breaks.**

Shape references (plan screen, approval vocabulary, DONE.json, report) live in
`examples/plan-and-report.md`. This file is the rules.

**Invoking.** `/goal-batch <batch>` in the interactive TUI, or **"Use the
goal-batch skill and …"** in natural language — both load this skill reliably
(measured). What does NOT work is a bare `/goal-batch …` in a headless
`amplifier run "<prompt>"`: the model reads the token as prose and does the work
itself, producing plausible branches with no gate, no manifest, and no lanes.
Name the skill, or call `load_skill(skill_name="goal-batch", arguments=…)`.

**Running the companion scripts.** `load_skill` returns `skill_directory`.
Resolve every script from it — `<skill_directory>/scripts/<name>.sh` — and use
that absolute path. Never a bare relative path: the working directory is the
target repo, not the skill, and once this ships in a bundle the skill lives
under a hash-suffixed cache path that changes. **Never copy a script into the
target repo** — a real run did exactly that, leaving `.amplifier/bin/` behind as
untracked pollution in someone else's repository.

**Input** — `$ARGUMENTS`: the work to batch, or a pointer to where it is
enumerated. If lane independence is unclear, that is Phase 1's job, not a
question for the user yet.

---

## Phase 1 — Plan

Read enough to decompose honestly. Lanes each own a disjoint set of files, have
a provable outcome, and do not need a sibling to finish first.

Then do the work that decides whether this batch lands:

- **Collision analysis.** Map every candidate lane to the files it will touch
  and print the intersections. Where two lanes want the same file, FOLD THEM
  INTO ONE LANE, or assign sole ownership and have the other record its needed
  edit as a residual. Merging two lanes that would have collided is a win.
- **Pre-assign anything numbered** — issue IDs, task IDs, migration numbers.
  Parallel lanes *will* both grab the next free number. Two really did take 075.
- **Name the seams.** List files no lane owns. That is where it breaks: a
  packaging script nobody owned shipped broken because nobody tested it. Either
  give a lane the seam, or carry it to Phase 7 as untested.
- **Pin the base SHA** every lane branches from, and **record current test
  baselines** so "no regressions" is a number.

No lane cap. Width is bounded by the work.

## Phase 2 — Review and go

**The one mandatory stop. Nothing is created and nothing launches before the
user says go.**

Show the plan on one screen — lane table, contested files, parked items, unowned
files, per-lane time bound, watching mode. Fifteen seconds to read, one sentence
to argue with. Shape in `examples/`.

Ask questions ONLY where a wrong guess costs a relaunch: an ownership call you
cannot make from the code, a repo you are not sure you may push to, a
human-reserved action. Bring a plan, not a form.

**Approval is conversational.** Accept a bare `go`, and accept a `go` carrying
options — reporting cadence, per-lane time bounds, dropping a lane — and honor
them without re-asking. Anything that is not an affirmative is feedback: revise,
show the diff, re-present the gate. Never infer approval from enthusiasm,
repetition, or silence.

## Phase 3 — Compose the goal files

Load **goalify** and use it per lane; it owns outcome-first composition and
termination linting.

**Commit the goal files to the base commit before Phase 4 cuts any worktree**,
and pin `BASE_SHA` to that commit. Goal files written only into a worktree die
with it; goal files committed after the worktree exists are not in it, and the
launcher will refuse the lane.

Every goal carries:

- **The disjunctive exit, close to verbatim.** The load-bearing sentence — what
  makes lanes terminate honestly instead of spinning or declaring victory:

  > Complete when **either** every item reaches a terminal state, **or** it is
  > conclusively demonstrated the remainder cannot, naming the blocker for
  > each. Items ending FAIL or BLOCKED are residuals, not failures of the goal.

- **Terminal states** `PASS` / `FAIL-named` / `BLOCKED-named` / `PENDING-HUMAN`.
  `PENDING-HUMAN` is distinct on purpose: a lane that discharges a review by
  assigning it to a person has deferred, not finished, and Phase 7 must show
  that separately.
- **Working directory + branch + base SHA.** "Work ONLY here. Do not touch the
  main checkout or sibling worktrees."
- **File ownership** with the residual protocol: crossing into another lane's
  files is a defect, not a courtesy — record the needed edit and stop. Draw
  ownership around what makes the thing *work*, not around the artifact. A lane
  owning an icon but not the packager does not own a shippable icon.
- **Commit early, push always.** Two tmux-server crashes cost minutes instead of
  hours because every lane pushed as it committed.
- **Never merge to main.** The orchestrator merges.
- **Host capability limits, stated plainly.** A lane that authors what this box
  cannot compile ships code that breaks on someone else's first build. Live
  shared services are read-only evidence to a lane; tests use fixtures.
- **The time bound**, and that exceeding it is a terminal `BUDGET` state, not a
  reason to rush the work or skip the commit.
- **Write `DONE.json` in the worktree root as your final act** — the terminal
  marker. Without it, an exited session is indistinguishable from a killed one.
  Fields: `lane, verdict, branch, head, pushed, items[], residuals[],
  pending_human[], suite`. Shape in `examples/`.
- **KNOWN section** — env setup, suite commands, baselines, footguns. Speed
  aid, not criteria.

## Phase 4 — Preflight

Fail loud here. Never launch degraded.

- **Every lane repo has a reachable remote.** `git remote -v` plus a dry push. A
  lane with no remote is a lane whose work dies with the folder — one real run
  produced 47MB of genuine output into a remoteless repo and landed nothing in
  git. A waiver is the user's to give, in writing.
- **Smoke-test the launcher once**, ~90s, thrown away, and confirm any
  capability a lane depends on is reachable from inside a lane.
- **Create worktrees**, skipping any that already exist rather than failing on
  them — this path is re-entered on resume:
  `[ -d "$WT" ] || git worktree add -b <branch> "$WT" <BASE_SHA>`

**One worktree per lane is not optional.** The session workspace slug is derived
from the working directory, so lanes sharing a directory share a workspace and
their activity becomes unattributable.

## Phase 5 — Launch and register

One tmux session per lane, via the companion script:

```bash
scripts/launch_lane.sh <lane> <worktree> .amplifier/goals/<lane>.md \
                       gb__<batch>__<lane> /tmp/gb-<batch>-<lane>.log [timeout_s]
```

It prints a manifest row and enforces four things you must not reimplement by
hand: the tmux command contains **no user prose** (a lone apostrophe in a launch
note silently truncated a real launch — put launch notes INSIDE the goal file);
logging survives; the lane is wrapped in `timeout` in its own process group so a
runaway dies with its children; and it **fails loud** if no session ID appears,
rather than writing a blank into the crash anchor.

One-phase launch is mandatory. Never start a bare `amplifier` TUI and `send-keys`
the `/goal` into it — keystrokes sent to a busy pane get swallowed silently (one
run left an 8MB job with a zero-byte log), and `amplifier run` *exits* when the
goal loop ends while a TUI sits at a prompt forever, so one-phase is what makes
session death a real signal.

Both bounds are real but live at different layers: `--max-turns` is parsed by
**`/goal`**, not by `amplifier run`, so it rides inside the prompt string
(`/goal --max-turns 40 @file`); wall-clock is `timeout` around the process.
`/goal` is unlimited by default on purpose (ADR-0005) — a batch should set both.

**Session names `gb__<batch>__<lane>`** — double underscore because lane names
contain hyphens. Gives `gb__*` (every lane of every batch, for the orphan sweep
in Phase 7 and for pane-viewer match strings), `gb__<batch>__*` (one batch),
exact (one lane). Never use `.` or `:`: tmux silently rewrites them to `_` and
two differently-named lanes can collide.

**Write the manifest** — TSV, one row per lane: `lane · worktree · branch · tmux
· goal · log · session_id`, beside the goal files. This is the crash anchor.
When the tmux server dies, panes are gone but git plus this file let any session
reconstruct the batch; without it, recovery was 40 minutes of archaeology.

## Phase 6 — Watch

Load **monitor** for the polling discipline — it owns the SEQUENTIAL-ONLY rule
and the batched-imposter check. Delegate the loop per its Step 3 and give it
this batch's instrument:

```bash
scripts/batch_status.sh <manifest.tsv> <BASE_SHA>     # one line per lane, ~8ms each
SHOW_LAST=1 scripts/batch_status.sh <manifest.tsv>    # + last 3 turns per lane
```

**Monitors lied in every prior run because they were reading `tail -1` of a
TUI.** Give the watcher a real instrument and its job becomes mechanical. Three
signals are counter-intuitive and the script exists to encode them:

- Liveness is `events.jsonl` mtime, **not** `transcript.jsonl` mtime — the
  transcript freezes completely while a lane delegates to a sub-agent.
- Progress is assistant turns counted from the transcript, **not**
  `metadata.turn_count`, which is corrupt (reports 1 for a 21-turn session).
- Pushed is `git ls-remote`, **not** `@{upstream}`, never set by an
  explicit-refspec push.

Report per the mode approved in Phase 2. Interrupt regardless for: a lane
`DIED`, a lane asking a human a question, or the probe itself failing twice.
Stall thresholds (120s/900s) are starting guesses — calibrate before letting
`STALLED` justify killing anything.

**Verify the watcher's verdict yourself before acting on it.** Both false-DONE
and false-crash have happened.

**Provider rate-limit errors in a pane are healthy, not a stall.** If a lane
dies of them, that is a model-routing problem: switch the model and relaunch.
Do not serialize the batch.

**A lane that died — crashed, or killed by its time bound — takes the same
path:** rescue-commit anything real it banked, then relaunch the same goal with
a RESUME note naming what the prior attempt completed with SHAs, "treat that as
your own prior work, do not redo it", and what remains. Max 2 resumes. A lane
that hit its bound twice is a scoping problem — report it, do not extend
forever. Never let a bounded-out lane vanish silently from the Phase 7 report.

## Phase 7 — Land

**Re-verify everything. Lane self-reports are hints.** Two lanes reported green
honestly from a suite run that predated their own last file.

1. `git fetch`. Diff-stat each landed branch against main.
2. Merge **sequentially, ascending by churn, `--no-ff`**. Run the full suite
   yourself after EVERY merge. Verify actual test counts from result files, not
   "BUILD SUCCESSFUL".
3. On conflict: resolve per the lanes' own merge notes. If notes are missing or
   intents genuinely conflict, stop and surface it rather than guessing.
4. On red: fix at the cause, or revert that merge and report. Never weaken a
   test to pass — the gate is doing its job.
5. Push main. Then per lane: `git worktree remove`, delete branch local and
   remote, `tmux kill-session`. Sweep for orphans: `tmux ls -F '#{session_name}'
   | grep '^gb__<batch>__'` must come back empty.
6. Report verdict-first: per-lane table (shipped, SHAs, suite results), what
   verification caught that lanes did not self-report, residuals, anything
   `PENDING-HUMAN`, the unowned-files list from Phase 1, and new baselines.
