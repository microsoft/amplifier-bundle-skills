#!/bin/bash
# Robust vision analysis with auto-fallback, bounded timeouts, and honest,
# classified failures.
#
# Usage: ./vision-analyze-robust.sh <image_path> <prompt> [timeout_seconds]
# Example: ./vision-analyze-robust.sh screenshot.png "Describe this UI" 60
#
# Exit codes (so callers can distinguish failure modes instead of guessing):
#   0  success
#   1  usage error, or all configured providers failed for mixed/other reasons
#   3  no vision provider configured (no API key present) -- fail fast & clear,
#      never hang waiting on a provider that can't run
#   4  provider_timeout: provider(s) were configured but every attempt timed out
#      within the bounded ${TIMEOUT}s -- distinct from "no provider" so a slow
#      provider is not mislabeled as a missing one

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
IMAGE_PATH="$1"
PROMPT="$2"
TIMEOUT="${3:-60}"  # Default 60s timeout (bounded -- never an unbounded wait)

# Validate arguments
if [ -z "$IMAGE_PATH" ] || [ -z "$PROMPT" ]; then
    echo "Usage: vision-analyze-robust.sh <image_path> <prompt> [timeout_seconds]" >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  ./vision-analyze-robust.sh screenshot.png \"Analyze this\" 60" >&2
    exit 1
fi

# Portable timeout: GNU coreutils 'timeout' (Linux) or 'gtimeout' (macOS via
# `brew install coreutils`). If neither exists we still run, but cannot enforce
# the bound -- say so loudly rather than pretend.
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_BIN="gtimeout"
else
    echo "WARNING: no 'timeout' command found; provider calls will NOT be" >&2
    echo "time-bounded. Install GNU coreutils (e.g. 'brew install coreutils')" >&2
    echo "to enable the ${TIMEOUT}s timeout and provider_timeout classification." >&2
fi

# Ensure venv exists. Pillow is required: the provider scripts downscale and
# bound the screenshot payload before sending (see examples/image_utils.py).
if [ ! -d "$VENV_DIR" ]; then
    echo "First-time setup: Creating virtual environment..." >&2
    cd "$SKILL_DIR"
    uv venv

    echo "Installing vision SDKs (anthropic, openai, google-genai) + pillow..." >&2
    uv pip install anthropic openai google-genai pillow --quiet

    echo "✓ Setup complete!" >&2
    echo "" >&2
fi

# Make sure Pillow is present even if the venv predates this change.
if ! "$VENV_DIR/bin/python" -c "import PIL" 2>/dev/null; then
    echo "Installing pillow (required for screenshot downscaling)..." >&2
    cd "$SKILL_DIR" && uv pip install pillow --quiet
fi

# Determine which providers are actually CONFIGURED (have an API key). We only
# attempt configured providers -- trying one with no key just wastes a slot and
# muddies the failure signal. Order: Gemini (fastest) -> Anthropic -> OpenAI ->
# Azure (enterprise; needs both key and endpoint).
PROVIDERS=()
[ -n "$GOOGLE_API_KEY" ] && PROVIDERS+=("gemini")
[ -n "$ANTHROPIC_API_KEY" ] && PROVIDERS+=("anthropic")
[ -n "$OPENAI_API_KEY" ] && PROVIDERS+=("openai")
[ -n "$AZURE_OPENAI_API_KEY" ] && [ -n "$AZURE_OPENAI_ENDPOINT" ] && PROVIDERS+=("azure")

# Fail-fast, clear, actionable signal when NO provider is configured. This is
# the failure that previously surfaced minutes later as an opaque hang.
if [ ${#PROVIDERS[@]} -eq 0 ]; then
    echo "ERROR: No vision provider configured." >&2
    echo "Set one of: GOOGLE_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY," >&2
    echo "or AZURE_OPENAI_API_KEY (+ AZURE_OPENAI_ENDPOINT)." >&2
    echo "Vision screenshot analysis cannot run without a provider key." >&2
    exit 3
fi

ERROR_LOG=$(mktemp)
ATTEMPTED=0
TIMEOUTS=0

for PROVIDER in "${PROVIDERS[@]}"; do
    case "$PROVIDER" in
        gemini)
            SCRIPT="gemini-vision.py"
            SDK_CHECK="from google import genai"
            SDK_INSTALL="google-genai"
            ;;
        anthropic)
            SCRIPT="anthropic-vision.py"
            SDK_CHECK="import anthropic"
            SDK_INSTALL="anthropic"
            ;;
        openai)
            SCRIPT="openai-vision.py"
            SDK_CHECK="import openai"
            SDK_INSTALL="openai"
            ;;
        azure)
            SCRIPT="azure-vision.py"
            SDK_CHECK="import openai"
            SDK_INSTALL="openai"
            ;;
    esac

    # Check/install SDK
    if ! "$VENV_DIR/bin/python" -c "$SDK_CHECK" 2>/dev/null; then
        echo "Installing $SDK_INSTALL SDK..." >&2
        cd "$SKILL_DIR" && uv pip install "$SDK_INSTALL" --quiet
    fi

    echo "Trying $PROVIDER (timeout: ${TIMEOUT}s)..." >&2
    ATTEMPTED=$((ATTEMPTED + 1))

    # Run with a bounded timeout when available.
    set +e
    if [ -n "$TIMEOUT_BIN" ]; then
        "$TIMEOUT_BIN" "$TIMEOUT" "$VENV_DIR/bin/python" "$SKILL_DIR/examples/$SCRIPT" "$IMAGE_PATH" "$PROMPT" 2>"$ERROR_LOG"
    else
        "$VENV_DIR/bin/python" "$SKILL_DIR/examples/$SCRIPT" "$IMAGE_PATH" "$PROMPT" 2>"$ERROR_LOG"
    fi
    EXIT_CODE=$?
    set -e

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ Success with $PROVIDER" >&2
        rm -f "$ERROR_LOG"
        exit 0
    elif [ $EXIT_CODE -eq 124 ]; then
        echo "✗ $PROVIDER timed out after ${TIMEOUT}s" >&2
        TIMEOUTS=$((TIMEOUTS + 1))
    else
        ERROR_MSG=$(cat "$ERROR_LOG" | head -5)
        echo "✗ $PROVIDER failed (exit $EXIT_CODE):" >&2
        echo "$ERROR_MSG" >&2
    fi
    # Try next provider
done

# All configured providers failed. Classify the failure so the caller gets an
# honest signal rather than a catch-all.
echo "" >&2
if [ "$TIMEOUTS" -eq "$ATTEMPTED" ]; then
    # Every attempt timed out: provider(s) present but too slow.
    echo "ERROR: provider_timeout -- all ${ATTEMPTED} configured vision provider(s) timed out after ${TIMEOUT}s each." >&2
    echo "Providers tried: ${PROVIDERS[*]}" >&2
    echo "Try a larger timeout (3rd arg), a smaller image, or a faster provider." >&2
    rm -f "$ERROR_LOG"
    exit 4
fi

echo "ERROR: All configured vision providers failed" >&2
echo "Providers tried: ${PROVIDERS[*]}" >&2
echo "Last error:" >&2
cat "$ERROR_LOG" >&2
rm -f "$ERROR_LOG"
exit 1
