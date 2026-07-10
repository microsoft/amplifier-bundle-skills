---
name: councilify
description: >
  Build a NEW complete "council" for a domain — a panel of orthogonal review
  lenses that fan out cold, debate to consensus, and return a synthesized verdict
  with recorded dissent, exactly like /council and /design-council. Identifies the
  distinct lenses the domain needs (one load-bearing question each, mined from real
  archetypes — not invented), reuses existing lenses where they already cover an
  axis, builds only the genuinely-missing ones (persona SKILLs via personafy, or
  agents when the role is an active builder), assembles the orchestrator + bench
  into an invocable council bundle, and proves it convenes end-to-end. Use when
  creating a council, standing up a review panel for a domain (product, security,
  performance, data), or when someone says "councilify", "make a council",
  "build a <domain> council".
user-invocable: true
model_role: reasoning
allowed-tools:
  - read_file
  - write_file
  - edit_file
  - glob
  - grep
  - bash
  - delegate
---

# Councilify

Produce a NEW, invocable **council** for a domain: a `context: fork` concierge
orchestrator over a bench of **orthogonal lenses**, following the proven
`/council` → `/design-council` pattern. Reuse before you build; build lenses only
where a real, distinct load-bearing question is missing.

**Success artifact:** a council bundle that, in a FRESH session, convenes on a
realistic target — prints a roster manifest, loads every rostered lens (cold,
independent), returns `{PASS|CONCERN|FAIL|N/A}` verdicts, and surfaces standing
dissent — with every NEW lens grounded in real evidence and proven to steer.

## Inputs

- `$ARGUMENTS`: the domain to build a council for (e.g. "product development",
  "security review", "performance"). Optionally: pointers to evidence/archetypes,
  a target-class hint, and a preferred bundle home.

## Core Principles

- **Reuse beats build.** A lens that already owns an axis is composed in by
  reference across bundle boundaries (the ROB-from-made-support precedent), never
  copied. Building a lens whose question equals an existing lens's is the failure
  this skill exists to prevent.
- **One question per lens, from evidence.** Every lens owns exactly ONE
  load-bearing question, mined from a real person/archetype per `personafy` —
  never invented from vibes. If a candidate's question collapses into an existing
  lens's, it is not a lens. Cut it.
- **No anthropomorphizing beyond a distinct voice.** A lens is a review
  *perspective* with a recognizable voice and discipline, not a fictional
  character with a backstory. Voice serves steering; lore does not.
- **Councils are complementary, not duplicative.** A new council must review a
  distinct target class at a distinct stage. Sharing a lens across councils is
  fine; two councils doing the same job is not.

## Steps

### 1. Study the pattern

Read the reference implementations in full: `council/SKILL.md`,
`council-here/SKILL.md`, and `design-council/SKILL.md` + two of its lens skills
(e.g. `originality-critic`, `purpose-keeper`). Extract: the phase-by-phase
orchestration (roster → optional neutral digest → cold fan-out →
debate-to-consensus → synthesize), the trust guardrails (roster manifest first,
attributed quotes, never downgrade a FAIL, keep FAIL≠N/A), UNAVAILABLE vs
ERRORED handling, and the **council-native lens template** (Load-Bearing
Question / Grounding / Tone / Core Behaviors / Verdict Protocol / Tension With).
Note the phase-numbering difference between the two: `council` has 5 phases
(Guard Check, Roster, repo-digest, fan-out, debate, synthesize) because it
supports a repo-crawl pre-digest; `design-council` has 4 phases (no pre-digest —
targets always pass directly) because every target is a single self-contained
design artifact.

**Success criteria:** You can restate the orchestrator's phases and the lens
template from memory, and name why `council-here` is inline while `council`
forks.

### 2. Frame the domain and mine candidate lenses

Name the domain's **target class** (what artifact does this council review?) and
**stage** (when in the lifecycle?). Then mine real domain-leadership archetypes
for the distinct perspectives that domain demands. For each candidate: one
load-bearing question, the archetype/framework it's grounded in, and a one-line
voice.

- **Execution:** Delegate parallel `model_role="research"` agents to gather
  archetype evidence per candidate lens; each writes findings to disk, returns a
  thin summary.

**Success criteria:** A candidate list where each entry has ONE question grounded
in a named archetype, not a vibe.

### 3. Additive test — inventory and route every candidate

Enumerate the FULL installed inventory before building anything:
`load_skill(list=true)` for all lens skills, and identify every existing panel —
`council` (6: intent-keeper, cranky-old-sam, crusty-old-engineer,
restless-old-brian, user-advocate, tester-breaker), `design-council` (7 design
lenses), `adversarial-review` (6: SRE, security, staff engineer, finance,
operator, developer advocate — production/operational risk of a system design;
note it also ships a recipe-callable `systems-design-critic` agent form of the
same bench, a third composition pattern worth considering in Step 6's optional
extension), plus any others surfaced by the inventory scan.

Build a **coverage matrix**: candidate lens × existing lenses. Route each
candidate to exactly one of:
- **REUSE** — an existing lens already owns this exact question → compose by
  reference; record its home bundle + graceful-degradation note.
- **BUILD-skill** — a real, distinct review question with no owner → Step 5.
- **BUILD-agent** — not a review lens at all but an *active builder/specialist*
  → Step 4.

Then apply the **needs-its-own-council test** (all three required): distinct
target class; ≥4–5 net-new orthogonal lenses; folding them into an existing bench
would make it incoherent or oversized (>~8). If it fails, STOP and recommend
`personafy`-ing the 1–2 new lenses into the existing council instead.

- **Human checkpoint:** confirm the roster (reused + new), and the
  own-council-vs-add-lenses decision, before any building.

**Success criteria:** Every candidate routed; the own-council decision is
explicit and defensible against all existing panels.
**Rule:** ground the decision in the actual inventory, not assumption.

### 4. Skill-lens vs agent decision (only for BUILD-agent candidates)

Consult the skills-vs-agents framework (`load_skill("skills-assist")`). Default:
a **review lens → persona SKILL**. Choose an **agent** only when the member must
wield its own tools, produce artifacts, or run isolated multi-turn builds — i.e.
it *builds*, it doesn't *judge*. If the domain's members are mostly builders, say
so plainly: you are producing an **agent-specialist panel** (fan-out delegate to
builder agents, synthesize artifacts), which is a different orchestration than a
critique council — do not force it into the council template.

**Success criteria:** Each new member is typed skill-lens or agent with a one-line
justification.

### 5. Build the missing lenses

For each BUILD-skill lens, run `personafy` end-to-end (study family → define the
load-bearing question + contrast table → mine voice/discipline from real evidence
→ draft to the **council-native lens template** → prove it steers → reduce).
Write each to `<council-bundle>/skills/<lens>/SKILL.md`.

- **Execution:** Delegate one `personafy` run per lens (parallel where the lenses
  are independent); `model_role="reasoning"`.

**Success criteria:** Each new lens has a verbatim-grounded profile, an explicit
Verdict Protocol returning `{lens,verdict,findings[],evidence[]}`, and a
Tension-With section naming its seams against the rest of the bench.
**Rule:** if two new lenses' contrast tables don't cleanly separate, one of them
isn't a lens — merge or cut.
**Artifacts:** the new SKILL.md paths.

### 6. Assemble the orchestrator

Instantiate `templates/council-orchestrator.SKILL.md.tmpl` →
`<council-bundle>/skills/<domain>-council/SKILL.md`, and the inline counterpart →
`<domain>-council-here/SKILL.md`. Fill: the bench (mandatory vs conditional
split), where each lens lives (in-bundle vs reused-cross-bundle + its
UNAVAILABLE reason string), the target class, and whether a neutral pre-digest
phase applies (repo targets → yes, like `council`; single-artifact targets → no,
like `design-council` — delete the phase and renumber down if not needed).
Preserve every trust guardrail verbatim.

Optional extension: if a recipe-driven consumer is identified (per the
`adversarial-review` / `systems-design-critic` precedent from Step 3), also
expose a thin `delegate`-able agent wrapper over the same bench for
recipe-context callers. Only add this if a real recipe consumer exists — do not
build it speculatively.

**Success criteria:** Orchestrator + here-counterpart exist, bench hard-coded,
graceful-degradation covers every reused (cross-bundle) lens.
**Rule:** keep `<domain>-council`/`<domain>-council-here` in sync — same roster,
same guardrails, only the target differs.

### 7. Scaffold the bundle and choose its home

Instantiate `bundle.md.tmpl`, `behavior.yaml.tmpl`, `awareness.md.tmpl` into a new
`amplifier-bundle-<domain>-council` (thin: includes the skills bundle + its own
behavior; behavior points `tool-skills.config.skills` at `@<bundle>:skills` and
`context.include`s the thin awareness pointer). Archetype-named council → public;
real-person-named lenses → keep those lenses in a private/team bundle and compose
by reference.

- **Human checkpoint:** confirm the bundle name and home (public vs private).

**Success criteria:** Bundle composes; awareness pointer is a thin "this council
exists, invoke /<domain>-council" — NOT the lens content.

### 8. Prove the council convenes (end-to-end)

In a FRESH session, run `/<domain>-council <realistic target>`. Confirm: roster
manifest prints first, every rostered lens LOADS (reused cross-bundle lenses
included, or degrades to UNAVAILABLE with reason), verdicts return, at least one
genuine tension is surfaced as dissent rather than averaged away.

**Success criteria:** A transcript of a real convened run — roster + attributed
verdicts + preserved dissent.
**Rule:** proof is a convened run. "The files exist" is NOT proof (the ROB gate).

### 9. Reduce and publish

Trim any restated procedure; keep guardrails and verbatim lens quotes. Run the git
lifecycle.

- **Execution:** Delegate branch/commit/PR/merge to `foundation:git-ops`.
- **Human checkpoint:** confirm before opening/merging the PR.

**Success criteria:** PR merged; then, in a clean session after `amplifier
update`, `/<domain>-council` resolves from the bundle cache — "merged" ≠ "loads
for a user."
