#!/bin/bash
# Robust vision analysis with auto-fallback and timeout handling
# Usage: ./vision-analyze-robust.sh <image_path> <prompt> [timeout_seconds]
# Example: ./vision-analyze-robust.sh screenshot.png "Describe this UI" 60

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
IMAGE_PATH="$1"
PROMPT="$2"
TIMEOUT="${3:-60}"  # Default 60s timeout

# Validate arguments
if [ -z "$IMAGE_PATH" ] || [ -z "$PROMPT" ]; then
    echo "Usage: vision-analyze-robust.sh <image_path> <prompt> [timeout_seconds]" >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  ./vision-analyze-robust.sh screenshot.png \"Analyze this\" 60" >&2
    exit 1
fi

# Ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "First-time setup: Creating virtual environment..." >&2
    cd "$SKILL_DIR"
    uv venv
    
    echo "Installing vision SDKs (anthropic, openai, google-genai)..." >&2
    uv pip install anthropic openai google-genai --quiet
    
    echo "✓ Setup complete!" >&2
    echo "" >&2
fi

# Try providers in order: Gemini (fastest) → Anthropic → OpenAI
PROVIDERS=("gemini" "anthropic" "openai")
ERROR_LOG=$(mktemp)

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
    esac
    
    # Check/install SDK
    if ! "$VENV_DIR/bin/python" -c "$SDK_CHECK" 2>/dev/null; then
        echo "Installing $SDK_INSTALL SDK..." >&2
        cd "$SKILL_DIR" && uv pip install "$SDK_INSTALL" --quiet
    fi
    
    echo "Trying $PROVIDER (timeout: ${TIMEOUT}s)..." >&2
    
    # Run with timeout
    if timeout "$TIMEOUT" "$VENV_DIR/bin/python" "$SKILL_DIR/examples/$SCRIPT" "$IMAGE_PATH" "$PROMPT" 2>"$ERROR_LOG"; then
        echo "✓ Success with $PROVIDER" >&2
        rm -f "$ERROR_LOG"
        exit 0
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "✗ $PROVIDER timed out after ${TIMEOUT}s" >&2
        else
            ERROR_MSG=$(cat "$ERROR_LOG" | head -5)
            echo "✗ $PROVIDER failed (exit $EXIT_CODE):" >&2
            echo "$ERROR_MSG" >&2
        fi
        # Try next provider
    fi
done

# All providers failed
echo "" >&2
echo "ERROR: All vision providers failed" >&2
echo "Providers tried: ${PROVIDERS[*]}" >&2
echo "Last error:" >&2
cat "$ERROR_LOG" >&2
rm -f "$ERROR_LOG"
exit 1
