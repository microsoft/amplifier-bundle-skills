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

### 2. Derive the domain's ideal roster — BLIND to the existing inventory first

Name the domain's **target class** (what artifact does this council review?) and
**stage** (when in the lifecycle?). Then derive, independently of what already
exists, the distinct perspectives that domain genuinely demands — mining real
domain-leadership archetypes for each. For each candidate: one load-bearing
question, the archetype/framework it's grounded in, and a one-line voice.

**Do this before looking at the installed skill inventory.** Naming what already
exists first biases the derivation toward "what we have" instead of "what the
domain actually needs" — the two can look similar, but a roster built the second
way is more likely to contain the ideal makeup rather than a locally-convenient
one.

- **Execution:** Delegate parallel `model_role="research"` agents to gather
  archetype evidence per candidate lens; each writes findings to disk, returns a
  thin summary. Explicitly instruct each research agent NOT to consult or let
  its own visible skill list bias which perspectives it proposes — derive from
  the domain's real leadership archetypes and literature, not from what
  happens to already be installed.

**Honest limitation, stated plainly (verified directly, not assumed):** on this
platform, a `delegate`-spawned sub-session — even with `context_depth="none"` —
still receives an unconditional `hooks-skills-visibility` system-reminder
listing dozens of installed skill names, regardless of what it was told or
asked to do. This was confirmed by direct test: a cold, context-free sub-agent
reported seeing the full skill list before any instruction reached it. **True
technical isolation from the inventory is not currently achievable via
`delegate` alone on this platform.** Treat the "don't consult the inventory"
instruction above as a *policy constraint you are asking the model to honor*,
not an architectural guarantee — and say so if you rely on it. If a stronger
guarantee is ever needed, that requires a different mechanism than same-platform
`delegate` (e.g., an external process with no skill-visibility hook at all);
don't claim isolation you haven't verified holds.

**Success criteria:** A candidate list where each entry has ONE question grounded
in a named archetype, not a vibe — derived from the domain's real needs first.

### 3. Reconcile against the installed inventory — route every candidate

Only now enumerate the FULL installed inventory: `load_skill(list=true)` for all
lens skills, and identify every existing panel — `council` (6: intent-keeper,
cranky-old-sam, crusty-old-engineer, restless-old-brian, user-advocate,
tester-breaker), `design-council` (7 design lenses), `adversarial-review` (6:
SRE, security, staff engineer, finance, operator, developer advocate —
production/operational risk of a system design; note it also ships a
recipe-callable `systems-design-critic` agent form of the same bench, a third
composition pattern worth considering in Step 6's optional extension), plus any
others surfaced by the inventory scan.

Build a **coverage matrix**: the Step 2 candidate list × existing lenses. Route
each candidate to exactly one of:
- **REUSE** — an existing lens already owns this exact question → compose by
  reference; record its home bundle + graceful-degradation note.
- **BUILD-skill** — a real, distinct review question with no owner → Step 5.
- **BUILD-agent** — not a review lens at all but an *active builder/specialist*
  → Step 4.

**Don't let reconciliation silently re-inflate what Step 2 derived as ideal.**
If an existing lens is a near-but-imperfect match for a Step 2 candidate,
check whether it's a genuine REUSE or whether accepting it is convenience
posing as fit — a real mismatch is still a BUILD, even if something adjacent
already exists.

Then apply the **needs-its-own-council test** (all three required): distinct
target class; ≥4–5 net-new orthogonal lenses; folding them into an existing bench
would make it incoherent or oversized (>~8). If it fails, STOP and recommend
`personafy`-ing the 1–2 new lenses into the existing council instead.

**Don't fix the headcount before this step produces it.** Naming a target
number ("we want N lenses") before deriving the roster is the same bias this
step exists to prevent, aimed at a different constraint — the count is an
output of Steps 2–3, not an input to them. If real evidence (multiple
independent derivations, actual usage history, a genuine overlap check) later
argues for a different count than what a single pass produced, that's a reason
to re-derive, not to trim or pad toward a number decided in advance.

#### Bench-size guidance (a strong default, not a gate)

Grounded in the real benches confirmed in this ecosystem, not invented round
numbers: `council` runs exactly 6 (intent-keeper, cranky-old-sam,
crusty-old-engineer, restless-old-brian, user-advocate, tester-breaker) —
confirmed directly from its own `SKILL.md`. `adversarial-review` runs exactly
6 (SRE, security, staff engineer, finance, operator, developer advocate) —
confirmed via its own declared skill description, surfaced live in-session (its
source file was not available to inspect directly, so this is a
metadata-level confirmation, not a file-level one — say so if you're ever in
the same position). `design-council` runs exactly 7 — confirmed directly from
its own `SKILL.md`. A `product-council` instance in this ecosystem grew from 7
to 8 after a genuinely orthogonal 8th lens passed the collapse-test gate
against its single closest neighbor — confirmed directly from its own
`SKILL.md` and bundle.md, which both flag 8 explicitly as "the edge, not the
comfortable middle" of the range below.

From these four real data points — **6, 6, 7, 8** — treat as a strong default:

- **Hard floor ~4.** Below four lenses, you don't have enough irreducible
  perspectives to justify calling the thing a "council" rather than just
  adding a couple of extra reviewers to whatever bench already exists — the
  orchestration overhead (roster manifest, cold fan-out, debate-to-consensus
  machinery) stops paying for itself. No confirmed bench in this ecosystem
  runs below 6; treat 4 as the line below which you should stop and ask
  whether this needs the council mechanism at all, not just a smaller one.
- **Typical/comfortable range 5–7.** Brackets all three of the smaller
  confirmed working benches (6, 6, 7) — the load a synthesizer can hold in
  its head, attribute every claim to, and quote verbatim from, per lens,
  without the Phase-5/Phase-4 synthesis guardrails becoming unwieldy.
- **Soft ceiling ~8.** `design-council`'s 7 is the largest *comfortable*
  confirmed precedent; the one 8-lens bench on record explicitly flags
  itself as sitting at the edge of the range, not inside it. Above 8, the
  cost of full cold fan-out (every lens spawned in an isolated sub-session)
  and the cognitive load on the human reading the synthesis both start to
  degrade faster than the added orthogonality is worth — that's the signal
  to fold an overlapping lens into a sibling, or split into two councils
  with genuinely distinct target classes, rather than keep growing one
  bench.

**This is guidance for your judgment in this step, not a hard-coded gate.**
Trust the model with the *why*, not a rigid headcount: if a candidate lens
genuinely passes the orthogonality/collapse-test gate — a real, distinct,
evidence-grounded load-bearing question with no existing owner — that is
stronger evidence than a round number, and the bench should grow to fit the
evidence, exactly as `product-council` did going from 7 to 8. The moment a
9th genuinely-orthogonal candidate shows up for any bench, treat that as the
trigger to seriously reconsider whether it's still one council — not a
reason to silently wave the 9th one in past the ceiling above.

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
