---
name: verification-discipline
description: >
  Use when verifying that completed work actually works. Auto-surface during
  /verify mode, post-implementation review, or before claiming a task is done.
  Teaches the discipline of testing outcomes vs implementation, the
  unit/integration/smoke gradient, and what "done" actually means.
---

# Verification Discipline

## The Principle

Unit tests verify that **code-as-written behaves as-written**. Smoke and
integration tests verify that **the system achieves the intended outcome**.
Those are different questions. You need both.

"All unit tests pass" is necessary. It is rarely sufficient. A finding from
the field: four consecutive integration-blocking bugs, all of which passed
unit tests, all of which would have been caught by a five-minute smoke test
on a fresh environment. The bugs were not exotic — they were the cost of
declaring "done" too early.

## The Four Failure Modes

1. **Tests written from the implementation outward miss scenarios the code
   doesn't anticipate.** The engineer writes code, then writes tests that
   exercise the code as written. The tests ask "does this code do what I
   wrote it to do?" They don't ask "what scenarios does the system need to
   handle?"
2. **Mocks verify shape, not behavior.** A mocked dependency returns the
   value you told it to return. That tells you nothing about whether the
   real dependency would have behaved that way.
3. **Tests in isolation miss integration boundaries.** Component A passes.
   Component B passes. Their interaction at the seam fails. The seam was
   never tested.
4. **Happy-path tests pass while activated code paths fail.** A
   golden-file test verifies that the default (un-activated) configuration
   renders correctly. The activated configuration — the one production
   actually uses — was never exercised.

## The Verification Gradient

Treat verification as a ladder. Skip a rung and you discover its bugs in
production.

| Tier | What it verifies | Example |
|---|---|---|
| 1. Unit | Code does what I wrote it to do | `pytest tests/unit/` |
| 2. Integration | Component pairs interact correctly | `pytest tests/integration/`, real DB |
| 3. Smoke / E2E | System achieves the user-visible outcome | Fresh DTU launch, run real pipeline, observe artifacts |
| 4. Production-equivalent | Real environment, real load, real data | Staging deployment, canary, replay traces |

Each tier catches bugs the tier below it cannot. Each tier costs more time
than the tier below it. The economic choice is not "skip the expensive
tiers." The economic choice is "spend five minutes on tier 3 to avoid five
hours of rollback."

## What "Done" Actually Means

Before claiming a task is done, satisfy this checklist:

- [ ] Code does what I wrote it to do (unit tests pass).
- [ ] Code interacts correctly with other components (integration tests
      pass, or — if no integration tests exist for this code path — a
      manual integration check is documented).
- [ ] The system achieves the user-visible outcome (smoke or E2E test
      passed, ideally on a fresh environment).
- [ ] Repo-specific gates from `AGENTS.md` and `.github/PULL_REQUEST_TEMPLATE.md`
      are satisfied.
- [ ] Evidence is **observable** — log file, screenshot, output excerpt,
      events.jsonl analysis. Not "tests pass." Not "looks right."

If any box is unchecked, the work is not done. Say so, explicitly.

## Tests-From-Outcomes Pattern

Different from classic TDD. TDD writes unit tests first. Tests-from-outcomes
writes the outcome assertion first.

```
1. Before writing implementation, write down the user-observable outcome.
   "After running this pipeline, events.jsonl contains a `branch_completed`
    event for each branch and no `contract_violation` events."

2. Write a test asserting that outcome. The test runs the real pipeline,
   inspects the real events.jsonl, checks the real conditions.

3. Implement code until the test passes.
```

Both patterns are valuable. Unit-level TDD verifies internal correctness.
Outcome-level testing verifies that the system behaves as the user expects.
Use both.

## Anti-Patterns

- **"All unit tests pass, so we're done."** Usually wrong. The unit tests
  verified the code you wrote. They did not verify the system you shipped.
- **Mocking the very thing the test is supposed to verify.** If the
  question is "does the database client retry correctly?" and you mock the
  database client's retry method, you have tested nothing.
- **Skipping smoke tests because they're slow.** A five-minute smoke test
  is cheaper than a five-hour rollback.
- **Verifying that the code compiles, not that it works.** "It builds"
  ≠ "it runs." "It runs" ≠ "it does the right thing."
- **Claiming "verified" without producing evidence.** Evidence is a log, a
  screenshot, an artifact diff, an events.jsonl excerpt. "I checked" is
  not evidence.
- **Treating CI green as proof.** CI runs what CI is configured to run.
  If CI has no integration tier, CI green tells you only that the unit
  tier passed.

## The Pattern That Emerged from the Field

Four integration-blocking bugs in four consecutive shippings. All would have
been caught by a smoke test on a fresh environment. None were caught by the
unit tests that did exist, because the unit tests asked the wrong question.

The fix:

- Smoke test as a **PR gate**, not an aspiration.
- The PR template encodes that gate — it auto-populates in every PR body.
- Reviewers see unchecked boxes immediately and refuse to merge without
  evidence linked next to each box.

Cultural change is hard. Changing the form is easy. Change the form first.

## Cross-References

- `skills/per-repo-conventions/` — how to discover the specific gates a
  given repo requires (AGENTS.md, PR template, CONTRIBUTING.md).
- `foundation:docs/PER_REPO_CONVENTIONS.md` — canonical principle for
  per-repo discovery.
- `skills/integration-testing-discipline/` — concrete tactics for running
  the integration tier (observe first, fix in batches, expect long
  durations).
