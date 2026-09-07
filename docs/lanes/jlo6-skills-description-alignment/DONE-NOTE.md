# DONE-NOTE — model_performance-jlo6

**Apply the shipped skills-bundle description-alignment patch (personafy /
skillify / councilify / skills-assist).**

Terminal outcome: **A — RESOLVED, at the LANDING STAGE.** Every deliverable is
DONE. Nothing was recorded NOT-POSSIBLE; nothing was blocked. The final state of
this work requires a merge, which this lane may not perform, so it ships as a
**draft PR** — <https://github.com/microsoft/amplifier-bundle-skills/pull/70>;
the merge is the manager's next stage. Spend against the $0 authority:
**$0** (§8).

---

## 1. What this closes

`model_performance-pwmy` (foundation PR #373, merged `5f0f04b`) moved the
description rules from convention to enforcement in foundation's validators.
The half of that work living in **this** repo — the creation skills that *emit*
descriptions — could not be committed by that lane, because this repo was held
at the time. It shipped drop-in patches as an artifact instead:

    amplifier-foundation: docs/lanes/pwmy-principles-to-tooling/patches/
                          skills-bundle-description-alignment.md

Read from `origin/main` at `cfd0e23`. All four patches are now applied.

The defect was concrete, not hypothetical: `personafy` step 7 *instructed* a
`description:` "at or below ~700–800 characters" — nearly 2× the enforced
400-char skill cap — and named `crusty-old-engineer`/`cranky-old-sam` as the
calibration target. The creation skill was emitting the defect by design.

---

## 2. Deliverables

| Deliverable | State |
|---|---|
| The four patches applied; the four files no longer instruct a cap above 400 | **DONE** — §3 |
| Clean-room `skillify`/`personafy` runs emit descriptions with zero WARNINGs, quoted char counts | **DONE, with one honest negative** — §5 |
| Explicit statement on the already-over-cap existing descriptions | **DONE — DEFERRED, not swept** — §6 |
| CI green where the repo has CI | **DONE — this repo has no CI** — §7 |
| Draft PR, not merged | **DONE** — see DONE.json |
| DONE-NOTE at the lane artifact root | this file |

---

## 3. The four patches

| # | File | Change | Deviation from the artifact |
|---|---|---|---|
| 1 | `skills/personafy/SKILL.md` step 7 | Both the measurement paragraph and the success criterion now name **400 chars, ERROR at 800**, cite `validate-bundle-repo.yaml` Phase 2.82, and say the 1024-char spec ceiling is *not* the operative limit. The "calibrate against siblings" instruction is replaced with "the siblings are the drift, not the standard". | The artifact's success-criterion text quotes **13 of 31 / 4 over 800**. This repo now measures **17 of 38 / 7 over 800** (§4) — the applied text carries **this repo's own current numbers**, not the stale ones. |
| 2 | `skills/skillify/SKILL.md` step 4 | The emitted template's `description:` guidance is replaced (trigger → USE WHEN → DO NOT USE WHEN; **HARD CAP 400, ERROR at 800**; zero `<example>`/`<commentary>`), and the measure-before-you-hand-it-back command is added. | The artifact says "add immediately after the template block". Placed instead at the **end of the same step**, after the step-annotation and frontmatter-rules subsections that belong to the template, immediately before the step's Success criteria — the same step, the actionable position. The step's Success criteria now also names the 400-char bar. |
| 2b | `skills/skillify/SKILL.md` frontmatter rules | **Beyond the artifact.** The bullet reading "trigger phrases, 'Use when...' guidance, **and example user messages** belong here" directly contradicted the patched template's zero-`<example>` rule three sections above it. Rewritten to the trigger / USE WHEN / DO NOT USE WHEN shape with "state a trigger as a decision rule, never as a worked `<example>` dialogue". Left unchanged, the file would instruct both policies at once. |
| 3 | `skills/councilify/SKILL.md` | The validator gate ("zero `skill_description_excessive`, zero `example_block_present`", with the invocation) added, plus the N-lens multiplier rationale; the step's Success criteria extended to require it. | The artifact points at "the step that confirms each lens via its own declared skill description, surfaced live in-session". That phrase is in §Bench-size guidance — a *headcount* citation about `adversarial-review`, not a verification step. Applied to **Step 8, "Prove the council convenes (end-to-end)"**, which is the step that verifies the built council and decides done. |
| 4 | `skills/skills-assist/authoring-guide.md` | The `description` frontmatter row carries the cap (**400 / ERROR 800**), the shape, the zero-`<example>` rule, the always-on rendering cost, and the two canonical pointers. The Minimal Example's `description` is now the compliant shape. | None. |

**Verification that the guidance no longer instructs an over-cap number:**

```
$ grep -rn "1024\|700–800\|250 characters\|can be longer" \
    skills/personafy skills/skillify skills/councilify skills/skills-assist
skills/personafy/SKILL.md:142: spec's 1024-char ceiling is a much looser upper bound and is NOT the operative limit; the
skills/personafy/SKILL.md:143: `tool-skills` warning past 1024 is soft and fires long after the real budget is blown.)
```

Both remaining hits are the patched text saying 1024 is *not* the limit.

---

## 4. Repo-level validation — before and after, and why they are identical

Foundation's `validate-bundle-repo.yaml` Phase 2.82 step (`skill-description-validation`)
is pure Python and deterministic, so it was extracted and run standalone at $0 —
`tools/skill_description_check.py`, a verbatim lift with its provenance and its
two non-behavioural differences documented in the file's own docstring. The full
recipe was **not** run: it drives LLM synthesis steps and regenerates
`bundle.dot`/`bundle.png`, neither of which this $0 item authorises.

| | before (`HEAD` = `bceac5f`) | after (patches applied) |
|---|---|---|
| skills checked | 38 | 38 |
| mean chars | 457 | 457 |
| median chars | 367 | 367 |
| max chars | 1008 | 1008 |
| over 400 (WARNING) | 10 | 10 |
| over 800 (ERROR) | 7 | 7 |

`before.json` and `after.json` (`evidence/repo-validation/`) have
**byte-identical** `skill_details` blocks. **That is the correct result, and it
is the point of §6:** this item changes what the creation skills *instruct*, not
the 38 descriptions already shipped. A moved number here would mean the sweep
had been silently folded in.

**Discrepancy with the artifact's own figures, stated rather than smoothed.**
pwmy measured this repo on 2026-09-07 as **n=31, mean 413, median 312, max 928,
13 over 400, 4 over 800**. The same check on this worktree gives **n=38, mean
457, median 367, max 1008, 17 over 400, 7 over 800**. The repo grew between the
two reads — the seven skills over the ERROR line include the product-council
lenses (`positioning-critic` 1008, `bet-sizer` 954, `outcome-cartographer` 913)
that are not in pwmy's n=31. Every number quoted in this note and in the applied
`personafy` text is **this** measurement, taken here.

The seven ERRORs and ten WARNINGs, largest first:

```
1008 ERROR  skills/positioning-critic          778 WARN  skills/restless-old-brian
 954 ERROR  skills/bet-sizer                   754 WARN  skills/intent-keeper
 928 ERROR  skills/user-advocate               681 WARN  skills/crusty-old-engineer
 927 ERROR  skills/msgraph-integration-patterns 681 WARN  skills/monitor
 913 ERROR  skills/outcome-cartographer        643 WARN  skills/cranky-old-sam
 849 ERROR  skills/tester-breaker              608 WARN  skills/personafy
 814 ERROR  skills/councilify                  533 WARN  skills/adapt-skill
                                               530 WARN  skills/amplifier-tool-leverage-patterns
                                               511 WARN  skills/skillify
                                               417 WARN  skills/one-line-installer-patterns
```

**Note the self-reference:** `councilify` (814) and `personafy` (608) are
themselves over the cap they now teach. They are in the deferred sweep, §6.

---

## 5. Clean-room arms — fail-before / pass-after

Two arms, differing **only** in the creation skill's own guidance file. Same toy
inputs (reused verbatim from pwmy, so this is a re-run and not a new
experiment), same instruction text, same `model_role=general`
(`gpt-5.6-terra`, `reasoning_effort=medium`), same clean-slate sub-session
(`context_depth="none"`). Arm inputs are frozen under
`evidence/creation-skill-demo/_guidance/{shipped,patched}/`; outputs under
`evidence/creation-skill-demo/{shipped,patched}/`, scored by
`tools/measure_arms.py` with the shipped thresholds. Full table:
`evidence/creation-skill-demo/RESULTS.txt`.

| arm | creation skill | n | chars | mean | over cap |
|---|---|---:|---|---:|---|
| shipped | `skillify` | 6 | 331, 313, 362, 290, 317, 286 | 316 | **0/6** |
| patched | `skillify` | 6 | 391, 360, 348, 393, 354, 313 | 360 | **0/6** |
| shipped | `personafy` | 3 | **482, 501**, 385 | 456 | **2/3 WARNING** |
| patched | `personafy` | 3 | 309, 278, 260 | 282 | **0/3** |

**The deliverable is met:** the patched arm emits **9/9 clean** — zero
WARNINGs, zero ERRORs, zero `<example>` blocks, zero `<commentary>` tags.

**The honest negative, which is the more interesting half.** The fail-before
reproduces for `personafy` and **does not reproduce for `skillify`.**

- `personafy`: shipped guidance produced 482 and 501 chars on 2 of 3 reps, both
  over the cap; patched produced 309/278/260. Mean **456 → 282 (−38%)**, over-cap
  **2/3 → 0/3**. pwmy's single shipped rep measured 714; the defect is real,
  and its size is variable.
- `skillify`: shipped guidance produced **0/6** over-cap here (max 362), against
  pwmy's single shipped rep at 453. The shipped template's "keep under 250
  characters for the first sentence; can be longer overall" **permits** an
  over-cap description but does not reliably **produce** one; at n=6 it never
  did. The patched arm is in fact ~44 chars *longer* on average (360 vs 316) —
  the DO-NOT-USE-WHEN clause the patch mandates costs characters — and still
  clean, 6/6, because the hard cap bounds it.

So: for `skillify`, the patch is not demonstrated to *fix* an emitted defect at
n=6; it is demonstrated to *bound* one, and to close the gap that made the
defect possible (a template that named no cap at all). For `personafy` it fixes
a defect that reproduced 2 times in 3. Both statements are one measurement, not
an assertion, and n is small in both.

### 5.1 An invalidated pilot, disclosed rather than dropped

A first pass of these arms (n=1 per cell) is kept at
`evidence/creation-skill-demo/pilot-invalid/` and **must not be read as a
result.** Its instruction ended "*Reply with one line: the path you wrote and
the character count of the frontmatter `description` value*" — which makes
description length salient to the author, i.e. **primes the treatment variable
in both arms**. It produced 234 and 223 chars in the *shipped* arm: a floor
effect, not a finding. Two of its four writes also failed on a sandbox
permission error, so the cell was incomplete anyway. The re-run above mentions
neither length, cap, nor `description`; measurement happens afterwards, in a
separate tool. Recorded because an instrument that cannot come out both ways has
not been tested.

---

## 6. The existing over-cap descriptions: **DEFERRED, explicitly**

**The 17 over-400 and 7 over-800 descriptions already shipped in this repo were
NOT swept in this item.** No skill's `description` field was edited. This is a
deliberate deferral, not an omission: the item's own step 5 says the sweep is
separate and names its entry point, and folding a 17-file rewrite into this diff
would make the guidance change unreviewable.

The entry point, per BUNDLE_GUIDE "Refreshing descriptions":

```bash
amplifier tool invoke recipes operation=execute \
  recipe_path=foundation:recipes/refresh-descriptions.yaml \
  context='{"repo_path": "."}'
```

It writes `violations.json`, `proposals.md` (with a per-rewrite fidelity table),
`verdict.json` and `REPORT.md` under `.description-refresh/` and changes nothing
in the repo. It was **not run here** — it drives LLM rewrite steps, which this
$0 authority does not cover.

Two facts the sweep should carry when it is funded:

1. `councilify` (814, ERROR) and `personafy` (608, WARNING) are themselves over
   the cap they now teach. A sweep that misses them leaves the creation surfaces
   contradicting their own instruction.
2. Four of the seven ERRORs are product-council lenses added after pwmy's read.
   A council multiplies a description defect by its lens count — which is
   precisely what patch 3 now gates against at build time.

---

## 7. Tests and CI

```
$ python3 -m pytest tests/ -q
....................                                    [100%]
20 passed in 0.03s
```

Green before and after. **This repo has no CI** — there is no
`.github/workflows/`, no `Makefile`, and no `pyproject.toml`; `pytest tests/` is
the whole gate, and it is run above. Stated plainly, as the deliverable
requires.

The changes are documentation and skill-guidance prose only; no module, no
behavior, no `bundle.md`, and no shipped `description` field was touched.

---

## 8. Spend

**$0 of the $0 authority.** No API measurement was bought. The repo validation
is the recipe's own deterministic Python step, extracted and run locally. The 18
clean-room `delegate` calls (12 valid + a 4-call invalidated pilot + 2 top-ups)
run inside this lane's own session on the same footing as every other LLM call
this item consumed — the same footing pwmy's goal priced at $0 for the same two
arms, which this item's goal cites by name as its precedent. No DTU was
launched, no infrastructure created, nothing registered in an infra ledger.

Cap arithmetic: a $0 authority admits no `runs × arms × per-run` arithmetic and
buys no runs, so there is nothing that could fail to close.

---

## 9. Reproducing this

```bash
# repo-level check, before and after (deterministic, $0)
python3 docs/lanes/jlo6-skills-description-alignment/tools/skill_description_check.py . --summary

# score the frozen clean-room arm outputs
python3 docs/lanes/jlo6-skills-description-alignment/tools/measure_arms.py \
  docs/lanes/jlo6-skills-description-alignment/evidence/creation-skill-demo
```

The arm outputs are named `*.SKILL.md.txt`, never `SKILL.md`: the validator
scans `docs/` by design and says so in its own comment, so an evidence file
named `SKILL.md` would be counted as a shipped skill of this repo and would
corrupt the very before/after counts in §4.
