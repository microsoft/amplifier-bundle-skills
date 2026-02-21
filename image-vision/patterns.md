# Image Vision Advanced Patterns

## Batch Processing Multiple Images

### Analyze multiple images in sequence

```python
#!/usr/bin/env python3
"""Batch analyze multiple images with the same prompt."""

import anthropic
import base64
import sys
import os
from pathlib import Path

def analyze_image(client, image_path: str, prompt: str) -> str:
    """Analyze a single image."""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.lower().split('.')[-1]
    media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                   "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    media_type = media_types.get(ext, "image/jpeg")
    
    message = client.messages.create(
        model="claude-sonnet-4-5",  # Latest model
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", 
                 "media_type": media_type, "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    return message.content[0].text

def main():
    if len(sys.argv) < 3:
        print("Usage: python batch-analyze.py <prompt> <image1> <image2> ...")
        sys.exit(1)
    
    prompt = sys.argv[1]
    image_paths = sys.argv[2:]
    
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    for image_path in image_paths:
        print(f"\n{'='*60}")
        print(f"Analyzing: {image_path}")
        print('='*60)
        
        try:
            result = analyze_image(client, image_path, prompt)
            print(result)
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
python batch-analyze.py "Describe this UI" screen1.png screen2.png screen3.png
```

### Parallel batch processing (faster)

```python
import asyncio
from anthropic import AsyncAnthropic

async def analyze_image_async(client, image_path: str, prompt: str) -> tuple[str, str]:
    """Analyze image asynchronously, return (path, result)."""
    # ... (same encoding logic) ...
    
    message = await client.messages.create(
        model="claude-sonnet-4-5",  # Latest model
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", 
                 "media_type": media_type, "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    return image_path, message.content[0].text

async def main():
    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    image_paths = sys.argv[2:]
    prompt = sys.argv[1]
    
    # Process all images in parallel
    tasks = [analyze_image_async(client, path, prompt) for path in image_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for path, result in results:
        print(f"\n{path}:\n{result}\n")

asyncio.run(main())
```

## Multi-Turn Conversations

### Follow-up questions on same image

```python
#!/usr/bin/env python3
"""Interactive multi-turn conversation about an image."""

import anthropic
import base64
import os

def load_image(image_path: str) -> dict:
    """Load and encode image once."""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.lower().split('.')[-1]
    media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                   "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    media_type = media_types.get(ext, "image/jpeg")
    
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": image_data
        }
    }

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python multi-turn.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # Load image once
    image_block = load_image(image_path)
    
    # Conversation history (include image in first message only)
    messages = []
    
    print("Multi-turn image conversation. Type 'quit' to exit.\n")
    
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in ['quit', 'exit', 'q']:
            break
        
        # First turn: include image
        if not messages:
            content = [image_block, {"type": "text", "text": prompt}]
        else:
            # Subsequent turns: text only (image persists in context)
            content = [{"type": "text", "text": prompt}]
        
        messages.append({"role": "user", "content": content})
        
        response = client.messages.create(
            model="claude-sonnet-4-5",  # Latest model
            max_tokens=1024,
            messages=messages
        )
        
        assistant_message = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_message})
        
        print(f"\nAssistant: {assistant_message}\n")

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
python multi-turn.py screenshot.png

You: What's in this image?
Assistant: This is a web dashboard showing...

You: What color is the header?
Assistant: The header is a dark blue...

You: quit
```

## Comparing Multiple Images

```python
#!/usr/bin/env python3
"""Compare two images side by side."""

import anthropic
import base64
import sys
import os

def compare_images(image1_path: str, image2_path: str, prompt: str) -> str:
    """Compare two images with a prompt."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # Load both images
    images = []
    for path in [image1_path, image2_path]:
        with open(path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        ext = path.lower().split('.')[-1]
        media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                       "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        media_type = media_types.get(ext, "image/jpeg")
        
        images.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data
            }
        })
    
    # Send both images in one message
    message = client.messages.create(
        model="claude-sonnet-4-5",  # Latest model
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Image 1:"},
                images[0],
                {"type": "text", "text": "Image 2:"},
                images[1],
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    return message.content[0].text

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python compare-images.py <image1> <image2> <prompt>")
        print('Example: python compare-images.py old.png new.png "What changed?"')
        sys.exit(1)
    
    result = compare_images(sys.argv[1], sys.argv[2], sys.argv[3])
    print(result)
```

**Usage:**
```bash
python compare-images.py before.png after.png "What visual changes were made between these two screenshots?"
```

## Structured JSON Output

```python
#!/usr/bin/env python3
"""Extract structured data from images as JSON."""

import anthropic
import base64
import sys
import os
import json

def extract_structured_data(image_path: str, schema: dict) -> dict:
    """Extract data matching a JSON schema."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.lower().split('.')[-1]
    media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                   "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    media_type = media_types.get(ext, "image/jpeg")
    
    # Construct prompt with schema
    schema_str = json.dumps(schema, indent=2)
    prompt = f"""Extract data from this image and return ONLY valid JSON matching this schema:

{schema_str}

Return nothing but the JSON object. No explanation, no markdown, just the JSON."""
    
    message = client.messages.create(
        model="claude-sonnet-4-5",  # Latest model
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", 
                 "media_type": media_type, "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    # Parse JSON from response
    response_text = message.content[0].text.strip()
    # Remove markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split('\n')
        response_text = '\n'.join(lines[1:-1])
    
    return json.loads(response_text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract-json.py <image_path>")
        sys.exit(1)
    
    # Example schema for invoice
    schema = {
        "vendor": "string",
        "date": "YYYY-MM-DD",
        "total": "number",
        "items": [
            {"description": "string", "amount": "number"}
        ]
    }
    
    result = extract_structured_data(sys.argv[1], schema)
    print(json.dumps(result, indent=2))
```

**Usage:**
```bash
python extract-json.py invoice.png > invoice.json
```

## Multi-Provider Fallback

```python
#!/usr/bin/env python3
"""Try multiple providers with automatic fallback."""

import sys
import os
from typing import Optional

def try_anthropic(image_path: str, prompt: str) -> Optional[str]:
    """Try Anthropic Claude."""
    try:
        import anthropic
        import base64
        
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", 
                     "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        return message.content[0].text
    except Exception as e:
        print(f"Anthropic failed: {e}", file=sys.stderr)
        return None

def try_gemini(image_path: str, prompt: str) -> Optional[str]:
    """Try Google Gemini."""
    try:
        from google import genai
        
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # Latest model
            contents=[prompt, types.Part.from_bytes(data=image_data, mime_type="image/jpeg")]
        )
        
        return response.text
    except Exception as e:
        print(f"Gemini failed: {e}", file=sys.stderr)
        return None

def try_openai(image_path: str, prompt: str) -> Optional[str]:
    """Try OpenAI GPT-4."""
    try:
        import openai
        import base64
        
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        response = client.chat.completions.create(
            model="gpt-5",  # Latest model
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }}
                ]
            }],
            max_completion_tokens=1024  # GPT-5 uses max_completion_tokens
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI failed: {e}", file=sys.stderr)
        return None

def analyze_with_fallback(image_path: str, prompt: str) -> str:
    """Try providers in order until one succeeds."""
    providers = [
        ("Gemini", try_gemini),      # Try cheapest first
        ("Anthropic", try_anthropic),
        ("OpenAI", try_openai),
    ]
    
    for name, func in providers:
        print(f"Trying {name}...", file=sys.stderr)
        result = func(image_path, prompt)
        if result:
            print(f"Success with {name}", file=sys.stderr)
            return result
    
    raise RuntimeError("All providers failed")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fallback.py <image_path> <prompt>")
        sys.exit(1)
    
    result = analyze_with_fallback(sys.argv[1], sys.argv[2])
    print(result)
```

## Image Preprocessing

```python
#!/usr/bin/env python3
"""Preprocess images before sending to vision API."""

from PIL import Image
import sys
import os

def preprocess_image(input_path: str, output_path: str, max_size: tuple = (2000, 2000)):
    """Resize and optimize image for API."""
    img = Image.open(input_path)
    
    # Convert to RGB if needed (handle PNG transparency)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
        img = background
    
    # Resize if too large
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Save optimized
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    print(f"Optimized: {os.path.getsize(input_path)} → {os.path.getsize(output_path)} bytes")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python preprocess.py <input> <output>")
        sys.exit(1)
    
    preprocess_image(sys.argv[1], sys.argv[2])
```

**Usage:**
```bash
# Optimize before sending
python preprocess.py huge-image.png optimized.jpg
python examples/anthropic-vision.py optimized.jpg "Analyze this"
```

## Error Handling and Retries

```python
#!/usr/bin/env python3
"""Robust vision analysis with retries and error handling."""

import anthropic
import base64
import sys
import os
import time
from typing import Optional

def analyze_with_retry(image_path: str, prompt: str, max_retries: int = 3) -> str:
    """Analyze image with automatic retries on rate limits."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.lower().split('.')[-1]
    media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                   "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    media_type = media_types.get(ext, "image/jpeg")
    
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", 
                         "media_type": media_type, "data": image_data}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            
            return message.content[0].text
            
        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited, waiting {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
            else:
                raise
        
        except anthropic.APIError as e:
            print(f"API error: {e}", file=sys.stderr)
            raise

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python robust-analyze.py <image_path> <prompt>")
        sys.exit(1)
    
    try:
        result = analyze_with_retry(sys.argv[1], sys.argv[2])
        print(result)
    except Exception as e:
        print(f"Failed after retries: {e}", file=sys.stderr)
        sys.exit(1)
```

## Cost Optimization

```python
#!/usr/bin/env python3
"""Route to cheapest model that can handle the task."""

def choose_model(task_complexity: str) -> tuple[str, str]:
    """Choose provider and model based on complexity."""
    
    if task_complexity == "simple":
        # Simple tasks: use fastest/cheapest
        return "gemini", "gemini-2.5-flash"
    
    elif task_complexity == "medium":
        # Balanced: use Sonnet 4.5 or GPT-4.1
        return "anthropic", "claude-sonnet-4-5"
    
    elif task_complexity == "complex":
        # Complex: use best quality
        return "openai", "gpt-5"
    
    else:
        # Default
        return "anthropic", "claude-sonnet-4-5"

# Example usage in your script:
complexity = "simple"  # or get from command line
provider, model = choose_model(complexity)

# Then use appropriate provider with that model
```

## See Also

- [SKILL.md](SKILL.md) — Quick start and basic usage
- [setup.md](setup.md) — Environment setup and API keys
