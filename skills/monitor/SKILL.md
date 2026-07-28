---
name: monitor
description: >
  Run a bounded, self-checking polling loop (sleep -> check -> decide, repeat)
  WITHOUT ENDING THE TURN, so the turn only ends when the watched thing is done,
  has failed, or genuinely needs the user's attention -- which is what makes
  Amplifier's end-of-turn notification fire correctly and honestly. Primarily
  invoked explicitly via `/monitor <thing to watch>`, e.g. `/monitor the CI run
  for PR 412, check every 2m, stop after 1h`. May also be self-invoked (not via
  slash command) in the rare case you are about to tell the user "I'll keep
  working and let you know" for something with a genuinely checkable, bounded
  condition -- see the self-invocation guard below before doing that.
version: 1.0.0
user-invocable: true
# Deliberately NOT `context: fork`: a fork would put the loop behind a second
# session boundary even when running it in THIS turn is the right call. The
# skill decides inline-vs-delegated per invocation (Step 1) instead.
# Deliberately NOT `disable-model-invocation: true`: staying model-invocable is
# what lets the agent reach for this instead of promising follow-up it has no
# mechanism to deliver -- which is the failure this skill exists to prevent.
---

# Monitor

You invoked (or are about to invoke) a bounded polling loop for: **$ARGUMENTS**

The entire point of this skill is that your TURN does not end until one of three
outcomes is reached. Ending the turn with "I'll check and let you know" instead
of actually running this loop is exactly the failure this skill exists to prevent.
Do not do that.

## Self-invocation guard (only relevant if you were NOT explicitly told `/monitor`)

Only start this loop on your own initiative if ALL of the following hold:
1. You were about to say something like "I'll keep an eye on it / let you know
   when it's done" -- i.e. you were about to make a promise you have no other
   way to keep once this turn ends.
2. The condition is concrete and checkable right now (a command, URL, log line,
   process, CI status) -- not vague ("I'll think about it more").
3. The user asked for ongoing follow-up, not a single point-in-time answer.

If any of those don't hold: do a single check and stop, or ask the user what
"done" means. Don't silently start a multi-hour loop nobody asked for -- that
burns the user's time and locks out their session just as much as no follow-up
would have, just less visibly.

## Step 0 -- Pin down the four parameters

Before the first sleep, make sure you can state all four (ask the user only if
truly ambiguous -- most of the time $ARGUMENTS already answers this):

1. **WHAT to check** -- exact command / URL / log path / process name / CI run id.
2. **DONE condition** -- the concrete success signal.
3. **NEEDS-ATTENTION condition** -- see the list below; don't invent new ones ad hoc.
4. **Interval and max duration.**
   - Defaults if unspecified: interval = 60s, max_duration = 2h.
   - Never assume beyond 4h without the user explicitly saying so.
   - State your interval/max_duration back to the user in one line before the
     first sleep, e.g.: "Checking every 60s for up to 2h." Say this ONCE, not
     every iteration.

Say NOTHING about whether the user can or cannot reach you mid-loop. Whether
typed input is queued and delivered between iterations depends on the client,
so any claim either way will be wrong somewhere -- and claiming they can't
reach you pushes them toward a hard cancel when a sentence might have worked.
Don't raise the subject.

## Step 1 -- Decide who runs the loop. DEFAULT: a sub-agent.

**Delegate the loop** (Step 3 has the exact call) unless one of these holds:

- The user needs to watch progress happen, or wants to steer mid-flight.
- Judging "done" needs context only this session has.
- The whole monitor is shorter than ~1 minute -- dispatch overhead exceeds it.

Otherwise: delegate. Every inline poll re-sends this session's entire context
to the model, so an inline loop in a large session is the single most expensive
way to wait for something.

Either way the notification is safe: delegation BLOCKS your turn, so your turn
still ends at the moment the work resolves, and sub-session completions do not
fire their own ping. Exactly one notification -- yours -- at the right time.

## Step 2 -- The loop itself

This is what runs. Identical whether you execute it inline or hand it to a
sub-agent in the instruction. Whoever runs it does not end their turn until
one of the outcomes below is reached.

```
iteration = 0
started   = now()

loop:
  iteration += 1
  elapsed = now() - started

  if elapsed >= max_duration:
      -> STOP (timeout). Report: "No resolution after {max_duration}. Last
         check showed: {one-line summary}." End your turn now.

  # Wait. Prefer several SHORT bounded waits over one giant one:
  #   - bash `sleep` is for FINITE waits, not indefinite ones -- keep each
  #     sleep call <= ~120-240s regardless of your overall interval, and
  #     chain multiple short sleeps to reach a longer interval if needed.
  #   - if the thing you're watching is itself a long-running foreground
  #     process (a build, a server), start it with run_in_background and
  #     poll its output/exit status with quick foreground calls instead of
  #     blocking a giant sleep on it.
  wait ~interval seconds this way, then:

  check the thing with the NARROWEST command that answers the question --
  prefer exit codes / grep -c / http status codes over dumping full content
  (see token discipline below).

  classify:
    USER SPOKE      -> If a user message appears between iterations, it
                       OUTRANKS the loop. Honor it immediately -- do not
                       finish the cycle first, do not "just do one more
                       check." (Whether this can happen depends on the
                       client; handle it if it does, don't count on it.)
                         stop/pause  -> STOP now, report state, end turn.
                         change      -> adopt the new interval/target/
                                        condition and continue looping.
                         question    -> answer it, then say whether you're
                                        still watching, then continue or stop.
    DONE            -> STOP. Summarize outcome. End your turn now.
    NEEDS ATTENTION -> STOP. Explain exactly what's blocking/ambiguous and
                       what you need from the user. End your turn now.
    NOT YET         -> say nothing chatty to the user; continue the loop.
```

## Step 3 -- The delegated form (this is the DEFAULT -- see Step 1)

Every poll re-sends this session's ENTIRE context to the model. The check
output is a few bytes -- the input is everything you have ever said. In a large
session that input cost dominates everything else about the monitor.

Delegate the loop instead of running it inline:

```
delegate(
  agent="self",
  context_depth="none",     # clean slate -- this is the entire point
  model_role="fast",        # polling judgment is usually mechanical
  instruction="<complete, self-contained monitor spec -- see below>",
)
```

The child pays only the bundle's system-prompt floor per poll, not this
session's accumulated history.

**This is safe, and the notification still lands correctly:**
- Delegation BLOCKS your turn until the child returns, so your turn still ends
  at the moment the work actually resolves.
- Sub-session completions do NOT fire their own notification -- they're
  suppressed by design. The user gets exactly one ping: yours, when you relay
  the verdict and end your turn.

**What you give up:** you cannot see the child's progress, and it cannot be
steered once dispatched. Everything must be in the instruction: the exact
check command, the done condition, the needs-attention conditions, the
interval, the max duration, the verdict-line format below, and the sequential
requirement below.

**SEQUENTIAL ONLY -- state this explicitly in the instruction.** A child that
is told to make N checks may issue all N as parallel tool calls in a single
turn. Observed: a child asked for 15 checks emitted 15 simultaneous `tool_use`
blocks, so all 15 "checks" sampled the same instant. It reported success. It
had monitored nothing -- a batch of simultaneous checks can never observe a
state change.

Put this in every delegated instruction, verbatim:

```
SEQUENTIAL ONLY: Make ONE check, wait for its result, decide, then make the
next. Never issue multiple checks in the same turn. Never batch or
parallelize. Each check must observe the result of the previous one.
```

A condition-driven loop ("keep checking until X") is mostly self-protecting,
because check N+1 depends on seeing check N's result. A count-driven loop
("make N checks") has no such dependency and WILL be parallelized. Prefer
condition-driven instructions, and state the rule regardless.

**Sanity-check the result before you trust it.** A real sequential monitor
costs roughly one LLM call per check and takes at least
`interval x checks` of wall time. If the child returns far faster or far
cheaper than that math predicts, it batched -- the result is void. Re-run it
with the sequential rule stated. Measured reference: a 13-check monitor on a
`fast` model took 14 LLM calls and 100 seconds. A batched 15-check imposter
took 2 LLM calls and 18 seconds, and cost a third as much. Suspiciously cheap
is the tell.

**Dispatch latency is real -- measure your expectations against it.** In a live
run, ~40 seconds elapsed between the parent issuing `delegate(...)` and the
child's first check actually executing (session spin-up plus first tool call).
Consequences:

- A delegated monitor cannot detect anything sooner than ~40s. If the thing
  might resolve faster than that, run inline or you will simply observe it
  already finished.
- The child's first check may find the condition ALREADY met. That is a
  legitimate DONE, not a bug -- but it means the loop never exercised. Do not
  report "watched for N minutes" when the child reported one immediate hit.
- Sub-minute intervals are pointless in the delegated form for the same reason
  they are pointless inline: per-check round-trip dwarfs the sleep.

When the child returns, use ITS verdict token as YOUR first line -- your final
message is what becomes the notification, not the child's.

## What counts as "needs attention" (stop and surface -- don't guess, don't grind)

- The **check itself** fails 2+ times in a row (distinct from the thing being
  watched failing) -- your monitoring mechanism is broken; don't loop blind.
- The condition is **unambiguously failed** (build failed, process crashed,
  a non-transient error) -- don't keep polling something that's already dead.
- You still can't tell done-vs-not-done after refining the check twice --
  irreducible ambiguity is itself a reason to stop, not a reason to keep trying.
- Proceeding would require a **destructive or irreversible decision** -- never
  make that call unattended; stop and ask.

## Token / context discipline

- Do not paste full log or command output into your visible response on every
  iteration. Read/check silently via tool calls; only surface a summary when
  you stop.
- Prefer small structured signals over full dumps: exit codes, `grep -c
  <marker> file`, `curl -o /dev/null -w '%{http_code}'`, `tail -n 20` instead
  of `cat`.
- This loop will generate many tool-call/result pairs in this session's
  history. That's expected and the system's compaction is explicitly designed
  to truncate old tool results first -- keeping each check's output small
  keeps compaction cheap and keeps your OWN reasoning focused.

## If the system gives you an iteration-limit / wrap-up reminder

Honor it. Treat it as an effective early stop even if you haven't hit your own
max_duration yet -- report status honestly, including that the turn's own
iteration budget capped you sooner than max_duration, and suggest the user
re-run with a longer interval / shorter max_duration next time if they want a
single turn to cover more ground. Do not try to argue past a wrap-up reminder.

## Escalation message shape (when you stop for DONE / NEEDS ATTENTION / TIMEOUT)

**Your final message IS the notification.** Verified mechanically: the desktop /
terminal / phone notification body is built from the **first ~100 characters of
your last assistant message**. Everything past that is invisible to someone
glancing at a phone or a background pane -- which is the entire audience for
this skill.

So the FIRST LINE must be verdict-first and under 100 characters, starting with
one of exactly four state tokens:

```
DONE: CI green on PR 412, 318 tests passed
NEEDS YOU: deploy blocked on manual approval gate, job 4471
GAVE UP: 2h elapsed, endpoint still returning 502
PAUSED: stopped watching at your request -- run still going, 4/110 sources
```

`PAUSED` is for when the user told you to stop watching. Be explicit that you
stopped WATCHING, not that you stopped the thing being watched -- those are
different, and confusing them will make the user think you killed their job.

Rules for that first line:
- State token first. No preamble, no "I've finished monitoring and...".
- The single most decision-relevant fact, not a summary of your process.
- No semicolons -- they are stripped by the notification sanitizer.

THEN, on following lines: what you observed (one line), how long you watched,
how many checks you made. Do not restate the whole poll history.

---

@foundation:context/shared/common-agent-base.md
