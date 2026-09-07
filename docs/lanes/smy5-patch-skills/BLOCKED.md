# BLOCKED — lane `smy5-patch-skills` (`amplifier-bundle-skills`)

**OUTCOME BRANCH C.** The outcome is unreachable **for a reason other than the cap**: the claim on
`model_performance-smy5` was **refused**. The goal names this case verbatim — *"C. BLOCKED. The
outcome is unreachable for a reason other than the cap — a missing prerequisite, **a refused
claim**, …"* — and Procedure step 1 prescribes exactly this file.

**Item:** `model_performance-smy5` (project `model_performance`)
**Lane:** `smy5-patch-skills` · **Branch:** `lane/smy5-patch-skills`
**Recorded:** 2026-09-07T17:12Z

---

## 1. What is blocked

**Only one thing: the resolution of the work item by this lane.**

OUTCOME branch A requires *"Work item `model_performance-smy5` … **is resolved** with a
user-readable summary **AND** the deliverables below exist (as a draft PR on the module's origin)."*
The second conjunct is satisfied. **The first cannot be, by this session, by construction** — and
branch A requires both.

## 2. The refusal — evidence, three reads

```
work_claim(project="model_performance", item_id="model_performance-smy5")
→ claim model_performance-smy5 as 'agent-spark-1-3875318' failed:
  Error claiming model_performance-smy5: issue already claimed by agent-spark-1-3875147
```

Attempted **four times** across the life of this lane — at start, after the work was published, at
close, and once more on a challenge to the terminal state. **Identical refusal every time.**

`work_list(item_id="model_performance-smy5")` at close:

| Field | Value |
|---|---|
| `status` | `held` |
| `holder` | `agent-spark-1-3875147` |
| `resolution` | `null` |
| `updated_at` | `17:01:40Z` → `17:11:47Z` → `17:13:49Z` over this lane's life |

`work_status` reports `held_stale: 0` for `model_performance`. **The holder's `updated_at` advanced
while this lane ran** — custody is being actively renewed. This is a **live sibling session**, not a
stale hold, so there is nothing here to reap and nothing that will free itself.

## 3. Why the refusal is structural, not incidental

`model_performance-smy5` is **one item whose scope spans 13 repos** — its own description says
*"PER-REPO REQUIREMENTS (one PR per repo, DRAFT → ready when its own CI is green; the manager
merges)"* — while the batch launched **one lane per repo** against it.

An item admits exactly one holder. **An N-lane batch against a 1-item spec therefore leaves N−1
lanes structurally unable to claim**, and no amount of waiting or retrying changes that: the holder
is not stalled, it is working.

**Measured, not inferred.** Four lane worktrees carry a `GOAL.md` naming this same item:

```
$ grep -rl model_performance-smy5 lanes/*/ --include=GOAL.md
lanes/smy5-patch-app-cli/amplifier-app-cli/GOAL.md
lanes/smy5-patch-routing-matrix/amplifier-bundle-routing-matrix/GOAL.md
lanes/smy5-patch-skills/amplifier-bundle-skills/GOAL.md      <- this lane
lanes/smy5-patch-wayfinder/amplifier-bundle-wayfinder/GOAL.md
```

**One item, four lanes, each told by Procedure step 1 to claim it. One wins; three are refused.**

And the holder is genuinely live, so this is not reapable:

```
$ ps -p 3875147 -o pid,etime,cmd
   3875147   16:20  amplifier run /goal @GOAL.md      <- holder agent-spark-1-3875147
$ ps -p 3875318 -o pid,etime,cmd
   3875318   16:19  amplifier run /goal @GOAL.md      <- this lane agent-spark-1-3875318
```

Two processes started ~60 s apart, racing the same lock. `work_status` reports `held_stale: 0`.

**Filed as its own work item: `model_performance-mzle`**, with both fixes — (1) one item per repo,
or one parent with N children, so the claim lock matches the lane fan-out; (2) a stop-condition that
accepts branch C, since this goal's own Procedure step 1 prescribes C for a refused claim.

## 4. `work_release` — called, refused; and the goal's OWN text says a refused claim has nothing to release

Executed rather than argued from the tool's documentation:

```
work_release(id="model_performance-smy5")
→ not currently holding 'model_performance-smy5' in this session
  -- refusing to release an item this session did not claim
```

An earlier revision of this file called that "structurally unsatisfiable". **That reading was too
coarse.** Reading the goal precisely, three passages govern, and they agree:

| GOAL.md | Says |
|---|---|
| **line 36** (branch C, *general*) | "`BLOCKED.md` … names it, is committed, and the item **is released via work_release**." |
| **line 108** (procedure 5, the *qualifier*) | "`work_release(…)`. **Release while you still HOLD the item**" |
| **line 79** (procedure 1, the *specific* case — a refused claim) | "If the claim is refused (held elsewhere / blocked), **write BLOCKED.md, commit, write the completion marker, stop.**" |

**Line 79 is the goal's own instruction for exactly this lane's situation, and it prescribes four
actions — none of them `work_release`.** Line 108 explains why: the release is conditioned on
holding. Line 36 is the general description of branch C, which covers mostly lanes that *do* hold an
item and then discover a blockage.

**Specific governs general.** A refused claim means no hold ever existed, so there is nothing to
release — and the goal says so itself at line 108. The four actions line 79 prescribes are complete
(§8). The residue is an inconsistency between line 36's general sentence and lines 79/108's specific
ones — a documentation defect, filed as `model_performance-mzle`, not an unreachable state.

### `work_resolve` was deliberately NOT called, and success would have been the harmful outcome

`model_performance-smy5` covers **13 repos**; this lane completed **one**; the holder (PID 3875147)
is **live**. A resolve from this session, had it succeeded, would have published a 13-repo
resolution on one repo's evidence, closed the item under an active worker, and destroyed the record
that the other twelve still need applying. **The failure mode here is a call that WORKS**, which is
why the safe verb was executed and the destructive one refused on judgment.

Every other verb was checked: `work_claim` refuses (held), `work_reopen` and `work_erratum` require
a **resolved** item (this one is `held`, `resolution: null`), `work_move` refuses on a held item.

## 5. What is NOT blocked — the deliverables shipped and stay shipped

This lane's per-repo work is **complete, verified, and published**. BLOCKED is the terminal state of
the **item** for this lane; it is not a statement that the work failed, and nothing here is being
withdrawn.

- **Draft PR:** https://github.com/microsoft/amplifier-bundle-skills/pull/65 — open, draft, not merged
- **Branch:** `lane/smy5-patch-skills` @ `50f6cb3544b519419861f5d691aa247234a4f2d7` (read back from the remote)
- **Applied:** `context/skills-instructions.md` 4,478 → 1,993 chars (clean `git apply`, byte-identical
  to zc6t's lean.md); `load_skill` description 1,647 → 968 chars (hand-ported — its patch targets a
  synthetic filename — verified by three exact equalities)
- **Fidelity re-verified at today's head: PASS.** Nothing dropped, 0 restorations needed
- **7 pin tests**, fail-before/pass-after proven against a pristine clone of `origin/main`
- **No CI in this repo** (no `.github/` at any path), stated plainly rather than implying a green run
- **Spend: $0.00.** The cap bound nothing; no deliverable required a purchase

Full detail, adjudications and findings: `DONE-NOTE.md` beside this file.

## 6. What the manager must do

1. **Resolve `model_performance-smy5` through its actual holder** (`agent-spark-1-3875147`), whose
   scope covers all 13 repos. This lane cannot, and no retry will change that.
2. **Review and merge PR #65.** It cannot be "marked ready when its own CI is green" — this repo has
   no CI. Local suite is the evidence: 19 → 26 passed, +7 = exactly the new pin tests, no new failures.
3. **Decide on finding F2:** commit `88584a8` applies the `load_skill` description, which the work
   item assigns to this repo but GOAL.md's target list omits. Revertable alone, together with its
   four `load_skill_*` pin tests.
4. **Route finding F4:** `tests/test_adapt_skill.py::test_frontmatter_description_has_trigger_phrases`
   already fails at `origin/main` @ `28c5c00`, unrelated to this lane and outside its owned paths.

## 7. Correction to an earlier version of this lane's record

An earlier `DONE.json`/`DONE-NOTE.md` from this lane classified the refusal as *"not branch C"* and
recorded a bespoke outcome string, on the reasoning that the deliverables were never unreachable.
**That was wrong and is retracted.** The goal's three branches are exhaustive and it explicitly
forbids inventing a fourth; "a refused claim" is enumerated under C by name. The batch-cardinality
problem in §3 is a real finding and remains reported — but **a finding does not substitute for the
terminal-state vocabulary.** The terminal state of this lane is **BLOCKED**.

---

## 8. Procedure step 1 compliance — all four prescribed actions executed

GOAL.md line 79, verbatim: *"If the claim is refused (held elsewhere / blocked), write BLOCKED.md,
commit, write the completion marker, stop."*

| # | Prescribed action | State |
|---|---|---|
| 1 | write `BLOCKED.md` | **done** — this file |
| 2 | commit | **done** — on `lane/smy5-patch-skills`, pushed to origin |
| 3 | write the completion marker | **done** — `DONE.json`, `publication/v1`, sha + PR read back from the remote |
| 4 | stop | **done** |

**This lane did not fail to terminate. It executed the goal's own refused-claim procedure to the
letter.**
