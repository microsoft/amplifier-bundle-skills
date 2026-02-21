#!/usr/bin/env python3
"""Analyze images using Anthropic Claude vision models.

Usage:
    python anthropic-vision.py <image_path> <prompt>

Example:
    python anthropic-vision.py screenshot.png "Describe this UI"
    python anthropic-vision.py photo.jpg "What's in this image?"

Requires:
    - anthropic SDK: pip install anthropic
    - ANTHROPIC_API_KEY environment variable
"""

import anthropic
import base64
import sys
import os
import time


def analyze_image(image_path: str, prompt: str, max_retries: int = 2) -> str:
    """Analyze an image using Claude's vision capabilities.
    
    Args:
        image_path: Path to image file (JPEG, PNG, GIF, WEBP)
        prompt: Question or instruction about the image
        
    Returns:
        Claude's text analysis of the image
    """
    # Initialize client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Read and encode image
    try:
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Image not found: {image_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to read image: {e}")
    
    # Detect media type from extension
    ext = image_path.lower().split('.')[-1]
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    media_type = media_types.get(ext, "image/jpeg")
    
    # Call Claude with vision (with retry logic)
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-5",  # Latest model (September 2025)
                max_tokens=1024,
                timeout=60.0,  # 60-second timeout
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            
            return message.content[0].text
        
        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                print(f"Rate limited, waiting {wait_time}s before retry...", file=sys.stderr)
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Rate limit exceeded after {max_retries} attempts: {e}")
        
        except anthropic.APITimeoutError as e:
            if attempt < max_retries - 1:
                print(f"Request timed out, retrying (attempt {attempt + 2}/{max_retries})...", file=sys.stderr)
                time.sleep(2)
            else:
                raise RuntimeError(f"Request timed out after {max_retries} attempts (60s each): {e}")
        
        except anthropic.APIError as e:
            # Other API errors - don't retry
            raise RuntimeError(f"API error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python anthropic-vision.py <image_path> <prompt>")
        print()
        print("Example:")
        print('  python anthropic-vision.py screenshot.png "Describe this UI"')
        sys.exit(1)
    
    image_path = sys.argv[1]
    prompt = " ".join(sys.argv[2:])  # Join remaining args as prompt
    
    try:
        result = analyze_image(image_path, prompt)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
