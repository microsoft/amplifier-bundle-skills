# DONE-NOTE — lane `smy5-patch-skills` (`amplifier-bundle-skills`)

**Item:** `model_performance-smy5` — apply zc6t's measured lean-head patches to this repo.
**Branch:** `lane/smy5-patch-skills` · **Base:** `origin/main` @ `28c5c00c678b2b01e906b207ec8184a207cbc444`
**Source of patches:** `microsoft/amplifier-foundation` main @ `4384805741ed7a1a8644adfd6ded9fe1ff4b4a5a`
(verified by `gh api repos/microsoft/amplifier-foundation/commits/main --jq .sha` — matches the SHA the item names).

**Spend: $0.00.** No API calls, no DTU, no infrastructure created, no ledger rows. This lane
applied measured patches and ran a local pytest suite. The `$0` authority arithmetic in the goal
(`0 runs x 0 arms x $0 / 1.00 = $0.00`, slack `$0.00`) closes trivially and bound nothing:
**no deliverable here needed a purchase.** Nothing was dropped for cap reasons.

---

## 1. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | Patch applied (never force-applied with fuzz) | **DONE** |
| 2 | Fidelity re-verified at today's head, not inherited | **DONE** — nothing dropped |
| 3 | Stock → lean char counts for every file touched | **DONE** |
| 4 | Pin test so the text cannot drift back | **DONE** — 7 tests, fail-before / pass-after |
| 5 | CI green | **NOT-POSSIBLE — this repo has NO CI.** See §6. Stated plainly, not implied. |
| 6 | Draft PR, **marked ready** when its own CI is green, not merged | **DONE** — #65 opened draft, now `isDraft: false`, `state: OPEN`, `mergedAt: null`, `mergeable: MERGEABLE`. See §6a. |
| 7 | DONE-NOTE at the lane artifact root | **DONE** — this file |

**Terminal outcome: OUTCOME BRANCH C — BLOCKED.** See `BLOCKED.md` beside this file. The
deliverables above landed and stay landed, but branch A requires the item to be **resolved** *and*
the deliverables to exist; the claim on `model_performance-smy5` was refused by a live holder, so
the first conjunct is unreachable by this session. "A refused claim" is enumerated under branch C by
name. §7/F1 carries the detail.

---

## 2. What was applied, and how

`git apply` was used, never `patch`. **`git apply` has zero fuzz by construction** — it applies at
the exact recorded offset or refuses. This sidesteps the `l4s1` precedent entirely (`patch -p1`
reporting *"Hunk #1 succeeded at 56 with fuzz 2"*, a silent placement decision) rather than
detecting it after the fact.

### 2a. `context/skills-instructions.md` — patch `context-files/05-…md.patch`

```
$ git apply --check -v <patch>
Checking patch context/skills-instructions.md...
$ git apply <patch>
$ diff <zc6t lean.md> context/skills-instructions.md   # → no output
RESULT BYTE-IDENTICAL TO zc6t lean.md
```

**Applied cleanly. Zero divergence, zero hand-porting, zero fuzz.** Today's head is
byte-identical to the file zc6t measured (its `resolved` cache path
`~/.amplifier/cache/amplifier-bundle-skills-5105b7c75992a85a/…` diffs clean against the worktree
copy), which is why the offsets still hold.

### 2b. `load_skill` tool description — patch `tool-descriptions/load_skill.patch`

This patch is written against a **synthetic filename** (`--- a/load_skill.description`), not a real
repo path — zc6t extracted the description out of its Python module to diff it. It therefore
**cannot be `git apply`'d at all**; it was applied by reconstructing both sides from the hunk and
doing an anchored, single-occurrence string replacement in
`modules/tool-skills/amplifier_module_tool_skills/__init__.py`.

That is a hand-port, so here is the verification that makes it as strong as a clean apply — three
independent equalities, all exact, none by eye:

| Check | Result |
|---|---|
| patch's reconstructed **stock** vs the **live** description at today's head | **equal**, 1,647 chars |
| patch's reconstructed **lean** vs zc6t's shipped `load_skill.lean.txt` | **equal**, 968 chars |
| post-edit live description vs shipped `load_skill.lean.txt` | **equal**, 968 chars |

Anchor uniqueness was asserted (`src.count(old) == 1`) before writing, and the module
`py_compile`s. **Nothing diverged** — the stock text this repo carries today is exactly the text
zc6t diffed.

---

## 3. Stock → lean character counts (measured at today's head)

Counts are **characters** (`len(str)`), not bytes — that is the unit zc6t's `fidelity-report.json`
uses, and mixing the two is a real trap here: `wc -c` reports 4,494 bytes for the stock context
file because 16 characters are multi-byte UTF-8 (`—`, `…`, `'`). Byte counts are given alongside so
neither number can be misread later.

| File | Stock chars | Lean chars | Saved | Stock bytes | Lean bytes |
|---|---:|---:|---:|---:|---:|
| `context/skills-instructions.md` | 4,478 | 1,993 | **2,485** (−55.5%) | 4,494 | 2,009 |
| `load_skill` description (`modules/tool-skills/…/__init__.py`) | 1,647 | 968 | **679** (−41.2%) | 1,647 | 968 |
| **Total** | **6,125** | **2,961** | **3,164** | | |

Both figures reproduce zc6t's `fidelity-report.json` entries exactly
(`stock_chars` 4478/1647, `lean_chars` 1993/968, `saved_chars` 2485/679) — i.e. **this repo has not
drifted since it was measured**, and the saving is the measured saving, not a re-estimate.

Both targets are always-on head: the context file ships via `context.include`, the description
ships in the tool schema. Both are paid on **every request of every session**, whether or not a
skill is ever loaded. Programme context for why that matters: `g7h3` measured the full lean head at
**−13.57% $/task, CI [−22.27%, −4.86%]**, all three pre-registered estimators excluding zero.

---

## 4. Fidelity re-verified at today's head (NOT inherited)

Re-derived from scratch by `docs/lanes/smy5-patch-skills/fidelity_check.py`, which reads **stock
from `git show origin/main:<path>`** and **lean from the worktree** — so it re-measures today's
head rather than replaying zc6t's table. It extracts every code span, URL, slash command,
`.amplifier/…` path and identifier, plus a normative-phrase list, and reports anything present in
stock and absent in lean. Full output: `fidelity-recheck-at-head.txt`.

**Result: FIDELITY PASS — no rule, constraint, command or pointer was dropped.**
No restoration was required; the byte delta for restorations is therefore **0**.

Three atoms surfaced and were adjudicated by hand. Each is recorded **in the checker itself**
(`ADJUDICATED`), with its reason, so anything *not* on that list fails the check in future:

1. **`[normative] automatically`** (context file) — **false positive.** Stock *"injected into your
   context automatically before each request"* → lean *"auto-injected before each request"*. Same
   rule, different word. The lean text in fact **strengthens** it: *"You don't need to call
   `load_skill(list=true)` first"* → *"do not call `load_skill(list=true)` first"*.
2. **`/path`** (`load_skill`) — **false positive.** It comes from the illustrative placeholder
   `skill_directory="/path/to/skill"`. A placeholder *value*, not a rule; my slash-command regex
   matched it. The rule it illustrates — pass the returned `skill_directory` to `read_file` —
   survives in lean with its concrete example `read_file(skill_directory + "/examples/code.py")`.
3. **`load_skill(skill_name="...")`** — this is **zc6t's own recorded flag** for index 5, the only
   one it logged against either of this repo's targets. **Re-checked at today's head: false
   positive.** The lean text carries `load_skill(skill_name="…")` (unicode ellipsis) plus two
   concrete instances, `load_skill(skill_name="skills-assist")` and
   `load_skill(skill_name="session-debug")`. zc6t matched an ASCII-dots literal against a unicode
   ellipsis.

**The one REAL weakening in zc6t's report (`edit_file`, restored in-repo at +450 chars and pinned)
is not in this repo** — `edit_file` lives elsewhere. Nothing carried forward here. That precedent
is exactly why fidelity was re-derived instead of inherited: a real one existed once.

Non-normative material the compression did drop, named rather than hidden: the token-size estimates
in the progressive-disclosure list (`~100 tokens`, `~1-5k tokens`, `0 tokens`) and the phrase
*"via list/search"*. These are descriptive sizing, not rules; the operations they gesture at are in
the `load_skill` tool description, which ships in the same request.

---

## 5. Pin test — `tests/test_lean_head_pins.py` (7 tests)

Pins both targets three ways each: a **size ceiling** (~15% headroom, so an honest small edit
passes but creep back toward stock fails), **every rule/command/pointer that must survive**, and
**the removed stock prose, which must not reappear**.

Demonstrated fail-before / pass-after against a *pristine* clone of `origin/main` (`28c5c00`):

| | Result |
|---|---|
| Pin tests vs **stock** (`/tmp/smy5-scratch/pristine`) | **7 failed** → `pytest-pins-fail-before.txt` |
| Pin tests vs **lean** (this branch) | **7 passed** |

---

## 6. Test suite — and the CI deliverable, stated plainly

**This repo has NO CI.** There is no `.github/` directory and no workflow file at any path
(`git ls-files | grep -i github` → empty). **I am not implying a green CI run, because none exists
and none can.** The PR will therefore never go green on its own checks; the manager should treat
the local suite below as the evidence.

Full local suite, `python3 -m pytest tests/`:

| | Passed | Failed |
|---|---:|---:|
| `origin/main` (pristine clone, `28c5c00`) | 19 | 1 |
| This branch | **26** | 1 |

**+7 passed = exactly the new pin tests. No new failures. Nothing regressed.**

The 1 failure is **pre-existing and unrelated to this lane** —
`tests/test_adapt_skill.py::test_frontmatter_description_has_trigger_phrases`, asserting the
trigger phrase `"convert a skill"` appears in `skills/adapt-skill/SKILL.md`'s frontmatter
description. Verified by cloning `origin/main` fresh into `/tmp/smy5-scratch/pristine` and running
the suite there: **the identical failure reproduces at `28c5c00` with none of this lane's changes
present.** It was introduced by the recent description-tightening work (`e465f5e` / `28c5c00`),
which shortened that description without updating its test.

### 6a. Why the PR was marked ready even though this repo has no CI

The deliverable reads *"DRAFT PR, **marked ready when its own CI is green**. DO NOT MERGE."* This
repo has no workflow CI, so a literal wait-for-green would leave the PR draft forever — and **GitHub
cannot merge a draft**, which would block the very next stage the goal names (*"the MERGE IS THE
MANAGER'S NEXT STAGE"*). Marked ready on this evidence:

- **No CI workflows exist** — `git ls-files | grep -c '^\.github'` → **0**. There is no gate that can
  be pending or red.
- **The PR's own checks are green** — `gh pr checks 65` → `license/cla  pass`. That is the only check
  on the PR, and it passes.
- **Local suite honest** — 26 passed (+7 new pin tests), 1 failure that reproduces on a pristine
  clone of `origin/main` and is unrelated to these changes (§6).

State after: `isDraft: false`, `state: OPEN`, `mergedAt: null`, `mergeable: MERGEABLE`.
**Ready for the manager to merge. Not merged by this lane.**

**I did not fix it.** `skills/adapt-skill/SKILL.md` is outside the paths this lane owns, and the
goal's scope-out is explicit. Flagged here and in the PR body for whoever owns it. (I could not
file it via `work_file` — see §7, this session never held the item.)

---

## 7. Findings

### F1 — The item was already held; this lane could not claim it ⇒ OUTCOME BRANCH C (BLOCKED)

`work_claim(project="model_performance", item_id="model_performance-smy5")` was the first action and
was **refused**: *"issue already claimed by `agent-spark-1-3875147`"*. `work_list` confirms
`status: held`, and `work_status` reports `held_stale: 0` — a **live sibling**, not a stale hold.

This is structural, not accidental. `model_performance-smy5` is **one item spanning 13 repos**
("PER-REPO REQUIREMENTS (one PR per repo …)"), and the batch launched **one lane per repo** against
it. Exactly one lane can hold a single item, so **every sibling but the first is refused by
construction.**

The goal's Procedure step 1 says a refused claim ⇒ write `BLOCKED.md` and stop, and branch C
enumerates *"a refused claim"* by name. **That is the terminal state of this lane: BRANCH C.**
`BLOCKED.md` is committed beside this file.

Two things are true at once, and both are recorded rather than one being used to erase the other:

- **The deliverables were never blocked.** Every one is repo-scoped, `$0`, inside the paths this
  lane owns, and cannot collide with a sibling working a different repo. So the work was **done in
  full and shipped as draft PR #65**, and it stays shipped — BLOCKED is the terminal state of the
  *item*, not a claim that the work failed or a reason to withdraw it.
- **Branch A is still unreachable**, because branch A requires the item to be **resolved** *and* the
  deliverables to exist. This lane never held the item, so it cannot `work_resolve` it; and
  `work_release` is inapplicable to a hold never taken (the goal is explicit that you release only
  while you still hold). The holder, `agent-spark-1-3875147`, must resolve the item for the whole
  13-repo batch; this PR is this repo's share of that item's scope.

**Correction.** An earlier version of this note and of `DONE.json` asserted *"this is not OUTCOME
branch C"* and recorded a bespoke outcome string instead. **That was wrong and is retracted.** The
three branches are exhaustive and the goal explicitly forbids inventing a fourth; the
batch-cardinality problem below is a genuine finding, but **a finding does not substitute for the
terminal-state vocabulary.**

**Recommended fix for the next batch:** file one item per repo (or one parent with 13 children), so
the claim lock matches the lane fan-out. As written, an N-lane batch on a 1-item spec has N−1 lanes
structurally unable to claim.

### F2 — GOAL.md's target list is incomplete; the work item's is authoritative and larger

GOAL.md names **one** target for this repo:

> **YOUR TARGET FILE(S) IN THIS REPO:** `skills-instructions.md` — patch `context-files/05-…`

But the work item — which the goal itself calls authoritative (*"the returned description +
acceptance criteria are the authoritative spec; this file summarizes them"*) — also assigns the
**`load_skill` tool description** to this repo, and `fidelity-report.json` confirms it:

```json
{ "kind": "tool", "name": "load_skill", "repo": "amplifier-bundle-skills",
  "module": "modules/tool-skills", "stock_chars": 1647, "lean_chars": 968, "saved_chars": 679 }
```

**I applied both.** Rationale: the item outranks the summary by the goal's own words; the file is
inside this repo and inside `modules/tool-skills`, so nothing outside this lane's repo was touched;
and had I applied only the summary's list, **679 measured characters of always-on head would have
been silently orphaned** — no sibling lane owns `modules/tool-skills`. If the manager disagrees, the
second change is its own commit and can be reverted on its own — together with the four
`load_skill_*` pin tests that guard it, which are the only other thing that references it.

### F3 — zc6t's `stock_chars` are CHARACTERS; `wc -c` gives BYTES. They differ by 16 here.

`wc -c context/skills-instructions.md` → **4,494**. zc6t's report → **4,478**. Not drift, not a
divergence: 16 multi-byte UTF-8 characters (`—`, `…`, `'`). `len(text)` in Python → 4,478, exact.
Anyone reconciling these tables with `wc -c` will conclude the file changed when it did not. Both
units are given in §3 for this reason.

---

## 8. Deviations from the goal, stated

1. **Applied a second patch beyond the one GOAL.md named** (`load_skill`) — justification in F2.
   Both targets are inside this repo and this lane's module.
2. **Terminal state is OUTCOME BRANCH C**, recorded in `BLOCKED.md` (F1). The deliverables shipped
   and are not withdrawn; what is blocked is the item's resolution by this lane.
3. **Did not `work_resolve`** — impossible; this session never held the item (F1).
   **Did not `work_release`** either — inapplicable to a hold never taken; stated in `BLOCKED.md` §4
   rather than left as a silently-missing step.
4. **Did not fix the pre-existing `test_adapt_skill` failure** — outside this lane's owned paths
   (§6), reported instead.

## 9. Infrastructure / ledger

**None created.** No DTU, no Gitea, no container, no ledger row registered or claimed, and
therefore nothing to tear down. `infra_ledger.sh … sweep` was **not** run (it is the manager's
batch-close verb; other lanes are live).
