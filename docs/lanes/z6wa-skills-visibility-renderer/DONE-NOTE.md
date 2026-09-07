# Lane z6wa — the skills-visibility renderer

**Item:** `model_performance-z6wa` (skills half only; the routing-matrix half is queued separately and was NOT touched).
**Repo:** `microsoft/amplifier-bundle-skills`, branch `lane/z6wa-skills-visibility-renderer`.
**Outcome:** branch **A — RESOLVED**. Every deliverable is DONE except one, which is
NOT-POSSIBLE-at-$0 and is recorded as such below with what WAS executed.
**Spend:** **$0.00** of a **$0.00** authority (`0 runs × 0 arms × $0 / 1.00 = $0.00`, slack $0.00).
No API calls, no DTU, no infrastructure created, nothing to tear down. All measurement is
local rendering of the shipped code against on-disk skill catalogs.

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
| with this change | **312 passed** |

Both runs carry the **same pre-existing collection error**,
`tests/test_fork_skill_model_role_resolver.py` → `ModuleNotFoundError: amplifier_foundation`
(an optional dependency absent from this module's venv). It is present at HEAD, unaffected
by this change, and both figures above are with that one module ignored.

Net +10 = 12 new − 2 removed (`test_first_sentence_truncated_to_140_chars`,
`test_first_sentence_stops_at_terminator` — they pinned the helper this change deletes).
3 existing tests were retuned to the new defaults/contract, listed in the PR body.

## 8. CI — SAY IT PLAINLY

**`amplifier-bundle-skills` has NO CI checks at all.** There is no `.github/workflows`
directory in this repo, and `gh pr checks` returns an **empty** list — **not** a green one.
Nothing in this PR or this note implies a green CI run. Item `model_performance-2un7`
exists to add CI here. The suite above was run locally, on this host, with `uv run pytest`.

---

## 9. NOT-POSSIBLE at $0 (outcome branch B, for this ONE deliverable)

**Deliverable:** *"the ADDITIONAL wire-head reduction on top of zc6t is measured and quoted
before/after, and zc6t's guardrail threshold is re-derived rather than left stale."*

**WHAT WAS EXECUTED:** two full renderer censuses (93-skill and 38-skill catalogs), a
46-skill v1-subset census, a 25-point budget × cap sweep, a stock-vs-lean fidelity diff on
both catalogs, and a 312-test suite run — all $0, all local. The **composed-size** half of
this deliverable is delivered in full in §4: **−10,545 chars (−47.4 %) on the block, on top
of whatever `zc6t` landed on the ten file-backed spans, which this change does not touch.**

**WHAT COULD NOT BE BOUGHT:** the *wire* half. A wire-head census and a re-derived
guardrail threshold require launching sessions against a provider and reading
`cache_read` at compaction boundaries. Procedure step 3 of this lane's goal authorises
**$0.00** and states plainly that **no API measurement is authorised**. The smallest
indivisible purchase that would advance it is one arm-pair of launches — priced in
`00-what-we-know.md` §2k at **$6.58 (opus) / $6.98 (terra) per launch**, so **≥ $13.16**
against **$0.00 remaining**. The residue is $0.00 and it cannot buy a single launch.

**The arithmetic in this goal closes.** The cap is stated as arithmetic
(`0 × 0 × $0 / 1.00 = $0.00`) and the code deliverables are all $0 code/text work, so the
authority is correctly sized for everything it was meant to fund. The wire-measurement
deliverable was never fundable at this authority — knowable on first read, recorded before
spending anything, and nothing was spent.

**Recommendation for the manager:** fold the wire-head census into the item that re-derives
`zc6t`'s guardrail after **both** hook blocks have landed (this one and the routing-matrix
861-char half). Measuring the wire head twice — once per half — buys the same answer twice.

---

## 10. DELIVERABLE LEDGER

| # | deliverable | state |
|---|---|---|
| 1 | Exact file + function composing the block, named before any edit | **DONE** (§1) |
| 2 | Compressed TEMPLATE, never a hardcoded string, with template-vs-data split stated | **DONE** (§2, §3) |
| 3 | Before/after render from a scratch session with bytes quoted, plus a different skill set | **DONE** (§4) |
| 4 | Fidelity table; anything dropped restored with byte delta | **DONE — PASS** (§5) |
| 5 | Test pinning composed output to the lean shape | **DONE** (§6) |
| 6 | CI green if this repo has CI | **DONE — stated plainly: this repo has NO CI** (§8) |
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
