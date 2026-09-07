# Lane j1e6-ci-skills — DONE-NOTE

**Item:** `model_performance-2un7` — CI for `microsoft/amplifier-bundle-skills` (had none).
**Audit repair:** `model_performance-5587` — make the visibility guards visible by name in a
green run (see "Audit repair" below).
**Outcome branch: A (RESOLVED).** Every deliverable is DONE. No deliverable was cap-bound.
**Terminal word: RESOLVED.**

**PR:** https://github.com/microsoft/amplifier-bundle-skills/pull/68 (open, ready for review,
NOT merged — the manager merges).

---

## Deliverables

| # | Deliverable | State |
|---|---|---|
| 1 | `.github/workflows/ci.yml` running the real suite, ruff pinned, push:main + pull_request, no path filters / `continue-on-error` / `\|\| true` | **DONE** |
| 2 | Both run URLs quoted in the PR body; the RED one's job log shows the suite executing with a genuine **test** failure | **DONE** |
| 3 | Scratch PR closed and branch deleted — **verified**, not assumed | **DONE** |
| 4 | A statement of what the suite actually covers | **DONE** — see "Coverage" below. This repo has real tests; the labelled import-smoke fallback was not needed |
| 5 | Clean main red → STOP, report, fix as separate named commits | **DONE** — it was red **twice**; both fixed as their own commits (below) |
| 6 | Draft PR, marked ready when green, not merged | **DONE** |

## The CI

Four jobs, all free — no API keys, no LLM, ~2 min wall clock:

| Job | Command | Scale |
|---|---|---|
| `Lint (ruff)` | `uvx ruff@0.15.7 check .` | whole repo |
| `Tests — root` | `python -m pytest tests -q -ra --tb=short` on 3.11 / 3.12 / 3.13 | 27 tests |
| `Tests — modules/tool-skills` | `uv sync --frozen --extra remote-sources` then `python -m pytest -v -ra --tb=short` | 315 tests |
| `Bundle structure` | `.github/scripts/check_bundle_structure.py` | 41 YAML surfaces |

Plus `ruff.toml` at the repo root — without it *nothing* here pins a lint configuration (no
root `pyproject.toml`; `modules/tool-skills/pyproject.toml` has no `[tool.ruff]`), so
`ruff check .` walks up out of the repo looking for one and local/CI can silently disagree.

Shape taken: the **bundle-with-`modules/`** template
(`microsoft/amplifier-bundle-context-intelligence` per-module install + pytest, plus the
bundle-structure YAML parse), adapted with the no-root-package handling that
`microsoft/amplifier-bundle-routing-matrix` (`b4xs`) worked out — ephemeral `uv run
--no-project` for the root suite, since this repo is a bundle, not a Python package. All three
GitHub Actions pinned to full commit SHAs, each verified to be the SHA its version tag points
at (`gh api repos/<a>/git/ref/tags/<v>`).

## Coverage — what the suite actually covers

**342 tests total.** 341 execute on a stock runner; 1 skips with a printed reason.

- **Root `tests/` — 27 tests**, all file-reading assertions (pathlib + re, no imports from this
  repo): `.gitignore` contents, `bundle.md`'s foundation include, the `adapt-skill` SKILL.md
  structure, and the lean-head size/content pins from `smy5`.
- **`modules/tool-skills/tests/` — 315 tests**, the real unit suite for the `load_skill` tool:
  discovery, multi-source resolution, preprocessing, fork context inheritance, model-role
  resolution, the hook integration, and — the reason this lane exists — `#66`'s
  `test_visibility_budget.py` and `test_visibility_line_cap.py`, **which nothing had ever
  executed before this PR**.
- **1 skipped:** `tests/test_real_session.py::test_skills_visible_in_session` — see finding 2.
- **Bundle structure:** `bundle.md` frontmatter (+ its local include resolving to a real file),
  both `behaviors/*.yaml`, and all **38** `skills/*/SKILL.md` frontmatter blocks parsed and
  checked for `name` + `description`. An empty glob is a **failure**, not a pass.

The structure script was itself proven to fail: appending `a: [unclosed` to
`behaviors/skills.yaml` produced `FAIL -- 1 problem(s)` and exit 1; restoring it returned exit 0.

## The non-negotiable gate — the CI has been seen red

Scratch branch `scratch/j1e6-ci-red-proof`, one deliberately failing assertion in **each** suite,
draft PR #67.

**RED run:** https://github.com/microsoft/amplifier-bundle-skills/actions/runs/34156222957
(head `a75782262d056cae722b0fe11ff076d4b2f28d6b` — the exact workflow being shipped)

```
success  Lint (ruff)
success  Bundle structure
failure  Tests — modules/tool-skills : 1 failed, 314 passed, 1 skipped in 1.38s
failure  Tests — root (3.11)         : 1 failed, 27 passed in 0.06s
failure  Tests — root (3.12)         : 1 failed, 27 passed in 0.07s
failure  Tests — root (3.13)         : 1 failed, 27 passed in 0.05s
```

Lint and Bundle structure stayed **green** while the test jobs went red — so the red came from
the test job running the real suite, not from a setup or lint error, which would have proved
nothing. Full excerpts: `red-run-evidence.txt` beside this note.

An earlier red run on the same branch (34155658273) used the pre-`-ra` workflow and is what
surfaced finding 2; the branch was rebased onto the corrected workflow and re-run so the
quoted red is of the exact file being merged.

**Scratch cleanup — verified, not assumed:** PR #67 `state: CLOSED`;
`git ls-remote --heads origin 'scratch/*'` returns **nothing**.

**GREEN run:** https://github.com/microsoft/amplifier-bundle-skills/actions/runs/34156726801 —
all six jobs green on `fbeb717a4b2586912b184bf6f3a3529cb972f7be`.

## Audit repair (`model_performance-5587`) — the guards are now named in the green log

**The gap.** The workflow above genuinely ran the guard tests, but the module job invoked
`pytest -q`, so a green log reported only an aggregate — `314 passed, 1 skipped`. An aggregate
cannot prove any *particular* test ran: delete or rename `test_visibility_budget.py` /
`test_visibility_line_cap.py` and the number simply gets smaller while the run stays green.
That is the exact vacuous-green failure mode the rest of this CI was built to close, left open
in the one place this lane exists for.

**The change.** One character in one step, `ci: run the module suite with -v ...`
(`245b27ba9c6c39cac0c5b624a24fb85c349a7611`): the module job's
`python -m pytest -q -ra --tb=short` became `python -m pytest -v -ra --tb=short`. `-v` prints
one `path::test_name PASSED` line per test. **No test was changed, added, skipped or weakened;
`-ra`, `--tb=short`, the fixtures guard, the `--frozen --extra remote-sources` sync and every
other job are untouched.** The suite still runs in full — this changes only what the log reports.

**Readback from the remote green run** (not from the local run):
https://github.com/microsoft/amplifier-bundle-skills/actions/runs/34163453241 — all six jobs
`success` on `245b27ba9c6c39cac0c5b624a24fb85c349a7611`. Fetched with
`gh api repos/microsoft/amplifier-bundle-skills/actions/jobs/101869779846/logs`
(job `Tests — modules/tool-skills`); timestamps stripped, otherwise verbatim:

```
tests/test_visibility_budget.py::test_default_config_is_budget_mode PASSED [ 88%]
tests/test_visibility_line_cap.py::test_description_within_the_cap_is_verbatim PASSED [ 93%]
```

Those are the first line each guard file contributes. The same green log carries **15**
`tests/test_visibility_budget.py::` lines and **13** `tests/test_visibility_line_cap.py::`
lines — every test in both files, each individually named `PASSED`, `FAILED`/`ERROR` count 0.

**Full-suite result in that same green job, unchanged from before:**

```
======================== 314 passed, 1 skipped in 1.61s ========================
SKIPPED [1] tests/test_real_session.py:28: the `amplifier` CLI is not on PATH -- ...
```

**Confirmed installed, not merely configured.** PR #68 was squash-merged to `main` as `dbd5201`
while this readback was in flight, so the same evidence exists on `main` itself: push run
https://github.com/microsoft/amplifier-bundle-skills/actions/runs/34163943164, all six jobs
green on `dbd5201bd90aa2e88dd0814b40948388ef0c29a4`, job `Tests — modules/tool-skills`
(`101871165945`) carrying the identical **15** + **13** named guard lines and the identical
`314 passed, 1 skipped in 1.61s`.

Run locally first with the byte-identical command
(`uv run --frozen --extra remote-sources python -m pytest -v -ra --tb=short` in
`modules/tool-skills`): exit 0, `315 passed` — 315 rather than 314 because the `amplifier` CLI
*is* on PATH on this machine, which is finding 2 above behaving exactly as designed.

## Clean main was red — twice. Neither papered over.

**Finding 1 — `ruff check .`: 3 genuine E741 findings on untouched main.** Ambiguous variable
name `l` in two archived lane-artifact scripts under
`docs/lanes/z6wa-skills-visibility-renderer/`. Fixed as its own commit (`fix(lint):`) with pure
loop-variable renames. Excluding `docs/` or narrowing the rule selection would have been the
same vacuous-green move as `continue-on-error`, so neither was done.

**Finding 2 — `tests/test_real_session.py` dies on any clean checkout.** Found by the first
red-proof run:

```
FAILED tests/test_real_session.py::test_skills_visible_in_session
  - FileNotFoundError: [Errno 2] No such file or directory: 'amplifier'
```

The test shells out to the `amplifier` CLI — a separate application
(`microsoft/amplifier-app-cli`) that is deliberately **not** a dependency of
`amplifier-module-tool-skills`. The dependency was never declared, so the test only ever passed
on a machine where the developer happened to have the CLI installed. This is the single most
useful thing this lane found: it was invisible precisely *because* there was no CI.

Fixed as its own commit (`fix(tests):`) by making the dependency explicit —
`shutil.which("amplifier")` → skip with a reason naming why. **Rejected alternative:**
installing app-cli from git in the module job, which would couple this module's CI to another
repo's `main` — the same "unrelated upstream change turns your PR red" failure mode the pinned
ruff version exists to avoid.

Because **a skip is green**, both test jobs now run pytest with `-ra`, printing every
non-passing outcome and its reason into the job log. Verified present in both the red and green
runs:

```
SKIPPED [1] tests/test_real_session.py:28: the `amplifier` CLI is not on PATH -- ...
```

## Decisions taken without asking (no human wait)

1. **ruff pinned to 0.15.7**, not routing-matrix's 0.15.11 — 0.15.7 is what this repo's own
   committed `modules/tool-skills/uv.lock` resolves, so CI lints with exactly the ruff a
   contributor gets from `uv sync` there. Both versions report identically on this tree
   (3 findings before the fix, 0 after), so the choice costs nothing and buys local/CI identity.
2. **`ruff format --check` NOT wired.** At 0.15.7 defaults it would rewrite **19 of 56 files**.
   That whitespace normalisation does not belong in the PR introducing CI — it would collide
   with every in-flight branch. Named in the workflow so the next contributor sees a decision,
   not an oversight.
3. **No LLM-backed validation**, per the item. Skills are prose and the temptation is real, but
   it needs keys and costs money per run.
4. **Two guards added that the template did not have**, each converting a silent weakening into
   a red run: `test -d tests/fixtures/skills` (nine tests self-skip without it), and `-ra` on
   both pytest invocations.
5. **`skills/*/SKILL.md` frontmatter added to the structure check** beyond the item's stated
   `bundle.md` + `behaviors/*.yaml`. It is the payload of a *skills* bundle: a skill whose
   frontmatter does not parse is invisible at runtime and nothing else in this repo notices.
6. **`uv sync --frozen --extra remote-sources` is mandatory**, measured: without the extra,
   `amplifier_foundation` is missing and pytest **aborts collection** rather than failing a test.

## Spend

**$0.00 of a $0.00 authority.** Arithmetic as stated in the goal: `0 runs x 0 arms x $0 / 1.00
= $0.00`, slack `$0.00`. This deliverable buys no API calls, no DTU, no containers — GitHub
Actions minutes only, which the authority explicitly permits. **The arithmetic closes**: the
deliverable's cost is structurally zero, so there is no cap-bound gap and no OUTCOME-branch-B
finding to report. No API keys were used, no infrastructure was created, so nothing was
registered in the infra ledger and nothing needed tearing down.

CI minutes actually consumed: 4 runs x 6 jobs (~2 min wall clock each run) — the fourth being
the audit-repair readback run 34163453241. The `-q` -> `-v` change adds ~300 log lines per run
and no measurable time (1.61s vs 1.52s for the same suite).

## What remains open (for whoever picks this up)

1. **The merge.** Procedure 4 forbids this lane to merge; PR #68 is ready for review. After
   merge, confirm `main` HEAD reports a successful check-run — *configured is not installed*.
2. **`ruff format`** is a mechanical follow-up: `uvx ruff@0.15.7 format .`, 19 files.
3. **`test_real_session.py` now skips in CI.** If the amplifier CLI smoke is considered
   load-bearing, the honest way to restore it is a separate job that installs app-cli
   explicitly — with eyes open about coupling this repo's CI to another repo's `main`.
