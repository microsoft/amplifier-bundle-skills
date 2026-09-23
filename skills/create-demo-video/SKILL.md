---
name: create-demo-video
description: >-
  Produce a narrated demo video that shows something the user made or built,
  cut from recordings they supply or recordings made to their direction. Use
  when showing a product, feature, tool, or project in action, including
  explainers built around a live demo. Not for slide-style explainers; for a
  single trim or audio cleanup, use the relevant tool directly.
---

# Create a Demo Video

Show the thing working. Build every demo scene from a recording of it, never
from slides or static screenshots standing in for it. Settle the storyboard and
narration before detailed visual timing, then review one canonical export end
to end.

## Harness

Drive this workflow from a harness running a strong reasoning model, such as
the Amplifier CLI with `gpt-6-astra` at high reasoning effort or Claude Opus 5.5.
The workflow depends on sustained judgment across footage, narration timing,
and review.

## Tools

Install the `smart-tools` skill from
[microsoft/amplifier-smart-tools](https://github.com/microsoft/amplifier-smart-tools):

```bash
npx skills add microsoft/amplifier-smart-tools
```

For the Amplifier app CLI, add the Smart Tools behavior instead:

```bash
amplifier bundle add 'git+https://github.com/microsoft/amplifier-smart-tools@main#subdirectory=behaviors/smart-tools.yaml' --app
```

Load it to access the catalog and each tool's installation, prerequisites, and
usage guidance:

- **vid:** edit plans, assembly, rendering, and export verification.
- **aud:** speech cleanup, mastering, and loudness/peak verification.
- **unfold:** silent animations with editable source.
- **showrun:** recorded walkthroughs of a running web app or terminal.
- **Stories:** storyboards and speech synthesis. Prefer Gemini 3.1 TTS
  (`gemini-3.1-flash-tts-preview`); audition a short passage to choose the voice.
  Master the resulting speech with aud.

Call the smart tool that owns each step: Stories for the storyboard and
narration, Showrun for recordings, aud for mastering, Unfold for animation, and
vid for video edits. Do not reimplement a tool's work with hand-written commands
or scripts; use scripts only to chain smart tool capabilities into repeatable
builds.

## Workflow

Before step 1, run `--help` for each smart tool the video will use: `stories`,
`showrun`, `aud`, `unfold`, and `vid`. Follow what the help says about setup,
capabilities, and arguments in every later step.

### 1. Create the storyboard with Stories

Inspect existing scripts, recordings, artwork, and credits. Establish the
audience, takeaway, runtime limit, and destination; ask only for missing
decisions. Use 1080p at 30 fps unless the brief calls for another format.

Start with a hook, a tour of visible results, a short synthesis, and a closing
action. Give each demo one spoken point and footage that proves it. Reuse chosen
branding; otherwise compare a few small layout previews and voice samples
before applying a direction throughout.

Build the storyboard in Stories. Use `create-storyboard` to import a script the
user already has, or `generate-storyboard` to develop one from the brief. Set
`explore` only when the user asks to compare directions. Each panel is one
scene:

- `id`: stable scene ID.
- `action`: the point the scene makes.
- `visual`: what is on screen: a recording excerpt with file and in/out times,
  an Unfold animation such as an opening title or concept diagram, a title
  card, or a combination.
- `narration`: the spoken line.
- `notes` (optional): on-screen text, such as titles, animation labels, and
  subtitles.
- `production_requirements` (optional): recordings or animations still to make.
- `asset_id` (optional): a still frame from the recording.

A direction holds up to eight panels; for a longer video, make each panel a
section and list its scenes in `visual` and `narration`. Share the storyboard
through the Stories dashboard with a short voice sample, and wait for the user
to approve both before recording or generating narration, unless the user has
said to proceed without review. The storyboard is the source of truth for every
later step. Apply changes with `revise-storyboard` and rebuild from the latest
revision.

Use the scene IDs to connect on-screen sources, narration, and review
timestamps. Preserve original assets, animation source, and generation
settings; separate caches from rebuild inputs.

**Success criteria:** Each scene has a purpose, an on-screen source, and a
narration line, the total fits the runtime budget, and the user has approved the
storyboard and voice or waived review.

### 2. Get the recordings

Use recordings the user supplies, or make recordings of what the user wants to
show. Long, unedited captures are fine; step 4 cuts them down. Make recordings
with real screen capture of the thing running, using Showrun for web apps and
its terminal mode for command-line demos. Seed realistic demo data first so
screens do not start empty. Record a trial take before the real one, especially
when a take spends money or time. Start each take with the screen and scrollback
cleared, keep terminal takes to one or two commands, and check the receipt that
every step shows a first interaction. Use Showrun's receipts, which time each
action and wait, to choose cut points. Share takes with the user through
Showrun's review dashboard before cutting them. Only substitute simulated or
animated footage when the user explicitly asks not to use real screen capture.
If a storyboard beat cannot be recorded because the thing lacks it, tell the
user rather than faking it.

**Success criteria:** Every demo scene in the storyboard maps to a recording
that shows it happening.

### 3. Finish narration before timing visuals

Clean supplied speech or generate one clip per scene with consistent voice
settings. Check the speech provider's quota before auditioning voices;
auditions spend the same budget as the final narration. Generate all lines with
one provider so the voice stays consistent. Use aud to master the clips; -16
LUFS and a -1.5 dBTP ceiling are useful starting points. Inspect the
verification results, and leave judgments of voice quality to the person
reviewing in step 7. Retain raw and mastered clips; regenerate only changed
lines.

Measure speech and set scene durations with breathing room. If the video runs
long, shorten copy and remove redundant beats before speeding up speech or demos.
Keep spoken copy and on-screen claims synchronized. Regenerated speech requires
new timing cues, including any timestamp-based breath or pause edits.

**Success criteria:** Narration sounds consistent, fits each scene without
clipping, and leaves the complete video within its runtime budget.

### 4. Cut demos around the result

Cut with vid's trim, cut, and retime verbs. Show enough setup to explain the
action, meaningful progress, and a readable result. Remove waiting and
repetition; accelerate only where viewers can still follow. Judge the excerpt at
delivery size and speed.

Preserve the full recording and aspect ratio unless a deliberate crop is wanted.
Where vid supports it, introduce the name, author, and description beside the
recording, then expand it smoothly to full screen while playback continues. A
2.5-second introduction and 0.9-second expansion are a useful starting point.
Otherwise open the scene with a title card. Hold final outputs long enough to
understand them.

**Success criteria:** Every excerpt supports its spoken point without hiding
content or rushing past the useful result.

### 5. Animate to the measured narration

Give Unfold the meaning, exact labels, palette, canvas size, frame rate, duration,
reveal timestamps, and final hold. Request silent output. For explanations, build
a stable diagram that reveals concepts in spoken order. Check a short prototype
before rendering the full sequence. Unfold `create` runs for minutes; run
creates one at a time with a timeout long enough to finish, not as background
jobs the harness may kill.

Retain editable source and dependencies. Make narrow text, alignment, and timing
changes there instead of regenerating the animation. Recompute cues when speech
changes. Inspect encoded frames at reveals, transitions, and the ending for
collisions, misleading arrows, small text, and blank frames. Share animations
with the user through Unfold's dashboard and apply their notes with Unfold's
refinement before assembly.

**Success criteria:** The animation matches the narration, remains readable,
and holds a complete final composition.

### 6. Assemble and mix

Build the whole video as one vid pipeline: stitch the scenes with vid
transitions, lay the narration in with vid's audio verbs, and render once.
Save the plan from `vid plan` with the project so the edit can be reviewed and
replayed.
Account for transition overlaps so later narration does not drift; extra
outgoing footage can compensate for an overlap. A dissolve crossfades audio as
well as picture, so start each scene's narration after its incoming transition
ends, or use a hard cut where a line must start immediately. Keep audio within
the picture's duration without cutting speech.

Mute recording audio only where voiceover replaces it. Where recorded and
synthetic voices meet, add the handoff to the checks for a person in step 7.

**Success criteria:** The export has the intended runtime, dimensions, frame
rate, and audio, with aligned transitions and intelligible speech.

### 7. Review and revise the complete video

Run the tool checks yourself: `vid verify` on the render, `aud verify` on the
final mix, a transcription of the mix compared against the storyboard
narration, and frames sampled at every scene boundary and in the final seconds.
Look for black flashes, clipped speech, frozen endings, and abrupt cutoffs. On
dark palettes, `vid verify --expect-no-black-frames` can flag designed frames;
confirm with the sampled frames before treating them as a defect. If `aud verify`
misses the loudness target, master the extracted mix with aud, swap it in with
`vid audio replace`, and render again; this is the one expected second render.
Model reviews of picture or sound do not replace a person. List the checks only
a person can make, such as pacing, voice quality, and whether the demo is
convincing, as open items in the delivery report.

Keep one canonical video for feedback, addressed by scene or timestamp. Revise
the saved vid plan and rebuild only affected assets before rendering the full
export again.

Create a local HTML review player for the canonical MP4. Include:

- A video player with playback, seeking, volume, and fullscreen controls.
- Selectable closed captions, enabled by default when captions are requested.
  Build the caption file from the storyboard narration and the scene timeline.
- Scene buttons labeled with each scene's start time and title from the
  storyboard. Clicking a button seeks to that scene and starts playback.
- Links to download the MP4 and caption file, and to view the storyboard.
- A responsive layout using the video's branding, with the player above the
  scene buttons.

Save the player as `index.html` alongside the video and caption files. Serve it
on localhost and open it for review. Start paused so the user controls playback.
Keep one canonical video and update the player's scene timings whenever the edit
changes.

Verify that the video plays, captions display correctly, and every scene button
seeks to the intended moment. Deliver the MP4 as the primary artifact and link
the review player as the feedback surface. The review player is supporting HTML
created by the coordinating agent; it does not need to come from a smart tool.

Keep review aids, the storyboard, original assets, animation sources, and
rebuild commands with prerequisites in the project rather than bundling them
into an archive. Report what was actually verified and any viewing or listening
checks that still need the user.

**Success criteria:** The complete video meets the brief and can be revised
without reconstructing the project.
