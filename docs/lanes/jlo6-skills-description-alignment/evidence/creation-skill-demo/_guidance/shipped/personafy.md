---
name: personafy
description: >
  Build a new opinionated advisor-persona skill — a reviewer "lens" like
  crusty-old-engineer — modeled on a real person or archetype and proven from real
  evidence. Mines the subject's authentic voice and discipline, defines its one
  distinct load-bearing question, drafts it to the family template, proves it steers
  in a live session, reduces it, and publishes it to a skills bundle. Use when
  creating or authoring a persona/advisor skill, adding a sibling to the
  crusty-old-engineer family, or turning a person's real direction style into a
  reusable reviewer skill. Also triggers on "personafy" / "personify".
user-invocable: true
shortcut: personify
model_role: reasoning
---

# Personafy

Build a new **advisor-persona skill** — an opinionated reviewer "lens" that joins an
existing family of sibling personas (e.g., `crusty-old-engineer`). The persona is
modeled on a real person or archetype, grounded in mined evidence, and enforces ONE
distinct recurring question.

**Success artifact:** a complete, family-conformant `SKILL.md` that is (a) grounded in
verbatim evidence, (b) *proven to steer* an LLM in a live session, (c) reduced to the
smallest set that still steers, and (d) loading from its target bundle in a fresh session.

## Inputs

- `<subject>`: (Optional) The person or archetype to model, plus pointers to evidence
  (session corpora, transcripts, docs). If no corpus exists, derive the persona from a
  written conceptual brief instead.
- `<family>`: (Optional) The sibling persona skills to fit alongside. Defaults to the
  advisor-persona family in `amplifier-bundle-skills` (e.g., `crusty-old-engineer`).

## Steps

### 1. Study the family

Read the existing sibling persona skills' `SKILL.md` in full. Extract: the shared section
template, the frontmatter/metadata shape, the tone-contract pattern (required / disallowed
/ style), and — critically — the single **load-bearing question** each sibling owns and how
they cross-reference each other.

**Success criteria:** You can state each sibling's distinct question in one line and
reproduce the shared template and metadata shape.

### 2. Observe the siblings in action (optional)

Run one or more existing personas live against a shared, realistic scenario — plus a
combined "consensus" run — to see how the written instructions translate into actual
behavior and steering.

- Execution: Delegate to `self` with `context_depth="none"` (one isolated run per persona).

**Success criteria:** You've *seen* how each sibling's instructions become behavior, not
just read them — enough to know what makes the steering work.

### 3. Define the load-bearing lens

Name the ONE distinct recurring question the new persona enforces. Build a contrast table
against every sibling.

**Success criteria:** A one-line lens plus a contrast table showing it is genuinely
distinct from each sibling.
**Rule:** if the question collapses into a sibling's, it is not a new persona — stop.

### 4. Mine the voice & discipline from real evidence

The heart of the method. Gather the subject's authentic voice and decision-discipline from
real data (use the conceptual fallback only if no corpus exists).

- **4a. Identify corpora and weight them** — e.g., the subject's own agent-directing
  sessions (long-term backbone) and human-to-human transcripts (enrichment). Weight recent
  material so it *informs* but doesn't *overpower* the long-term signal.
- **4b. Deterministic extraction** — pull ONLY the subject's own words. Exclude delegated
  sub-sessions (agent-to-agent), and flag/exclude automated eval-harness / smoke-test noise.
  Build a tracking directory + manifest + batches so the corpus never overflows your context.
  - Execution: `bash` (jq/grep/sed; never `cat` a huge session file — a single line can
    exceed your context window).
- **4c. Fan out scoped analysis agents** — one per batch, each following a shared evidence
  brief, writing structured findings to disk and returning only a thin summary. Many small
  agents beat one overloaded agent.
  - Execution: Delegate (parallel), `model_role="research"`.
- **4d. Two-tier synthesis** — partial synthesizers consolidate groups of findings, then a
  final synthesizer produces ONE profile: recurring traits ranked by cross-source
  corroboration, verbatim catchphrases, pet peeves, decision lenses, and the top
  "this is them" quotes. Quarantine AI-authored vocabulary (don't attribute it to the
  subject). Record confidence and which batches were synthetic.
  - Execution: Delegate, `model_role="reasoning"`.

**Conceptual fallback (no corpus):** derive the same profile fields from a written brief
about the archetype; mark everything as designed-not-mined.

**Success criteria:** A consolidated profile where every load-bearing trait is backed by a
verbatim quote (or explicitly marked as designed), ranked by corroboration, with synthetic
noise excluded.
**Rule:** ground every claim in real evidence; an honest "N/A — not observed" beats a
fabricated trait.
**Artifacts:** the profile file path.

### 5. Draft the SKILL.md to the family template

Write the skill mirroring the siblings exactly: identity (defined by negation — "not X, not
Y"), When-to-Use framed as a **cross-stage lens, not a stage-gate**, the tone contract
(required / disallowed / style), Core Behaviors each anchored in a **verbatim quote** from
the profile, an Output Structure, one worked Example, Explicit Non-Goals, a
Relationship-to-siblings section, and a Final Note. Match the family's frontmatter format.

**Success criteria:** A complete draft, structurally identical to the siblings, every
behavior grounded in the profile.
**Rule:** keep the verbatim quotes — they are the highest-signal tokens and the soul of the
persona.
**Rule:** do NOT include `allowed-tools` in the generated SKILL.md. Persona advisor skills are
inline (no `context: fork`), so the field is inert. If you must restrict tools for a fork-based
variant, use Amplifier **module IDs** (e.g. `tool-filesystem`, `tool-bash`, `tool-delegate`) —
never Claude Code tool names (`Read`, `Grep`, `Bash`, `Agent`).

### 6. Prove it steers in a live session

Run the draft in a fresh CLI session against a real-ish scenario and confirm it adopts the
voice and hits each behavior.

```bash
amplifier run --mode single --output-format text \
  "Load the skill \"<name>\" and review the following as that persona: <realistic scenario>"
```

**Success criteria:** A transcript showing the persona *behaving* as designed (voice + each
behavior firing).
**Rule:** proof is demonstrated behavior — "the file exists" is NOT proof.

### 7. Reduce & refine

Apply context-reduction: cut redundancy to the smallest set that still steers (drop restated
procedure, compress prose), but keep the verbatim quotes and the structural skeleton.
Re-prove (Step 6) if the cut was heavy.

**Check the frontmatter `description:` length, not just the body.** The Agent Skills spec
recommends a 1024-character ceiling on `description`, and Amplifier's `tool-skills` module logs
a warning past it (soft — it does not block loading or truncate anything — but every visible
skill's full `description` is injected into the model's context on every turn, so an over-long
one is a small, permanently-recurring token cost, not a one-time nuisance). Measure it (e.g.
`python3 -c "import yaml; print(len(yaml.safe_load(open('SKILL.md').read().split('---')[1])['description']))"`)
and if it's near or past 1024, compress — do not relocate the trimmed content into the body,
since the visibility hook only ever shows `description`, never the body. The single highest-value
cut is almost always the negation-identity clause (e.g. "Not a long-term ownership-cost reviewer —
a reviewer of whether THIS bet, sized as proposed, is a bet the team can actually win." compresses
to "Not a cost reviewer — a bet-sizing reviewer." with zero loss of routing signal, since the full
nuance already lives in the body's Identity section). Never cut the "Use when:" trigger list itself
— that's the part carrying the routing weight this step must preserve.

**Success criteria:** A leaner SKILL.md with the same steering power, verified, and a
`description:` field at or below ~700–800 characters (matching sibling norms like
`crusty-old-engineer`/`cranky-old-sam`) — comfortably under the 1024 ceiling, not just barely under it.

### 8. Name it and choose its home

Pick a name in the family's convention. A **shareable archetype** name (a generic role) →
a public bundle; a name that **references a real person** → a private/team bundle.

- Execution: Delegate to design/voice agents for name options (optional).
- **Human checkpoint:** the user chooses the final name and target bundle.

**Success criteria:** Name chosen and target bundle decided — public vs private matched to
whether the name exposes a real person.

### 9. Publish to the target bundle

Place `SKILL.md` at `<bundle>/skills/<name>/SKILL.md`. Verify the bundle exposes skills via
the **canonical directory-discovery** registration — its `tool-skills` config points
`config.skills` at the whole `skills/` directory (`#subdirectory=skills`), so a new skill
dir is auto-discovered. Do NOT rely on per-skill wrapper behaviors. Then run the git
lifecycle.

- Execution: Delegate the branch/commit/PR/merge to `foundation:git-ops`.
- **Human checkpoint:** confirm before opening/merging the PR.

**Success criteria:** PR merged into the target bundle.
**Rule:** a `SKILL.md` in `skills/` is NOT exposed unless the bundle points `tool-skills`
at the `skills/` directory — registration is directory-based, not per-file.

### 10. Prove it loads from the bundle

Run `amplifier update`, then load the skill in a FRESH session and confirm `loaded_from` is
the bundle cache — not a local `~/.amplifier/skills` copy.

**Success criteria:** `load_skill` resolves the skill from the bundle cache path in a clean
session.
**Rule:** "merged on main" ≠ "loads for a user" — verify discoverability end-to-end, the
same gate the persona itself would demand.
