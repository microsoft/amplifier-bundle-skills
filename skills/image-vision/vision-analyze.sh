#!/bin/bash
# Auto-setup wrapper for image vision analysis
# Usage: ./vision-analyze.sh <provider> <image_path> <prompt>
# Example: ./vision-analyze.sh anthropic screenshot.png "Describe this UI"

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
PROVIDER="${1:-anthropic}"
IMAGE_PATH="$2"
PROMPT="$3"

# Validate arguments
if [ -z "$IMAGE_PATH" ] || [ -z "$PROMPT" ]; then
    echo "Usage: vision-analyze.sh <provider> <image_path> <prompt>" >&2
    echo "Providers: anthropic, openai, gemini, azure" >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  ./vision-analyze.sh anthropic screenshot.png \"Describe this UI\"" >&2
    exit 1
fi

# Check if venv exists, create if not. Pillow is required: the provider scripts
# downscale and bound the screenshot payload before sending (see
# examples/image_utils.py).
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

# Map provider to script, verify SDK installed, and check the provider's API key
# is present. A missing key fails fast and clearly (exit 3) instead of surfacing
# later as an opaque error.
case "$PROVIDER" in
    anthropic)
        SCRIPT="anthropic-vision.py"
        KEY_VAR="ANTHROPIC_API_KEY"; KEY_VAL="$ANTHROPIC_API_KEY"
        if ! "$VENV_DIR/bin/python" -c "import anthropic" 2>/dev/null; then
            echo "Installing anthropic SDK..." >&2
            cd "$SKILL_DIR" && uv pip install anthropic --quiet
        fi
        ;;
    openai)
        SCRIPT="openai-vision.py"
        KEY_VAR="OPENAI_API_KEY"; KEY_VAL="$OPENAI_API_KEY"
        if ! "$VENV_DIR/bin/python" -c "import openai" 2>/dev/null; then
            echo "Installing openai SDK..." >&2
            cd "$SKILL_DIR" && uv pip install openai --quiet
        fi
        ;;
    gemini)
        SCRIPT="gemini-vision.py"
        KEY_VAR="GOOGLE_API_KEY"; KEY_VAL="$GOOGLE_API_KEY"
        if ! "$VENV_DIR/bin/python" -c "from google import genai" 2>/dev/null; then
            echo "Installing google-genai SDK..." >&2
            cd "$SKILL_DIR" && uv pip install google-genai --quiet
        fi
        ;;
    azure)
        SCRIPT="azure-vision.py"
        KEY_VAR="AZURE_OPENAI_API_KEY"; KEY_VAL="$AZURE_OPENAI_API_KEY"
        if ! "$VENV_DIR/bin/python" -c "import openai" 2>/dev/null; then
            echo "Installing openai SDK (for Azure)..." >&2
            cd "$SKILL_DIR" && uv pip install openai --quiet
        fi
        ;;
    *)
        echo "Unknown provider: $PROVIDER" >&2
        echo "Valid providers: anthropic, openai, gemini, azure" >&2
        exit 1
        ;;
esac

if [ -z "$KEY_VAL" ]; then
    echo "ERROR: No API key for provider '$PROVIDER' ($KEY_VAR is not set)." >&2
    echo "Set $KEY_VAR, or use a provider whose key is configured." >&2
    exit 3
fi

# Run the vision script with venv Python
exec "$VENV_DIR/bin/python" "$SKILL_DIR/examples/$SCRIPT" "$IMAGE_PATH" "$PROMPT"
