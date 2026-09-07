# model_performance-4br4 — skills catalog reduction

**LANDING STAGE: draft PR.** Everything below is on
`lane/4br4-skills-catalog-reduction`. Nothing is merged; merging is the manager's
next stage.

**Spend: $0.00 of a $0.00 authority for measurement.** Every census render is the
shipped renderer run locally over local files. The three real-session checks the
goal requires cost **~$0.90 of ordinary session use** on `claude-haiku-4-5` — the
authority names "real-session checks via load_skill and slash commands" as
authorised, and no API-metered *measurement* was bought.

---

## The one thing to read first

**Hiding a skill did not shrink the always-on head — it grew it by 19.4%.**
Measured, not assumed. The `disable-model-invocation` flag moves a skill from the
visibility block's *budgeted* regular section into its *unbudgeted* user-invoked
section, so on a catalog whose regular section is already at budget the freed
tokens are immediately re-spent upgrading other skills' detail tiers while the
user-invoked section grows by a full ~180-char line per moved skill.

The catalog counts all move the right way; the byte count does not. Both are
below, and the renderer defect is filed as **`model_performance-0sbr`**.

---

## Three-arm census — the numbers

All four renders taken back-to-back in one sitting (the host bundle cache is
live; renders an hour apart are not comparable). Renderer:
`SkillsVisibilityHook._format_skills_list`, `visibility_token_budget=2500`
(the shipped default), `visibility_line_char_cap=180`.
Full output: `evidence/census-arms.txt`, `evidence/{before,after}-{small,full}.txt`.

| arm | catalog | | model-invocable | user-invoked | block chars |
|---|---|---|---|---|---|
| **A** origin/main `dbd5201` | repo-only | 38 | 31 | 7 | 6,276 |
| **B** patterns fold only | repo-only | 26 | 19 | 7 | 4,824 |
| **C** fold + hide *(this PR)* | repo-only | **26** | **7** | **19** | **4,824** |
| **A** origin/main `dbd5201` | host-real | 107 | 96 | 11 | 11,693 |
| **B** patterns fold only | host-real | 95 | 84 | 11 | 11,709 |
| **C** fold + hide *(this PR)* | host-real | **95** | **72** | **23** | **13,984** |

Read three ways:

1. **Catalog size falls on both catalogs: 38 → 26 and 107 → 95** (−12 entries,
   the 13 pattern skills folded into 1). **Model-invocable entries fall hardest:
   31 → 7 and 96 → 72.** That is the routing-noise win the owner asked for, and
   it is real on every catalog.
2. **The fold is the token win, and only where the budget is not binding.**
   Repo-only: −1,452 chars (−23.1%). Host-real: **+16 chars, i.e. nothing** —
   that catalog's regular section is budget-saturated, so removing 12 entries
   just frees budget that other entries immediately spend.
3. **Hiding is token-NEUTRAL on an unsaturated catalog (4,824 both arms) and
   token-NEGATIVE on a saturated one (+2,275 chars, +19.4%).** Cause: the
   user-invoked section has never been budgeted — #66's own commit message says
   so. Filed as `model_performance-0sbr`; deliberately **not** fixed here,
   because the renderer belongs to lane z6wa (#66), which pins the composed block
   byte-exact in `modules/tool-skills/tests/test_visibility_line_cap.py`.

**Recommendation to the manager:** merge this for the routing win, and land
`0sbr` before or with it if the always-on byte count is the binding constraint.
On its own this PR trades 2,275 chars of head for 24 fewer skills competing for
the model's routing attention.

---

## Deliverables

| # | Deliverable | Verdict |
|---|---|---|
| 1 | Every persona lens except tester-breaker / restless-old-brian carries `disable-model-invocation: true`; the two exceptions verified unchanged | **DONE** |
| 2 | Real-session evidence: councils still fan out to lenses by name; each hidden lens still loads by name | **DONE** |
| 3 | Exactly one `engineering-patterns` skill; description names every absorbed topic; every original body survives as an L3 file | **DONE** |
| 4 | adapt-skill / councilify / personafy hidden; skillify hidden-or-kept per the load-path check | **DONE** — all four hidden, check quoted below |
| 5 | Before/after render of the visibility block, both quoted, after-count smaller | **DONE on count** (96 → 72 model-invocable, 107 → 95 catalog). **NOT on bytes** — 11,693 → 13,984, reported above rather than hidden |
| 6 | pwmy's validators re-run, verdict quoted, must stay PASS | **PARTIAL** — see below |
| 7 | Anything already compliant left unedited, named as such | **DONE** — see below |

### 1 + 4 — who is hidden, who is not

**Hidden (12), all verified `disable-model-invocation: true` + `user-invocable: true`:**
bet-sizer, cranky-old-sam, crusty-old-engineer, intent-keeper,
outcome-cartographer, outcomist, positioning-critic, user-advocate,
adapt-skill, councilify, personafy, skillify.

**Unchanged, full visibility (2):** `tester-breaker` (385 standalone uses),
`restless-old-brian` (236) — `git diff origin/main` touches neither file.

**Out of scope, confirmed by directory listing:** the 9 design-council lenses are
**not in this repo at all** (they live in the `anderlpz` fork). Nothing here
touches them.

### 4 — the skillify question, answered

The goal said: hide skillify only if its loads are exclusively user-initiated;
keep it visible if the model ever reaches for it on its own.

Counting documented `load_skill(skill_name="X")` instructions across every bundle
mounted on the owner's real app list, excluding each skill's own directory:

```
skills-assist            : 8    <- positive control
digital-twin-universe    : 12   <- positive control
claiming-work-safely     : 1    <- positive control
work-tracker-operations  : 1    <- positive control
---
skillify                 : 0
adapt-skill              : 0
councilify               : 0
personafy                : 0
```

**skillify is HIDDEN**: zero model-initiated load paths, on an instrument that
finds 1–12 for four known positives.

**Two instrument failures are recorded rather than buried** (full detail in
`evidence/author-tools-load-path-check.txt`): the first positive control was
`goalify`, which returns 0 because it was *moved out of this repo* in `c2e2049`
and is not in the cache at all; and a `ripgrep`-based pass returned 0 for
everything because **`rg` is not installed on this host** and the errors were
being swallowed. Both zeros were the instrument, not the data.

**One half of the question is UNKNOWN, not zero.** A historical census over this
host's 33,083 captured `events.jsonl` files could not be completed — tool-call
arguments are stored as *escaped* JSON inside the event payload, so the obvious
pattern never matches, and `context-intelligence:graph-analyst` (the right tool)
failed to start here with `LLMError: cannot import name 'path_template' from
'openai._utils'`. The decision rests on the static result above.

### 2 — real-session verification

Scratch `AMPLIFIER_HOME` seeded with a **copy** of the owner's `settings.yaml`
(same 20-entry `bundle.app` list), with the cached clone of this bundle's
`skills/` replaced by a symlink to the branch, proven by
`amplifier tool invoke load_skill info=councilify` resolving to
`<lane>/amplifier-bundle-skills/skills/councilify/SKILL.md`.
Full transcript excerpts: `evidence/realsession-verification.txt`.

**14 of 14 skills loaded by name** (12 hidden + the umbrella + a kept lens), and
the umbrella's L3 reference read back `# Microsoft Graph Integration Patterns`.

`/product-council` fanned out naming every one of its six lenses, five of them
newly hidden:

```
{ lens: "intent-keeper", verdict: "FAIL", ...
{ lens: "outcome-cartographer", verdict: "FAIL", ...
{ lens: "outcomist", verdict: "CONCERN", ...
{ lens: "user-advocate", verdict: "CONCERN", ...
{ "lens": "positioning-critic", "verdict": "FAIL", ...
{ lens: "bet-sizer", verdict: "CONCERN", ...
```

`/council` fanned out the same way:

```
arguments: "... Act as intent-keeper and return the required structured lens result."
arguments: "... as the cranky-old-sam lens: ..."
arguments: "... as the restless-old-brian lens: ..."
{ lens: "intent-keeper", verdict: "FAIL", ...
{ lens: "crusty-old-engineer", verdict: "CONCERN", ...
"lens": "user-advocate", ...
```

**Disclosed:** the first `/council` attempt **mis-routed to `/design-council`** on
haiku — the root model saw the design-council bundle in the same app list and
delegated there instead. Re-run with the explicit
`load_skill(skill_name="council", arguments=...)` call — which is exactly what
the slash command does — and it convened the persona roster correctly. The
mis-routed run is kept, because it is also evidence that `/design-council` still
convenes (`Consulted: Originality Critic, Coherence Guardian, Craft Inspector,
Emotion Reader, Context Tester, Human Advocate, Purpose Keeper`) — those 9 lenses
are in the fork and this lane did not touch them.

### 3 — the patterns fold, and the count discrepancy

**The program directive said 12. The correct count on this branch is 13.** The
uncounted one is `one-line-installer-patterns`. All 13 verified present by
directory listing before anything was touched.

Each original `SKILL.md` was `git mv`'d — the diff shows 13 `R` (rename) entries,
**zero deletions** — to
`skills/engineering-patterns/references/<original-name>.md`, byte-for-byte
unchanged, frontmatter retained as provenance. The umbrella's body is a
13-row index that links every one.

The description names all 13 topics **and fits the shipped 180-char render cap at
178 chars**, so the catalog line renders VERBATIM rather than being clipped:

```
- **engineering-patterns**: Use for tool/service work: CLI packaging, installers, config/state, HTTP, auth/TLS, file IPC, plugins, instance storage, containers, React MFE, Graph, self-update, tool leverage.
```

That is deliberate. A longer description naming the topics in full would be
truncated by `_condense`, and truncation eats the *tail* — the least guessable
topics. `tests/test_skills_catalog_shape.py` pins both the topic list and the cap.

### 6 — pwmy's validators: PARTIAL, with the reason

- `@foundation:recipes/validate-agents.yaml` — **structural validation PASS**
  (`status: valid`, schema v2, runner-isolated preflight), $0.
- A **full** `validate-agents` / `validate-bundle-repo` run is LLM-driven and
  API-metered, which the $0 authority does not fund. **NOT-POSSIBLE at $0.**
- `validate-agents` also has **no subject in this repo**: there is no `agents/`
  directory here. This bundle ships skills and one tool module.
- The deterministic gate that *does* cover this branch is the repo's own CI,
  landed in `#68`, run in full (`evidence/test-run.txt`):

```
ruff 0.15.7        : All checks passed!
bundle structure   : OK -- bundle structure checks passed (26 SKILL.md, 29 files parsed cleanly)
root tests         : 35 passed
module tests       : 315 passed
```

`35` is up from `27` on main: one pre-existing guard was **inverted, not
deleted** (`tests/test_adapt_skill.py::test_no_disable_model_invocation` →
`test_disable_model_invocation_is_set`, docstring carrying the owner's dated
reversal), and `tests/test_skills_catalog_shape.py` adds 7 new guards pinning who
is hidden, who is not, that every hidden skill stays `user-invocable`, that all
13 bodies survive, and that the umbrella description fits the render cap.

### 7 — already compliant, left unedited

`code-review`, `council`, `council-here`, `mass-change`, `product-council`,
`product-council-here`, `session-debug` already carried
`disable-model-invocation: true`. Untouched. `monitor` carries an explicit
comment refusing the flag on purpose ("staying model-invocable is what lets the
agent reach for this instead of promising follow-up it has no mechanism to
deliver") — untouched, and it is not a persona lens or an authoring tool.

---

## Owner's environment: what was and was not touched

`~/.amplifier/settings.yaml` md5 **changed** during this lane,
`46626a41…` → `028a195c…`, and the diff is **`updates.last_check` only**
(`2026-09-07T13:41:50` → `15:04:14`) plus one `bundle.app` line the owner
themselves removed at 14:46. The routine update-check timestamp is written by the
CLI on invocation. **No source override, no bundle change, and no `4br4` string
was written to the owner's settings** — `grep 4br4 ~/.amplifier/settings.yaml`
returns nothing; the override went to the scratch home, confirmed in
`scratch-home/settings.yaml:227`.

## Reproducing the census

```bash
python3 docs/lanes/4br4-skills-catalog-reduction/census.py --catalog small   # this repo's skills only, deterministic anywhere
python3 docs/lanes/4br4-skills-catalog-reduction/census.py --catalog full    # + this host's mounted bundle cache
```

The harness is the sibling lane's `render_census.py` with one deliberate change:
any cached clone of `amplifier-bundle-skills` is excluded and this checkout's
`skills/` is merged first, so a before/after measures the branch instead of the
cache's stale copy.
