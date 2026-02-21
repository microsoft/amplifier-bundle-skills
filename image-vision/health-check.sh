#!/bin/bash
# Verify image-vision skill is properly configured
# Usage: ./health-check.sh

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"

echo "Image-Vision Skill Health Check"
echo "================================"
echo ""

# Check 1: Venv exists
if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment exists"
else
    echo "✗ Virtual environment missing"
    echo "  Run: cd $SKILL_DIR && uv venv"
    exit 1
fi

# Check 2: Python executable
if [ -x "$VENV_DIR/bin/python" ]; then
    echo "✓ Python executable found"
    PYTHON_VERSION=$("$VENV_DIR/bin/python" --version 2>&1)
    echo "  $PYTHON_VERSION"
else
    echo "✗ Python executable not found in venv"
    exit 1
fi

# Check 3: SDKs installed
echo ""
echo "Checking SDKs..."

if "$VENV_DIR/bin/python" -c "import anthropic" 2>/dev/null; then
    echo "✓ Anthropic SDK installed"
else
    echo "✗ Anthropic SDK missing"
    echo "  Run: $VENV_DIR/bin/pip install anthropic"
fi

if "$VENV_DIR/bin/python" -c "import openai" 2>/dev/null; then
    echo "✓ OpenAI SDK installed"
else
    echo "✗ OpenAI SDK missing"
    echo "  Run: $VENV_DIR/bin/pip install openai"
fi

if "$VENV_DIR/bin/python" -c "from google import genai" 2>/dev/null; then
    echo "✓ Google Gemini SDK installed"
else
    echo "✗ Google Gemini SDK missing"
    echo "  Run: $VENV_DIR/bin/pip install google-genai"
fi

# Check 4: API Keys
echo ""
echo "Checking API keys..."

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✓ ANTHROPIC_API_KEY set"
else
    echo "⚠ ANTHROPIC_API_KEY not set (required for Anthropic)"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ OPENAI_API_KEY set"
else
    echo "⚠ OPENAI_API_KEY not set (required for OpenAI)"
fi

if [ -n "$GOOGLE_API_KEY" ]; then
    echo "✓ GOOGLE_API_KEY set"
else
    echo "⚠ GOOGLE_API_KEY not set (required for Gemini)"
fi

# Check 5: Example scripts exist
echo ""
echo "Checking example scripts..."

SCRIPTS=("anthropic-vision.py" "openai-vision.py" "gemini-vision.py" "azure-vision.py")
for script in "${SCRIPTS[@]}"; do
    if [ -f "$SKILL_DIR/examples/$script" ]; then
        echo "✓ $script exists"
    else
        echo "✗ $script missing"
    fi
done

echo ""
echo "================================"
echo "Health check complete!"
echo ""

# Overall status
if [ ! -d "$VENV_DIR" ]; then
    echo "Status: ✗ FAIL - Run setup first"
    exit 1
elif ! "$VENV_DIR/bin/python" -c "import anthropic" 2>/dev/null; then
    echo "Status: ⚠ PARTIAL - Install SDKs"
    exit 1
else
    echo "Status: ✓ READY"
    exit 0
fi
