# Image Vision Setup Guide

## One-Time Environment Setup

**Use `uv` for isolated environment to avoid polluting global Python:**

```bash
# Navigate to skill directory (wherever you loaded it)
cd ~/.amplifier/skills/image-vision  # or your skills directory

# Create virtual environment with uv
uv venv

# Activate environment
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows

# Install all provider SDKs (recommended)
uv pip install anthropic openai google-genai

# Or install only what you need
uv pip install anthropic              # Claude only
uv pip install openai                 # OpenAI + Azure OpenAI
uv pip install google-genai           # Gemini only
```

**Verify installation:**

```bash
# Check Python can import the packages
python -c "import anthropic; print('✓ Anthropic SDK installed')"
python -c "import openai; print('✓ OpenAI SDK installed')"
python -c "from google import genai; print('✓ Gemini SDK installed')"
```

## API Key Configuration

### Option 1: Environment Variables (Recommended)

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, or `~/.bash_profile`):

```bash
# Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# OpenAI
export OPENAI_API_KEY="sk-..."

# Google Gemini
export GOOGLE_API_KEY="..."

# Azure OpenAI (if using Azure)
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
```

**Apply changes:**
```bash
source ~/.zshrc  # or ~/.bashrc
```

### Option 2: .env File (Alternative)

Create `.env` file in skill directory:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
```

Then load before running scripts:
```bash
export $(cat .env | xargs)
python examples/anthropic-vision.py image.png "prompt"
```

### Getting API Keys

**Anthropic:**
1. Visit https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys section
4. Create new key

**OpenAI:**
1. Visit https://platform.openai.com/
2. Sign up or log in
3. Go to API Keys section
4. Create new key

**Google Gemini:**
1. Visit https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Create API key

**Azure OpenAI:**
1. Set up Azure OpenAI resource in Azure Portal
2. Get keys from resource management page
3. Note the endpoint URL

## Using Scripts After Setup

### Option 1: Activate venv first (interactive use)

```bash
source ~/.amplifier/skills/image-vision/.venv/bin/activate
python examples/anthropic-vision.py image.png "Describe this image"
deactivate  # when done
```

### Option 2: Call venv Python directly (recommended for agents)

```bash
# Full path to venv Python
~/.amplifier/skills/image-vision/.venv/bin/python \
  examples/anthropic-vision.py image.png "Describe this image"
```

### Option 3: Add alias (convenience)

Add to shell profile:

```bash
alias vision-claude='~/.amplifier/skills/image-vision/.venv/bin/python ~/.amplifier/skills/image-vision/examples/anthropic-vision.py'
alias vision-gpt='~/.amplifier/skills/image-vision/.venv/bin/python ~/.amplifier/skills/image-vision/examples/openai-vision.py'
alias vision-gemini='~/.amplifier/skills/image-vision/.venv/bin/python ~/.amplifier/skills/image-vision/examples/gemini-vision.py'
```

Then use:
```bash
vision-claude image.png "What's in this image?"
```

## Supported Models by Provider

### Anthropic Claude

```python
# In examples/anthropic-vision.py, change model:
model="claude-sonnet-4-5"         # Default: latest (September 2025)
model="claude-3-opus-20240229"    # Best quality, slower (older)
model="claude-3-haiku-20240307"   # Fastest, cheaper
```

**Recommended:** claude-sonnet-4-5 (latest, best balance)

### OpenAI

```python
# In examples/openai-vision.py, change model:
model="gpt-5"                     # Default: latest flagship (2025)
model="gpt-4.1"                   # High-volume production
```

**Note:** GPT-5 requires `max_completion_tokens` parameter instead of `max_tokens`

**Recommended:** gpt-5 (latest)

### Google Gemini

```python
# In examples/gemini-vision.py, change model:
model="gemini-2.5-flash"          # Default: latest (2025)
model="gemini-2.5-pro"            # Best quality, handles huge images
model="gemini-2.0-flash"          # Older version
```

**Recommended:** gemini-2.5-flash (latest)

### Azure OpenAI

Azure uses **deployment names** instead of model names. Configure in your Azure Portal:

```python
# In examples/azure-vision.py:
deployment_name="gpt-4o"  # Your deployment name
api_version="2024-02-15-preview"
```

## Image Format Support

**Supported formats:**
- JPEG/JPG
- PNG (with transparency)
- GIF
- WEBP

**Maximum sizes:**
| Provider | Max Size | Notes |
|----------|----------|-------|
| Anthropic | 5MB | Multiple images supported |
| OpenAI | 20MB | Auto-resizes if needed |
| Gemini | Varies | 1.5-pro handles very large images |
| Azure | 20MB | Same as OpenAI |

**Best practices:**
- Use JPEG for photos (smaller file size)
- Use PNG for screenshots, diagrams (preserves clarity)
- Compress images if over size limits
- Higher quality → better analysis results

## Troubleshooting

### "ModuleNotFoundError: No module named 'anthropic'"

**Solution:** Install the SDK in the venv:
```bash
cd ~/.amplifier/skills/image-vision
source .venv/bin/activate
uv pip install anthropic
```

### "AuthenticationError: Invalid API key"

**Solution:** Check your API key:
```bash
# Verify key is set
echo $ANTHROPIC_API_KEY

# Re-export if needed
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### "FileNotFoundError: [Errno 2] No such file or directory: 'image.png'"

**Solution:** Use absolute path or correct relative path:
```bash
# Absolute path
python examples/anthropic-vision.py /full/path/to/image.png "prompt"

# Or navigate to image directory first
cd ~/Desktop
python ~/.amplifier/skills/image-vision/examples/anthropic-vision.py image.png "prompt"
```

### "Rate limit exceeded"

**Solution:** You're making too many requests:
- Wait a few seconds and retry
- Check your API usage dashboard
- Upgrade to higher rate limit tier

### "Image too large"

**Solution:** Compress or resize the image:
```bash
# Using ImageMagick
convert large.png -resize 50% smaller.png

# Using Python PIL (install: uv pip install pillow)
python -c "from PIL import Image; img = Image.open('large.png'); img.thumbnail((2000,2000)); img.save('smaller.png')"
```

### Scripts work in terminal but not via Amplifier agent

**Solution:** Use the wrapper scripts instead:
```bash
# Best approach - auto-setup, handles venv automatically
~/.amplifier/skills/image-vision/vision-analyze-robust.sh image.png "prompt"

# Or specific provider
~/.amplifier/skills/image-vision/vision-analyze.sh anthropic image.png "prompt"

# Old approach (manual venv path) - NOT RECOMMENDED
~/.amplifier/skills/image-vision/.venv/bin/python \
  ~/.amplifier/skills/image-vision/examples/anthropic-vision.py \
  image.png "prompt"
```

### Scripts time out after 30 seconds when called by agents

**Problem:** Amplifier's bash tool has a default 30-second timeout. Vision API calls can take 5-60 seconds depending on image size and complexity.

**Solution 1: Use the robust wrapper (RECOMMENDED)**
```bash
# This script has 60-second timeout and auto-fallback to other providers
~/.amplifier/skills/image-vision/vision-analyze-robust.sh image.png "Describe this"
```

**Solution 2: Use custom timeout with robust wrapper**
```bash
# Increase timeout to 120 seconds for very large images
~/.amplifier/skills/image-vision/vision-analyze-robust.sh image.png "Analyze" 120
```

**Solution 3: Try faster provider first**
```bash
# Gemini Flash is fastest (typically 3-10 seconds)
~/.amplifier/skills/image-vision/vision-analyze.sh gemini image.png "Describe this"
```

**Typical API response times:**
- Gemini Flash: 3-10 seconds (fastest)
- Anthropic Claude: 5-15 seconds
- OpenAI GPT-4: 8-20 seconds
- Large images (>2MB): Add 5-20 seconds

### Agent receives no output after vision call

**Problem:** Vision analysis failed but agent proceeded to write analysis documents anyway, fabricating observations.

**This is a CRITICAL failure mode** - agents must NEVER fabricate visual observations.

**For AI agents using this skill:**

✅ **REQUIRED PATTERN - Check exit code:**
```bash
OUTPUT=$(~/.amplifier/skills/image-vision/vision-analyze-robust.sh image.png "Analyze" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Vision analysis succeeded:"
    echo "$OUTPUT"
    # Proceed with analysis
else
    echo "ERROR: Vision analysis failed (exit code: $EXIT_CODE)"
    echo "Error details: $OUTPUT"
    echo ""
    echo "I have NOT successfully analyzed the image."
    echo "I cannot provide visual feedback without actually seeing the image."
    echo ""
    echo "Options:"
    echo "1. Retry with different provider"
    echo "2. Investigate the error"
    echo "3. Defer visual analysis until issue is resolved"
    # STOP HERE - do NOT proceed with fabricated observations
    exit 1
fi
```

❌ **NEVER DO THIS:**
- Proceed to write design/UI analysis if vision failed
- Fabricate pixel measurements or element sizes
- Guess visual layout details from context
- Pretend you saw images you didn't analyze
- Write "based on the screenshot" when you have no output

**If vision analysis fails, STOP and report it. Do not guess.**

## Verifying Setup

**Quick test script:**

```bash
# Test each provider (requires API keys set)

# Anthropic
echo "Testing Claude..."
~/.amplifier/skills/image-vision/.venv/bin/python \
  examples/anthropic-vision.py test-image.png "What color is dominant?"

# OpenAI
echo "Testing GPT-4..."
~/.amplifier/skills/image-vision/.venv/bin/python \
  examples/openai-vision.py test-image.png "What color is dominant?"

# Gemini
echo "Testing Gemini..."
~/.amplifier/skills/image-vision/.venv/bin/python \
  examples/gemini-vision.py test-image.png "What color is dominant?"
```

If all three return reasonable answers, setup is complete!

## Cost Considerations

**Approximate costs per image (as of 2024):**

| Provider | Model | Cost per Image* |
|----------|-------|-----------------|
| Anthropic | Claude 3.5 Sonnet | ~$0.003 |
| Anthropic | Claude 3 Opus | ~$0.015 |
| Anthropic | Claude 3 Haiku | ~$0.0004 |
| OpenAI | GPT-4o | ~$0.01 |
| OpenAI | GPT-4 Turbo | ~$0.01 |
| Gemini | 2.0 Flash | ~$0.001 |
| Gemini | 1.5 Pro | ~$0.0035 |
| Azure | (varies) | Similar to OpenAI |

*Approximate, varies by image size and prompt length

**Recommendations:**
- **Development/testing:** Use Haiku or Gemini Flash (cheapest)
- **Production:** Use Sonnet or GPT-4o (balanced)
- **High-quality needs:** Use Opus or GPT-4 Turbo

## Security Best Practices

1. **Never commit API keys to git:**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo "*.key" >> .gitignore
   ```

2. **Use environment variables, not hardcoded keys**

3. **Rotate keys regularly** (every 3-6 months)

4. **Set spending limits** in provider dashboards

5. **Monitor usage** to detect unauthorized access

## Next Steps

- ✓ Environment set up
- ✓ API keys configured
- ✓ SDKs installed

**Now try:**
1. Test with a sample image (see "Verifying Setup" above)
2. Read SKILL.md for usage examples
3. Read patterns.md for advanced use cases
