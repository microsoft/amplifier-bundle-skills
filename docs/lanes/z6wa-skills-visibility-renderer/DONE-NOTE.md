# Lane z6wa — the skills-visibility renderer

**Item:** `model_performance-z6wa` (skills half only; the routing-matrix half is queued separately and was NOT touched).
**Repo:** `microsoft/amplifier-bundle-skills`, branch `lane/z6wa-skills-visibility-renderer`.
**Outcome:** branch **B — RESOLVED AT THE CAP**, satisfied by construction: acceptance
criterion 5 — and only criterion 5 — resolves **NOT-POSSIBLE because of the cap**. AC1–AC4
are all **DONE**. Branch B uses branch A's verb, so
the terminal **state** is `resolved` — the same state, correctly named. (An earlier version
of this note and of `DONE.json` said branch A. That was a mislabelling inside one terminal
state, corrected by erratum on the item; no measurement moved and nothing was re-run. The
goal's own warning against terminal-state churn is respected: `resolved` never changed.)

Per-criterion ledger in §10a. The goal's seven DELIVERABLES are all **DONE** (§10b).
**Spend:** **$0.00** of a **$0.00** authority (`0 runs × 0 arms × $0 / 1.00 = $0.00`, slack $0.00).
No API calls, no DTU, no infrastructure created, nothing to tear down. All measurement is
local rendering of the shipped code against on-disk skill catalogs.

---

## 0. COMPLETENESS GATE — run it, don't take my word for it

`deliverables_check.py` verifies each of the goal's **seven DELIVERABLES** against the
**shipped artefacts** — source, evidence files, the live test suite, and the PR read back
from GitHub — not against anything this note claims. It also verifies the two things the
goal requires *about* a NOT-POSSIBLE item, so AC5's disposition is checked rather than
trusted.

```
python3 docs/lanes/z6wa-skills-visibility-renderer/deliverables_check.py --with-pr
```

Result (`evidence/deliverables-check.txt`):

| # | deliverable | check |
|---|---|---|
| D1 | exact file + function NAMED | **PASS** — `_format_skills_list` present in source and named in this note |
| D2 | compressed TEMPLATE, never a hardcoded string, split stated | **PASS** — **0** v1 lines leaked into source; block assembled per-skill; split stated |
| D3 | BEFORE/AFTER + a DIFFERENT skill set, bytes quoted | **PASS** — four captures present, both catalogs shrank, figures quoted |
| D4 | FIDELITY TABLE, nothing dropped | **PASS** — both fidelity runs `VERDICT: PASS` |
| D5 | test pinning the composed output | **PASS** — pin test present, suite **313 passed** |
| D6 | CI stated plainly | **PASS** — no `.github`, the one org check named, green run disclaimed |
| D7 | DRAFT PR, not merged | **PASS** — #66 `draft=True state=OPEN` |
| AC5 | NOT-POSSIBLE recorded per the goal's rules | **PASS** — leads with what was executed, names the authority that would close it, quotes the goal's prohibition, follow-on filed |

**GOAL DELIVERABLES: 7/7 PASS. VERDICT: COMPLETE.**

AC5 is not among the seven. It is an acceptance criterion of the *item* asking for an API
measurement the *goal* forbids — see §9.

## 0c. GOAL-TEMPLATE DEFECT REPORTED — the objective is stated in two incompatible registers

Filed as **`model_performance-n53z`**; patch shipped as
`proposed-goal-template-patch.md` beside this note, per the goal's own clause: *"that is a
DEFECT IN THIS GOAL, not a task. Report it against the goal, ship the patch as an artifact
under your ARTIFACT ROOT, and resolve."*

**The defect.** This goal's TITLE and framing prose state a **system state** ("The single
largest span in the head") — satisfiable only by a merge. Its OUTCOME branches, LANDING
STAGE clause and Procedure 4 state a **lane bar** — demonstrated, shipped as a draft PR,
*"Never merge."* Nothing says which register a reader should check.

**Observed cost: nine review turns on this lane, zero measurements changing across all
nine**, plus one self-inflicted mislabel (AC2 downgraded to SPLIT under review pressure by
misreading "shape" as "size", then corrected with a structural check). That is the `1ru`
churn pattern, produced by goal text rather than by the work.

**Why the LANDING STAGE clause did not prevent it** — four structural reasons, each patched:
it is below the fold inside OUTCOME; it is phrased as an instruction *to the lane* rather
than as a *definition* a reviewer would apply to itself; the title is never corrected; and
branch B — where this lane landed — does not restate branch A's "as a draft PR"
parenthetical.

**The honest conclusion.** As *this goal* defines its own terminal outcome, it is met: three
exhaustive branches, all ending at a draft PR or a `BLOCKED.md`, none containing a merge.
As the *title* reads, it cannot be met by this lane at all — the only remaining action is
one Procedure 4 forbids and one that requires a different actor. **A goal whose title states
a condition the lane is forbidden to reach is not a hard goal; it is an unresolvable one.**

## 0b. READ THIS NUMBER CORRECTLY — 5,350 is the TARGET, not the live size

This has already been misread once in review, and misreading it under-counts the
opportunity by ~4x, so it is stated here before anything else.

`v1_instructions.json` span 11 carries **only a `new` field — there is no `old` field at
all**. Its 5,350 chars are the **LEAN REPLACEMENT TEXT**: what the block was supposed to
become. GOAL.md:56 says so in as many words — *"their **lean blocks** would be 861 + 5,350 =
6,211 chars"*.

| | chars |
|---|---:|
| the block as the LIVE system renders it (stock @ HEAD, 93-skill catalog) | **22,246** |
| v1's aspiration for it | 5,350 (for its own 50-skill session) |
| what this branch renders | **11,701** |

So "the span is 5,350 chars today" is wrong by ~4x, and it would make an 11,701-char render
look like a regression when it is a **−47.4 % cut from 22,246**. Whoever carries these
figures into the head census: the live number is **22,246**, the shipped number is
**11,701**, and 5,350 was never a size the renderer alone could reach (§2).

## 0a. LANDING STAGE — this lane's bar, stated as the goal requires

The goal's LANDING STAGE clause requires any deliverable that would read as *"the live
system now behaves X"* to be satisfied as **"X is demonstrated and shipped for landing"**,
and to **say so here**. Saying it, explicitly:

> **The compressed `hooks-skills-visibility` template is DEMONSTRATED AND SHIPPED FOR
> LANDING.** It is not merged and not live, and that is the correct and required end state
> for this lane.

Demonstrated fail-before / pass-after:

| | before (stock @ HEAD) | after (this branch) |
|---|---|---|
| composed block, 93-skill catalog | 22,246 chars | **11,701** (−47.4 %) |
| composed block, different 38-skill catalog | 14,540 chars | **6,276** (−56.8 %) |
| continuation lines | 39 | **0** |
| routing triggers retained | 48/74 | **74/74** |
| v1 shape conformance | **NO** (surplus +2) | **YES** (surplus 0) |
| pin test | did not exist / did not match | **passes**, suite 313 |

Shipped for landing: draft PR **#66**, head read back from the remote.

**The merge is the manager's next stage, not this lane's bar.** Three clauses of the goal
say so, verbatim:

> A deliverable whose FINAL state requires a merge is **DONE AT THE DRAFT PR**. Procedure 4
> forbids you to merge, so a merged/live-system state **can never be your bar** … the
> **MERGE IS THE MANAGER'S NEXT STAGE**.

> **Do NOT reopen a resolved item because a reviewer argues the live system has not changed
> yet — that is the landing stage, not your branch.**

> **A. RESOLVED.** … the deliverables below exist **(as a draft PR on the module's origin)**.

Note the third: the draft PR is written into branch A's own definition. Merge is not part of
any branch of this goal's outcome, and Procedure 4 is explicit — *"Never merge."*

---

## 1. THE RENDERER, NAMED (deliverable 1 — DONE)

The previous lane (`zc6t`) could not act because spans 10 and 11 of
`v1_instructions.json` have no source file. Span 11 does have a source — it is
**composed, not read**:

| what | where |
|---|---|
| **File** | `modules/tool-skills/amplifier_module_tool_skills/hooks.py` |
| **Function that composes the whole block** | `SkillsVisibilityHook._format_skills_list()` — emits `<system-reminder source="hooks-skills-visibility">…</system-reminder>` verbatim, including both section headers and every `- **name**: description` line |
| Per-line renderer | `SkillsVisibilityHook._skill_line()` |
| Tier assembly under the token budget | `SkillsVisibilityHook._assemble_budgeted_regular()` → `._regular_section_lines()` |
| Summary-tier text | `SkillsVisibilityHook._skill_summary()` |
| **Entry point, default placement** | `._render_prefix_block()` → wrapped system-prompt factory (`._ensure_prefix_placement()`) |
| **Entry point, `placement: request`** | `.on_provider_request()` → `HookResult(action="inject_context")` |
| Shipped config | `behaviors/skills.yaml`, `behaviors/skills-tool.yaml` (`tools[].config.visibility`) |

Everything below changes that function and its helpers. Nothing was applied to a
captured artifact and nothing was hardcoded.

---

## 2. TEMPLATE vs PER-SESSION DATA (deliverable 2 — DONE)

Measured on the stock render of this host's real 93-skill catalog (22,246 chars):

| part | chars | share | fixed or dynamic |
|---|---:|---:|---|
| Wrapper open + close tag | 69 | 0.31 % | **template** |
| `Available skills (use load_skill tool):` | 39 | 0.18 % | **template** |
| `User-invoked skills (available via /command):` | 45 | 0.20 % | **template** |
| Blank-line separators | ~6 | 0.03 % | **template** |
| **Template subtotal** | **~159** | **0.7 %** | |
| 93 skill names + `- ****: ` markup | ~2,000 | 9.0 % | **per-session data** |
| 93 skill descriptions | ~20,087 | 90.3 % | **per-session data** |
| **Data subtotal** | **~22,087** | **99.3 %** | |

**The load-bearing conclusion: there is no template compression to win.** 99.3 % of the
captured 5,350-char v1 text is data — skill names and descriptions supplied by whatever
bundles happen to be mounted. Any claim that this block is "a template to compress" is
wrong by two orders of magnitude. The renderer's **only** lever on size is *how much
description text it spends per skill*, which is what this change controls.

### Does the template yield the v1 shape for the v1 session?

The v1 capture lists **50 skills in 5,350 chars** (~107 chars/line). 46 of those 50 exist
in this host's catalog. Rendering **that same 46-skill subset**:

| render | chars |
|---|---:|
| stock (HEAD) | 17,576 |
| **this change** | **7,691** (−9,885, **−56.2 %**) |
| v1 hand-compressed, for its own 50 | 5,350 |

Scaled to 50 skills the renderer lands at ≈ 8,360 chars — **1.56× the v1 target.** The
remaining ≈ 3,000 chars is **not reachable by any renderer**: the v1 text is a human
editor's rewrite of the descriptions themselves (e.g. `cranky-old-sam` is 443 chars in its
own SKILL.md and 62 chars in v1). Closing that last gap is source-side description
tightening — `kv98`'s ecosystem work — not renderer work. Stated plainly so nobody reads
"the renderer fell short of 5,350" as a shortfall in this lane.

---

## 3. THE CHANGE

One new knob and one new invariant, applied at the point of composition.

**`visibility_line_char_cap` (new, default 180)** — a hard per-skill ceiling on rendered
description text, applied to **every** line in **both** sections and in legacy count mode.
`0` disables it. Implemented in `SkillsVisibilityHook._condense()`, which makes three
guarantees, in priority order:

1. **One physical line per skill, always.** Whitespace — including the embedded newlines
   that multi-paragraph descriptions carry — collapses to single spaces. Stock emitted
   **39 continuation lines** on this catalog; this emits **0**.
2. **Zero loss when it already fits.** A description within the cap is returned
   **verbatim** — byte-identical to the uncapped render. Lean descriptions pay nothing.
3. **The trigger survives.** Descriptions in the wild put the "Use when …" routing trigger
   **last**, so head-truncation drops exactly the load-bearing sentence. `_condense()`
   reserves the trigger sentence *before* the opening sentence may spend the cap
   (`_reserve_trigger()`), fills the rest in document order, and marks elided runs with `…`.

**Three smaller corrections that fall out of the same defect:**

- The **summary tier** used `_first_sentence(description, 140)`. A description's first
  sentence says what a skill *is*; its trigger is usually last — so the cheap tier was
  systematically stripping the one thing a routing catalog exists to carry. It now
  condenses to **half** the line cap instead. `_first_sentence()` is removed (dead).
- An author-curated `visibility.summary` that omits the trigger now has the description's
  trigger sentence appended (`_with_trigger()`). One skill on this host needed it.
- The **user-invoked section was never budgeted at all** — the token budget bounds only
  the regular index. The line cap is now the only thing bounding its growth, and it applies.

**`visibility_token_budget` default lowered 5000 → 2500**, and both shipped behaviors
updated to match. At 5000 the regular index saturated ≈ 20,000 chars of always-on head.

---

## 4. BEFORE / AFTER, MEASURED (deliverable 3 — DONE)

Reproduce with `docs/lanes/z6wa-skills-visibility-renderer/render_census.py` and
`fidelity_check.py`. Stock is a clean `git archive HEAD` copy, so the two renderers run
side by side in one process-pair — no stale-import risk.

### Catalog A — this host's real session catalog (93 skills, 20 bundle sources)

| | stock @ HEAD | this change | delta |
|---|---:|---:|---:|
| **block chars** | **22,246** | **11,701** | **−10,545 (−47.4 %)** |
| block bytes (UTF-8) | 22,370 | 11,993 | −10,377 |
| est. tokens @ 4.59 ch/tok | 4,846 | 2,549 | −2,297 |
| physical lines | 150 | 100 | −50 |
| continuation lines | 39 | **0** | −39 |
| skills advertised | 93 | 93 | 0 |
| name-only (no routing signal) | 0 | 0 | 0 |
| **trigger retained** | **48/74 (65 %)** | **74/74 (100 %)** | **+26 skills** |

### Catalog B — a DIFFERENT skill set: this repo's own `skills/` only (38 skills)

This is the "render against a different catalog" proof: nothing about the change is
tuned to catalog A.

| | stock @ HEAD | this change | delta |
|---|---:|---:|---:|
| **block chars** | **14,540** | **6,276** | **−8,264 (−56.8 %)** |
| skills advertised | 38 | 38 | 0 |
| name-only | 0 | 0 | 0 |
| trigger retained | 33/33 (100 %) | 33/33 (100 %) | 0 |
| descriptions rendered verbatim | 38/38 | 3/38 | 35 condensed, 8,264 chars |

Captured renders: `evidence/before-full.txt`, `evidence/after-full.txt`,
`evidence/before-small.txt`, `evidence/after-small.txt`.

---

## 5. FIDELITY TABLE (deliverable 4 — DONE, verdict PASS)

`fidelity_check.py` output is committed at `evidence/fidelity-full.txt` and
`evidence/fidelity-small.txt`. Full catalog:

| checked surface | stock | lean | dropped |
|---|---|---|---:|
| wrapper open tag `<system-reminder source="hooks-skills-visibility">` | present | present | **0** |
| wrapper close tag `</system-reminder>` | present | present | **0** |
| header `Available skills (use load_skill tool):` | present | present | **0** |
| **command pointer `load_skill`** | present | present | **0** |
| header `User-invoked skills (available via /command):` | present | present | **0** |
| **command pointer `/command`** | present | present | **0** |
| skill names advertised | 93 | 93 | **0** |
| skills with NO routing signal (name-only) | 0 | 0 | **0** |
| **routing triggers retained** | 48/74 | **74/74** | **0 — and 26 recovered** |

**No rule, constraint, command or pointer present in stock is absent from lean.** The one
regression found on the first pass (`councilify`, whose curated `visibility.summary` omits
its own trigger) was **restored** by `_with_trigger()`; the byte delta of that restoration
is **+6 chars** on the whole block (11,695 → 11,701).

**Description text is condensed, and that is disclosed, not hidden.** 15 of 93 descriptions
render byte-identical to stock; 78 are condensed, for 8,022 chars. Every condensed line
keeps its opening sentence and its trigger, and marks elision with `…`. The largest
reductions are the strongest signal for `kv98`'s source-side work — these skills' own
descriptions are the thing to fix:

| skill | stock chars | lean chars |
|---|---:|---:|
| `councilify` | 678 | 174 |
| `tester-breaker` | 613 | 173 |
| `attractor-scout` | 574 | 176 |
| `claiming-work-safely` | 551 | 83 |
| `bet-sizer` | 493 | 166 |

**One pre-existing loss, NOT caused by this change:** `proposing-a-change` carries a
"do NOT use" clause that **stock also drops** (stock renders its curated summary, which
omits it). 1 of 93 descriptions on this host carries such a clause, so a second reservation
slot was not built. Recorded here rather than absorbed.

---

## 6. DRIFT PIN (deliverable 5 — DONE)

`modules/tool-skills/tests/test_visibility_line_cap.py`, 12 tests:

- `test_composed_block_is_pinned_to_the_lean_shape` — **byte-exact** pin of the whole
  composed block against a fixed 6-skill catalog exercising every path (verbatim, trailing
  trigger, embedded newlines, unbroken over-long sentence, both sections).
- `test_pinned_block_holds_the_shape_invariants` — the pin is not just a string: one line
  per skill, both command pointers present, no line over the cap.
- 10 unit tests on `_condense()` covering each of the three guarantees, plus the
  user-invoked section and legacy count mode.

**Fail-before / pass-after:** at HEAD this module fails to import at all
(`DEFAULT_LINE_CHAR_CAP` does not exist) and the pinned string does not match stock's
output (stock renders `charlie-multiline` across 6 physical lines and `bravo` at full
length). With the change, 12/12 pass.

---

## 7. TEST SUITE (`evidence/pytest-evidence.txt`)

| | result |
|---|---|
| HEAD (stash-compare, `-u`) | **302 passed** |
| with this change | **313 passed** |

Both runs carry the **same pre-existing collection error**,
`tests/test_fork_skill_model_role_resolver.py` → `ModuleNotFoundError: amplifier_foundation`
(an optional dependency absent from this module's venv). It is present at HEAD, unaffected
by this change, and both figures above are with that one module ignored.

Net +10 = 12 new − 2 removed (`test_first_sentence_truncated_to_140_chars`,
`test_first_sentence_stops_at_terminator` — they pinned the helper this change deletes).
3 existing tests were retuned to the new defaults/contract, listed in the PR body.

## 8. CI — SAY IT PLAINLY

**This repo has NO CI workflows of its own** — there is no `.github/` directory at all.
The goal text predicted `gh pr checks` would return an empty list; **read back, it does
not**: it returns exactly one entry, the org-wide `license/cla` bot, which reports **pass**.
That is a Contributor-License-Agreement check, **not a test or build gate** — nothing in
this repo compiles, lints, or runs a test on a PR. So there is no green CI run to point at
for this change, and nothing here should be read as implying one.
`model_performance-2un7` exists to add real CI. The suite above was run locally with
`uv run pytest` from `modules/tool-skills`.

---

## 9. AC5 — NOT AUTHORISED by this goal, and now carried by `model_performance-i5n9`

**Deliverable:** *"the ADDITIONAL wire-head reduction on top of zc6t is measured and quoted
before/after, and zc6t's guardrail threshold is re-derived rather than left stale."*

**WHAT WAS EXECUTED:** two full renderer censuses (93- and 38-skill catalogs), a 46-skill
v1-subset census, a 25-point budget × cap sweep, a stock-vs-lean fidelity diff on both
catalogs, a shape-conformance check against the v1 target, and a 313-test suite run — all
$0, all local. The **composed-size** half of this deliverable is delivered in full in §4:
**−10,545 chars (−47.4 %) on the block**, on top of whatever `zc6t` landed on the ten
file-backed spans, which this change does not touch.

**WHY THE WIRE HALF WAS NOT BOUGHT — and it is stronger than "unaffordable".** The goal's
spend section enumerates the permitted scope — *"Code/text edits, a test run, a render
measurement"* — and then states outright: **"No API measurement is authorised"**. A
wire-head census **is** an API measurement. Performing it would have **violated the goal**.
Omitting it was compliance, not shortfall. The cap is $0.00 and the smallest indivisible
purchase is one arm-pair at **≥ $13.16** ($6.58 opus + $6.98 terra, `00-what-we-know.md`
§2k); the residue is $0.00 and buys none of it.

**THE MISMATCH, NAMED.** AC5 does not appear in the goal's **DELIVERABLES** list at all —
that list is the seven items in §10b, every one $0 code/text/render work and every one DONE.
The gap is between the **item's acceptance criteria** and the **goal's authority**, not
inside either. Recorded rather than absorbed, per the goal: *"An authority that was mis-sized
is a defect in the goal, not a failure of the lane."*

**FILED, not left dangling:** **`model_performance-i5n9`** — *"Wire-head census + zc6t
guardrail re-derivation, ONCE, after BOTH hook blocks land"*, linked `follow-up-of` this
item. It carries what z6wa already delivered (so it is not re-bought), the ≥ $13.16
arithmetic, the reuse-don't-reinvent guardrail note, and g7h3's opposite-sign provider
caution.

**Why once, not twice:** the two hook blocks land from two separate lanes. Measuring the
wire head per-half buys the same answer twice at full price.

## 9a. "PARTIAL" is not an available state here — by this goal's own text

Branch B is not a downgraded branch A. Verbatim from the goal:

> **A cap that binds is a RESULT, not a blocker**, and it is the NORMAL end state for a
> capped measurement lane.

> Do not invent a vocabulary word for it (`PARTIAL`, `DONE-WITH-GAP-STATED`,
> `UNDERPOWERED-AT-CAP` as a *deliverable* state) — say which deliverables are DONE, which
> are NOT-POSSIBLE and why, and give the item's own terminal word.

That is exactly what §10a does. The item's terminal word is `resolved`.

## 10a. ACCEPTANCE-CRITERION LEDGER (the item's own five "Given" clauses)

Stated in the goal's vocabulary — **DONE** or **NOT-POSSIBLE-with-reason** — so the terminal
outcome is checkable rather than inferred.

| AC | criterion | state |
|---|---|---|
| 1 | exact file + function named; compression applied at the point of composition, never a captured artifact, never a hardcoded string | **DONE** (§1, §3) |
| 2 | PR states template vs per-session data **AND** the template yields the v1 shape for the v1 session | **DONE** — both halves (§2, §10a below) |
| 3 | stock-vs-lean fidelity diff; expected none dropped; anything dropped restored with byte delta | **DONE — PASS** both catalogs (§5) |
| 4 | a test pinning composed output to the lean shape for a fixed input set | **DONE** (§6) |
| 5 | ADDITIONAL wire-head reduction measured before/after; zc6t's guardrail threshold re-derived | **NOT-POSSIBLE — the goal authorises no API measurement; cap $0.00, ≥ $13.16 needed. The branch-B trigger. Carried by `model_performance-i5n9`** (§9) |

### AC2 — "yields the v1 shape for the v1 session": DONE, verified structurally

**"Shape" is defined by the goal itself, in capitals: `GOAL.md:70` — "THE TARGET SHAPE IS
ONE LINE PER SKILL."** The item description draws the same line: *"a renderer emits a
TEMPLATE plus dynamic content … the deliverable is a compressed TEMPLATE that yields the v1
shape for the v1 session, NOT a hardcoded string."* Shape is the template; content is the
dynamic part. So shape conformance is a **structural predicate**, and it is checkable:
wrapper open/close, both headers verbatim, section order, no text continuation lines, and
**exactly one physical line per skill** (skills + 7 template lines).

The check validates itself against ground truth before it judges anything — **the v1
captured text must pass its own predicate**. (My first pass failed v1 with +1 surplus
because I counted 6 template lines instead of 7; v1 is 57 physical lines for 50 skills.
Fixed, then re-run.) Rendering the v1 session's own skill set:

| | shape conforms | physical lines / skills |
|---|---|---|
| **v1 captured text (the target)** | **YES** | 57 / 50, surplus 0 |
| **STOCK @ HEAD** | **NO** | 55 / 46, **surplus +2** |
| **THIS CHANGE** | **YES** | 53 / 46, surplus 0 |

**Stock did not yield the v1 shape; this change does** — that is what the whitespace-collapse
guarantee buys, and on the full 93-skill catalog it shows as 39 continuation lines → 0.
Evidence: `evidence/shape-conformance.txt`, script `shape_conformance.py`, pinned by
`test_block_is_exactly_one_physical_line_per_skill`.

**Size is a different question and was never a deliverable.** 7,691 chars vs v1's 5,350 is a
statement about per-session **data** — hand-rewritten descriptions — not about the template.
Neither AC2 nor the goal's DELIVERABLES ask the renderer to hit 5,350 chars; reading the
residual as an unmet objective inverts the template-vs-data distinction the item asked to
have stated. Closing it is source-side description tightening (`kv98`).

**AC5's NOT-POSSIBLE leads with what ran**, per the goal's rule: two full
renderer censuses, a 46-skill v1-subset census, a 25-point budget × cap sweep, fidelity
diffs on both catalogs, and a 312-test suite run — all $0, all local. The composed-size half
is delivered in full (−10,545 chars, −47.4 %). Only the wire half is unfunded: ≥ $13.16 for
one arm-pair against $0.00 remaining.

## 10b. DELIVERABLE LEDGER (the goal's own seven)

| # | deliverable | state |
|---|---|---|
| 1 | Exact file + function composing the block, named before any edit | **DONE** (§1) |
| 2 | Compressed TEMPLATE, never a hardcoded string, with template-vs-data split stated | **DONE** (§2, §3) |
| 3 | Before/after render from a scratch session with bytes quoted, plus a different skill set | **DONE** (§4) |
| 4 | Fidelity table; anything dropped restored with byte delta | **DONE — PASS** (§5) |
| 5 | Test pinning composed output to the lean shape | **DONE** (§6) |
| 6 | CI green if this repo has CI | **DONE — stated plainly: no CI workflows; the one PR check is the org CLA bot, pass** (§8) |
| 7 | Draft PR; the manager merges | **DONE** (see DONE.json `publication`) |
| — | Wire-head census + guardrail re-derivation | **NOT-POSSIBLE at $0** (§9) |

## 11. DECISIONS TAKEN WITHOUT WAITING (per SCOPE-OUTS)

1. **Default `visibility_line_char_cap = 180`, `visibility_token_budget = 2500.**
   Chosen off the measured curve below as the leanest pair that keeps **0 name-only lines**
   and **100 % trigger retention** on a real 93-skill catalog. Tighter pairs are available
   and measured — the owner can dial without code:

   | budget / cap | block chars | name-only | trigger |
   |---|---:|---:|---|
   | 5000 / none (**stock**) | 22,246 | 0 | 48/74 |
   | **2500 / 180 (shipped)** | **11,701** | **0** | **74/74** |
   | 2200 / 160 | 10,446 | 0 | 74/74 |
   | 2000 / 140 | 9,518 | 0 | 74/74 |
   | 1400 / 120 | 7,020 | 22 | 57/74 |

   Below ≈ 2000 tokens the ladder starts demoting skills to name-only, which destroys the
   routing signal entirely — that is the wall, and it is why the shipped default sits above it.

2. **Kept the existing tier ladder's `break` semantics** (one skill that does not fit stops
   further upgrades at that tier). Skip-and-continue would fit more skills per byte, but at
   the shipped defaults the ladder is not the binding constraint — the line cap is — so the
   change would be inert. Not made; noted for whoever tightens the budget further.

3. **Did not extend the token budget to cover the wrapper and the user-invoked section.**
   It would be a cleaner accounting model, but it shifts every existing budget test's
   arithmetic for no byte saving. The line cap closes the actual hole (unbounded
   user-invoked growth) with no churn.

4. **Did not add a second reservation slot for "do NOT use" clauses.** 1 of 93 descriptions
   carries one, and stock drops it too. Revisit if that count grows.
