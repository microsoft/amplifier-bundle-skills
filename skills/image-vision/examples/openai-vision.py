#!/usr/bin/env python3
"""Analyze images using OpenAI GPT-4 vision models.

Usage:
    python openai-vision.py <image_path> <prompt>

Example:
    python openai-vision.py screenshot.png "Describe this UI"
    python openai-vision.py photo.jpg "What's in this image?"

Requires:
    - openai SDK: pip install openai
    - OPENAI_API_KEY environment variable
"""

import openai
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from image_utils import prepare_image_base64  # noqa: E402


def analyze_image(image_path: str, prompt: str, max_retries: int = 2) -> str:
    """Analyze an image using GPT-4's vision capabilities.
    
    Args:
        image_path: Path to image file (JPEG, PNG, GIF, WEBP)
        prompt: Question or instruction about the image
        
    Returns:
        GPT-4's text analysis of the image
    """
    # Initialize client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = openai.OpenAI(api_key=api_key)
    
    # Read, downscale, and bound the payload before sending (see image_utils).
    # This caps screenshot size so a large image can't produce an oversized,
    # interruptible request that hangs.
    image_data, media_type = prepare_image_base64(image_path)
    
    # Call GPT-5 with vision (with retry logic)
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-5",  # Latest flagship model (2025)
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}"
                            }
                        }
                    ]
                }],
                max_completion_tokens=1024,  # GPT-5 uses max_completion_tokens
                timeout=60.0  # 60-second timeout
            )
            
            return response.choices[0].message.content
        
        except openai.RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                print(f"Rate limited, waiting {wait_time}s before retry...", file=sys.stderr)
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Rate limit exceeded after {max_retries} attempts: {e}")
        
        except openai.APITimeoutError as e:
            if attempt < max_retries - 1:
                print(f"Request timed out, retrying (attempt {attempt + 2}/{max_retries})...", file=sys.stderr)
                time.sleep(2)
            else:
                raise RuntimeError(f"Request timed out after {max_retries} attempts (60s each): {e}")
        
        except openai.APIError as e:
            # Other API errors - don't retry
            raise RuntimeError(f"API error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python openai-vision.py <image_path> <prompt>")
        print()
        print("Example:")
        print('  python openai-vision.py screenshot.png "Describe this UI"')
        sys.exit(1)
    
    image_path = sys.argv[1]
    prompt = " ".join(sys.argv[2:])  # Join remaining args as prompt
    
    try:
        result = analyze_image(image_path, prompt)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
