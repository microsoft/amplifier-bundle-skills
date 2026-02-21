---
name: image-vision
description: "Analyze images using LLM vision APIs (Anthropic Claude, OpenAI GPT-4, Google Gemini, Azure OpenAI). Use when tasks require: (1) Understanding image content, (2) Describing visual elements, (3) Answering questions about images, (4) Comparing images, (5) Extracting text from images (OCR). Provides ready-to-use scripts - no custom code needed for simple cases."
license: MIT
---

# Image Vision Analysis

## Overview

Analyze images using state-of-the-art LLM vision models. **Use the provided scripts** for most tasks - custom code only needed for advanced scenarios.

## Workflow Decision Tree

### First time using this skill?
→ Read [`setup.md`](setup.md) for one-time environment and API key setup

### Simple image analysis (most common)
→ Use "Quick Start" canned scripts below

### Batch processing or multi-turn conversations
→ Read [`patterns.md`](patterns.md) for advanced patterns

### Something failing?
→ Check setup.md for troubleshooting

## Quick Start (Use Wrapper Scripts)

**ALWAYS use the wrapper scripts** - they handle venv setup automatically:

```bash
# Simple analysis (auto-creates venv on first use)
./vision-analyze.sh <provider> <image_path> <prompt>

# Robust analysis (auto-fallback if provider times out)
./vision-analyze-robust.sh <image_path> <prompt> [timeout_seconds]
```

**The wrapper scripts automatically:**
- Create venv if it doesn't exist
- Install required SDKs
- Use venv Python (no manual activation needed)
- Handle errors gracefully

**Example usage:**

```bash
# Analyze a UI screenshot (Anthropic Claude)
./vision-analyze.sh anthropic screenshot.png "Describe any UI bugs or issues you see"

# Extract text (Google Gemini - fastest)
./vision-analyze.sh gemini document.jpg "Extract all text from this image"

# Robust analysis with auto-fallback (tries Gemini → Anthropic → OpenAI)
./vision-analyze-robust.sh photo.png "Describe this image in detail"

# With custom timeout (default is 60 seconds)
./vision-analyze-robust.sh large-image.png "Analyze this" 120
```

### Advanced: Direct Script Usage (Not Recommended)

If you need to call the Python scripts directly, you MUST use the venv Python:

```bash
# ❌ WRONG - uses system Python, will fail
python examples/anthropic-vision.py image.png "prompt"

# ✅ CORRECT - uses venv Python
./.venv/bin/python examples/anthropic-vision.py image.png "prompt"
```

**For agents:** Always use the wrapper scripts to avoid setup issues.

## Provider Comparison

| Provider | Model | Best For | Speed | Cost |
|----------|-------|----------|-------|------|
| **Anthropic** | claude-sonnet-4-5 | Latest, balanced quality/speed | Fast | $$ |
| **Anthropic** | claude-3-opus | Highest quality (older) | Slow | $$$ |
| **Anthropic** | claude-3-haiku | Fastest, simple tasks | Very Fast | $ |
| **OpenAI** | gpt-5 | Latest flagship model | Fast | $$$ |
| **OpenAI** | gpt-4.1 | High-volume production | Fast | $$ |
| **Gemini** | gemini-2.5-flash | Latest, excellent balance | Very Fast | $ |
| **Gemini** | gemini-2.5-pro | Large images, best quality | Medium | $$ |
| **Azure** | (deployment-based) | Enterprise, compliance | Varies | Varies |

## Supported Image Formats

- **JPEG/JPG** - Most common
- **PNG** - With transparency
- **GIF** - Static or animated
- **WEBP** - Modern format

**Max sizes:**
- Anthropic: 5MB per image
- OpenAI: 20MB (auto-resizes)
- Gemini: Varies by model (1.5 pro handles very large)

## Common Use Cases

```bash
# UI/UX Analysis - High-level layout and spacing
./vision-analyze.sh anthropic app-screenshot.png \
  "Analyze this UI for accessibility issues and suggest improvements"

# Bug Identification (use robust for auto-fallback)
./vision-analyze-robust.sh error-state.png \
  "What's wrong with this interface? Describe any visual bugs."

# Content Moderation
./vision-analyze.sh openai user-upload.jpg \
  "Does this image contain inappropriate content? Yes or no, and explain."

# Document Understanding (Gemini is fastest)
./vision-analyze.sh gemini invoice.png \
  "Extract the total amount, date, and vendor name from this invoice"

# Design Review - Layout, color, hierarchy (not typography details)
./vision-analyze-robust.sh mockup.png \
  "Provide design feedback on this mockup. Consider layout, color hierarchy, and spacing."
```

## ⚠️ Known Limitations for Web UI Analysis

### Typography and Font Detection

Vision models **struggle with precise typography** at typical screenshot resolutions:

**❌ Unreliable for:**
- Distinguishing serif vs sans-serif fonts at small sizes (<16px)
- Identifying specific font families (Inter vs Roboto vs Arial)
- Detecting subtle weight differences (400 vs 500)
- Precise alignment measurements (<5px differences)

**✅ Reliable for:**
- High-level layout issues (spacing, hierarchy, colors)
- Large size differences (14px vs 24px heading sizes)
- Missing elements or obviously broken UI states
- Color contrast and accessibility problems

### Best Practice: Multi-Modal Investigation

**For Web UI bugs, use this hierarchy:**

```bash
# 1. Vision for TRIAGE (identify area of concern)
./vision-analyze-robust.sh screenshot.png "Are there any visual inconsistencies in the navigation?"

# 2. Browser inspection for FACTS (if typography/font suspected)
# Use Playwright or DevTools to query computed CSS:
# const styles = await page.evaluate(() => ({
#   fontFamily: getComputedStyle(element).fontFamily
# }));

# 3. Code investigation for ROOT CAUSE
# grep -r ".suspicious-class" src/

# 4. Vision for VERIFICATION (after fix applied)
./vision-analyze-robust.sh fixed.png "Is the navigation font now consistent?"
```

### When to Stop Using Vision

If vision gives **contradictory results** across 2+ attempts on similar screenshots:
1. **Stop** asking vision for more detailed analysis
2. **Switch** to browser DevTools inspection (query computed styles)
3. **Use vision only** for final verification after fix is applied

This indicates the issue is too subtle for vision models to detect reliably.

### Prompt Patterns for Web UI

**Font/Typography (with caveats):**
```bash
# Be explicit about what to look for
./vision-analyze.sh anthropic ui.png \
  "Look at the navigation text. Do any items have decorative 'feet' at letter ends (serif font) 
  while others have clean straight edges (sans-serif)? Point out any font style differences."
  
# Note: Small fonts may be unreliable - verify with browser inspection
```

**Alignment (relative observations):**
```bash
# Ask for noticeable differences, not pixel precision
./vision-analyze.sh anthropic ui.png \
  "Is the bullet (•) noticeably misaligned with the text baseline? 
  Describe its vertical position relative to the text."
```

**Layout and Spacing:**
```bash
# Vision is GOOD at this
./vision-analyze.sh anthropic ui.png \
  "Compare the spacing between navigation sections. Is it consistent?"
```

## Output Format

All scripts output to stdout as plain text. The LLM's analysis is printed directly:

```bash
$ python examples/anthropic-vision.py screenshot.png "What's in this image?"

This image shows a web application dashboard with a navigation bar at the top,
a sidebar on the left with menu items, and a main content area displaying...
```

**For structured output**, modify your prompt:

```bash
python examples/openai-vision.py data.png \
  "Extract data as JSON with keys: title, date, amount"
```

## When to Write Custom Scripts

**Use the canned scripts for:**
- ✅ Single image + single prompt analysis
- ✅ Quick one-off tasks
- ✅ Simple Q&A about images

**Write custom scripts when you need:**
- ❌ Batch processing (analyze 100 images)
- ❌ Multi-turn conversations (follow-up questions on same image)
- ❌ Custom output formatting (generate markdown reports)
- ❌ Image preprocessing (resize, crop, filter)
- ❌ Provider fallback logic (try Gemini, then Claude)

→ See [`patterns.md`](patterns.md) for custom script examples

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Write custom script for simple analysis | Use canned scripts |
| Use low-quality compressed images | Use clear, high-res images |
| Ask vague questions | Be specific in prompts |
| Forget to set API keys | Set keys in environment variables |
| Mix up provider-specific model names | Check provider comparison table |

## Quick Reference

| Task | Command |
|------|---------|
| Analyze (single provider) | `./vision-analyze.sh anthropic img.png "prompt"` |
| Analyze (auto-fallback) | `./vision-analyze-robust.sh img.png "prompt"` |
| Extract text (OCR) | `./vision-analyze.sh gemini img.png "Extract all text"` |
| Health check | `./health-check.sh` |
| Compare images | See patterns.md for custom script |
| Batch process | See patterns.md for custom script |

## ⚠️ CRITICAL INSTRUCTIONS FOR AGENTS

**READ THIS BEFORE USING THIS SKILL:**

### 1. Always Use the Wrapper Scripts

```bash
# For AI agents (recommended) - auto-fallback on timeout
~/.amplifier/skills/image-vision/vision-analyze-robust.sh <image_path> <prompt>

# Single provider (faster if you know which to use)
~/.amplifier/skills/image-vision/vision-analyze.sh <provider> <image_path> <prompt>
```

**Examples:**
```bash
# Robust analysis (tries multiple providers if timeout)
~/.amplifier/skills/image-vision/vision-analyze-robust.sh screenshot.png "Analyze this UI"

# Specific provider
~/.amplifier/skills/image-vision/vision-analyze.sh anthropic screenshot.png "Describe this"
```

### 2. ALWAYS Check Exit Code Before Using Output

```bash
# Correct usage pattern
OUTPUT=$(~/.amplifier/skills/image-vision/vision-analyze-robust.sh image.png "Analyze this" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Vision analysis succeeded"
    # Now you can use $OUTPUT
else
    echo "ERROR: Vision analysis failed (exit code: $EXIT_CODE)"
    echo "Error details: $OUTPUT"
    # STOP HERE - do NOT proceed
    exit 1
fi
```

### 3. NEVER Fabricate Visual Observations

**If vision analysis fails, you MUST:**

✅ **DO:**
- Report failure explicitly to user
- Provide error details from stderr
- Ask user how to proceed (retry? different provider? skip visual analysis?)
- Wait for user direction before continuing

❌ **NEVER:**
- Write analysis documents without successfully seeing images
- Fabricate visual observations based on context/guesswork
- Guess pixel measurements or UI element details
- Pretend you analyzed screenshots you didn't actually see
- Continue with tasks that require visual inspection if vision failed

**Example of CORRECT failure handling:**

```
Agent: I attempted to analyze the 3 screenshots using the image-vision skill:
- screenshot-1.png: ✗ Anthropic timed out (60s)
- screenshot-1.png: ✗ Gemini timed out (60s)  
- screenshot-1.png: ✗ OpenAI failed (API error)

I have NOT successfully analyzed any of the screenshots. I cannot provide visual design 
feedback without actually seeing the images.

Options:
1. Retry with different settings
2. Investigate why all providers are failing
3. Defer visual analysis until the issue is resolved

I will NOT write design analysis documents based on guesswork or context alone.
```

### 4. Timeout Considerations

Vision API calls typically take 5-60 seconds:
- Gemini Flash: 3-10s (fastest)
- Anthropic Claude: 5-15s
- OpenAI GPT-4: 8-20s

The wrapper scripts handle timeouts with:
- 60-second default timeout (configurable)
- Auto-fallback to faster providers (robust script)
- Retry logic on transient failures

If still hitting timeouts:
- Use smaller images (resize to 2000px max)
- Simplify prompts
- Use faster models (Gemini Flash)

## Environment Setup Reminder

**For interactive use:**
1. Create venv: `cd image-vision && uv venv`
2. Install SDKs: `uv pip install anthropic openai google-generativeai`
3. Set API keys: Export `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`

**For agents:**
- Just use the wrapper scripts - they auto-setup on first use
- Verify health: `./health-check.sh`

→ See [`setup.md`](setup.md) for complete instructions

## See Also

- [`setup.md`](setup.md) — One-time environment setup, API keys, troubleshooting
- [`patterns.md`](patterns.md) — Advanced patterns: batch processing, multi-turn, custom output
