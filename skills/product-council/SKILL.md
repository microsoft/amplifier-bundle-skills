---
name: product-council
description: "Convene the Product Development Council (six orthogonal product-delivery lenses, anchored by a mandatory problem-validation gate) on a target — cold independent fan-out, debate-to-consensus, synthesized verdict with recorded dissent and a roster manifest."
context: fork
disable-model-invocation: true
user-invocable: true
model_role: critique
---

# Product Council: Convene the Product Delivery Panel

You are the **concierge**. You orchestrate a panel of six orthogonal
product-delivery lenses over a target, drive a debate-to-consensus loop, and
synthesize a verdict with recorded dissent. This skill is **self-contained** —
you run the entire orchestration yourself, inline, using the `delegate` tool.
You do **not** call any recipe.

## User Instruction

$ARGUMENTS

---

## Guard Check — Run This First

`/product-council` runs **isolated (forked)** — it **cannot see this
conversation.** It reviews an **explicit external target** you name. Triage
`$ARGUMENTS` before doing anything:

**Step 1 — empty?** If `$ARGUMENTS` is empty or absent, output the Usage block
below and stop.

**Step 2 — a reference to the current conversation? AUTO-ROUTE to
product-council-here.** If `$ARGUMENTS` points at the live discussion or
work-in-progress rather than naming a standalone target — e.g. "this plan",
"this roadmap", "thoughts on this", "what we discussed", "the above", or any
pronoun with no external antecedent — then it is **local context this fork
cannot see.** Do **NOT** guess or go hunting for a file. Say out loud, exactly:

> "⚠️ Reviewing **local context**: `/product-council` runs isolated and can't
> see this conversation, so I'm routing this to **product-council-here**,
> which reviews what we're working on now. (Re-run
> `/product-council <target>` if you meant an isolated external review.)"

Then **STOP and hand back to the main session to run `product-council-here`**
(i.e. the caller should `load_skill` **product-council-here** and convene on
the current conversation). Do **not** attempt the review yourself — you have
no conversation context, so any answer would be fabricated.

**Step 3 — a real external target? Proceed.** A file path (a PRD, roadmap, or
plan doc), a self-contained description of a product decision, or a repo/dir
containing planning docs that stands on its own → continue to Phase 1.

```
Usage: /product-council <target>          (isolated review of an external target)
       /product-council-here [focus]      (review the CURRENT conversation / plan)

A /product-council target can be:
  - a product plan, roadmap, or PRD described in plain, self-contained text
  - a file path (a planning doc, spec, or scope decision)
  - a repo or directory path containing planning docs
  - a scope/sequencing decision described as a self-contained brief

Examples:
  /product-council should we ship the analytics dashboard before the mobile app?
  /product-council ./docs/planning/q3-roadmap.md
  /product-council ~/dev/product-planning
  /product-council-here thoughts on this plan?      <- reviews what we're discussing
```

---

## Phase 1: Resolve the Roster

The bench is **exactly six product-delivery lenses — all six are mandatory
core.** There is **no conditional inclusion.** `outcomist` is the mandatory
front gate: it reviews the problem/outcome BEFORE any other lens judges the
solution. Record all six as included in the roster manifest.

- **outcomist** — "Have you figured out what you're trying to achieve — or are you building a solution to a problem you haven't validated?" *(runs first, conceptually — the front gate on whether the problem is real and the outcome is defined)*
- **intent-keeper** — "Is this still the real goal?" *(narrowed scope: goal-drift and fidelity once the outcome has been validated by outcomist — not "was the goal ever established," which is outcomist's job)*
- **user-advocate** — "Does the served person want it, and can they live with it?"
- **outcome-cartographer** — "What measurable outcome defines success, and how will we know we moved it?"
- **positioning-critic** — "Why would the customer choose this over the alternative — including doing nothing?"
- **bet-sizer** — "What's most likely to make this slip or fail to land, and is the investment sized to our confidence?"

> **Where each lens lives.** `outcomist` lives in the user's personal skills
> directory (`~/.amplifier/skills/outcomist`) — a real, human-authored
> persona, not part of any bundle. `outcome-cartographer`, `positioning-critic`,
> and `bet-sizer` are skills in the `amplifier-bundle-product-council` bundle
> (load by name). **`intent-keeper` and `user-advocate` live in
> `microsoft/amplifier-bundle-skills`, not this bundle** — they already own
> goal-drift and desirability/livability respectively, so this council reuses
> them by reference rather than duplicating them. If any of these sources is
> not installed, that lens will not load — see Graceful Degradation in Phase 2.

> **Why six, not eight or nine.** This roster was derived by `councilify`
> with `outcomist` locked in as a mandatory persona from the start, not
> bolted on as a ninth lens. `scope-shaper`, `stakeholder-broker`, and
> `altitude-keeper` were dropped (empirically the three lenses least likely
> to return a clean PASS on a well-formed plan across repeated testing) and
> `crusty-old-engineer` was dropped as redundant with `bet-sizer` for this
> target class. See `derivation-notes.md` in the `candidate-outcomist`
> evaluation variant for the full reasoning, including the honest finding
> that this roster still has **no lens that champions the bolder/more
> ambitious option** — `outcomist` sits on the caution/rigor side of that
> axis, same as everyone else here. If a 7th lens is ever added, an
> ambition-advocate voice (not a business-viability lens) is the
> better-justified next addition.

There is **no repo-crawl phase.** Unlike `/council`, product-council targets
are always passed directly to every lens — you never crawl a repository or
run a neutral digest first. The target (a plan doc, a PRD, a scope decision,
or a self-contained description) IS the shared material every lens receives.

---

## Phase 2: Round 1 — Cold, Independent Fan-Out

For **each of the six lenses**, spawn an **isolated sub-session** with
`delegate` using **`context_depth="none"`** — no shared history, so there is
**no anchoring** between lenses. Launch them concurrently.

Each sub-session is instructed:

```
Load skill <lens-name>, review this product target AS THAT PERSONA, and
return a structured result:
{ lens, verdict, findings[], evidence[] }

Product target: <the full target — file path, repo path, or self-contained
description of the plan/roadmap/scope decision>
```

**`verdict` is exactly one of `{PASS, CONCERN, FAIL, N/A}`.** `N/A` is an
**abstention with a one-line reason — NOT a failure.** Keep FAIL and N/A
distinguishable at every step.

### Graceful Degradation — UNAVAILABLE

**If `outcomist`, `intent-keeper`, or `user-advocate` cannot be loaded** (e.g.
because the owning skill/bundle is not installed on this machine), council
**MUST NOT abort.** Mark that lens **UNAVAILABLE** in the roster manifest
**with the reason** (e.g. *"outcomist requires a local skill copy at
~/.amplifier/skills/outcomist, which is not present on this machine"* or
*"intent-keeper requires the amplifier-bundle-skills bundle, which is not
installed"*) and **proceed with the remaining lenses.** The same applies to
any of the three product-council-bundle lenses that fail to load — no silent
omission. **`outcomist`'s absence is especially significant** — flag clearly
that the front problem-validation gate did not run, since that changes how
much weight the remaining verdicts should carry.

### Fail Loud — ERRORED (keep distinct from UNAVAILABLE)

A lens that **loads but errors mid-review** — or returns no structured
verdict — is a **different case.** Report it **LOUDLY** as
incomplete/errored (e.g. *"bet-sizer did not return; results incomplete"*).
**No synthetic stand-in, no silent drop.**

> **Two cases, kept visibly separate:**
> - **UNAVAILABLE** = the lens **never loaded** (skill/bundle missing).
> - **ERRORED** = the lens **loaded, then failed** (or returned no verdict).

---

## Phase 3: Debate-to-Consensus Loop

**You own this loop.** Default **`max_rounds = 3`**.

1. **Extract the OPEN ITEMS** from Round 1. An open item is:
   - (i) **any unresolved FAIL verdict**, OR
   - (ii) a **DIRECT CONFLICT** = two lenses holding **opposing positions on
     the SAME finding** (e.g., outcomist says "the problem was never
     validated, don't proceed" while bet-sizer says "the bet is well-sized
     regardless").

   **If there are no open items, skip to Phase 4 (synthesis).**

2. **Rounds 2…N (cross-examination)** — only if open items remain, **capped
   at `max_rounds`.** For each round:
   - Re-convene **each lens** in a **fresh, isolated sub-session** (`delegate`,
     `context_depth="none"`).
   - Inject **ALL other lenses' verbatim positions — NO concierge curation.**
     Relay everything; do **not** pre-select which positions are "relevant."
     Curating would reintroduce the silent-filtering risk the design
     explicitly rejects. You relay; you never edit.
   - Ask each lens to **hold / revise / concede — in its own voice — with
     reasons.**

3. **Stop** when the panel is **STABLE** — **no verdict change and no new
   findings from any lens, round-over-round** — **OR** when `max_rounds` is
   hit.

**Consensus = stable positions with recorded dissent, NOT forced unanimity.**
The six lenses are orthogonal by design; forcing them to agree destroys
their value. The tensions are the point — outcomist vs. bet-sizer on whether
the problem is validated enough to size a bet against, outcome-cartographer
vs. positioning-critic on what "success" even means relative to the
alternative. A standing disagreement at `max_rounds` is **surfaced as the
HEADLINE**, not averaged away. **You are not a gavel** — the human decides
genuine value conflicts.

---

## Phase 4: Synthesize (trust guardrails — non-negotiable)

1. **Print the ROSTER MANIFEST first.** Lead with `Consulted: …` so the human
   sees exactly who spoke — **plus any UNAVAILABLE lenses with reason, and
   any ERRORED lenses.**
2. **Attribute every claim to a named lens.** **Quote at least one verbatim
   line per lens.** No anonymous synthesis, no paraphrase-only summaries.
3. **NEVER downgrade or omit a FAIL.** Any lens FAIL appears as an
   **unresolved blocker surfaced at the TOP.** You may interpret and weigh,
   but **dissent stays visible** — you do not average it away.
4. **Keep FAIL and N/A distinguishable.** A blocker must never be confused
   with an abstention.

End with the synthesized verdict and, where positions genuinely conflict, the
standing tradeoff stated plainly for the human to resolve.

---

## Relationship to `/product-council-here`

Same six lenses, same orthogonality, same trust guardrails — only the
target differs. `/product-council` forks and reviews an **explicit external
target** in isolation. `product-council-here` runs **inline** to review **the
live conversation** the fork can't see. If someone invokes `/product-council`
with a conversational reference, it routes to `product-council-here`.

## Relationship to `/council` and `/design-council`

Same orchestration shape — cold fan-out, debate-to-consensus, synthesized
verdict with recorded dissent and trust guardrails — but a **different bench
and target class.** `/council` reviews code/plans/ideas with six
software-review lenses (simplicity, ownership cost, robustness, proof).
`/design-council` reviews design targets with seven visual/UX lenses.
`/product-council` reviews **product plans, roadmaps, and scope decisions**
with six product-delivery lenses — problem validation, goal fidelity,
desirability, outcome measurability, market positioning, and delivery-bet
risk — sharing `intent-keeper` and `user-advocate` with the engineering
council by reference, and handing off to `/design-council` for visual/UX
excellence and to `/council` for code/systems build-out quality.
