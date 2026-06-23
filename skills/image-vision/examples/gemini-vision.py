#!/usr/bin/env python3
"""Analyze images using Google Gemini vision models.

Usage:
    python gemini-vision.py <image_path> <prompt>

Example:
    python gemini-vision.py screenshot.png "Describe this UI"
    python gemini-vision.py photo.jpg "What's in this image?"

Requires:
    - google-genai SDK: pip install google-genai
    - GOOGLE_API_KEY environment variable
"""

from google import genai
from google.genai import types
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from image_utils import prepare_image_bytes  # noqa: E402


def analyze_image(image_path: str, prompt: str, max_retries: int = 2) -> str:
    """Analyze an image using Gemini's vision capabilities.
    
    Args:
        image_path: Path to image file (JPEG, PNG, GIF, WEBP)
        prompt: Question or instruction about the image
        
    Returns:
        Gemini's text analysis of the image
    """
    # Initialize client
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    client = genai.Client(api_key=api_key)
    
    # Read, downscale, and bound the payload before sending (see image_utils).
    # This caps screenshot size so a large image can't produce an oversized,
    # interruptible request that hangs.
    image_data, mime_type = prepare_image_bytes(image_path)
    
    # Call Gemini with vision using proper types (with retry logic)
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",  # Latest model (2025)
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_data, mime_type=mime_type)
                ]
            )
            return response.text
        
        except Exception as e:
            error_msg = str(e).lower()
            
            # Rate limiting or quota errors - retry with backoff
            if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                    print(f"Rate limited, waiting {wait_time}s before retry...", file=sys.stderr)
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"Rate limit exceeded after {max_retries} attempts: {e}")
            
            # Timeout errors - retry
            elif "timeout" in error_msg or "deadline" in error_msg:
                if attempt < max_retries - 1:
                    print(f"Request timed out, retrying (attempt {attempt + 2}/{max_retries})...", file=sys.stderr)
                    time.sleep(2)
                else:
                    raise RuntimeError(f"Request timed out after {max_retries} attempts: {e}")
            
            # Other errors - don't retry
            else:
                raise RuntimeError(f"API error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gemini-vision.py <image_path> <prompt>")
        print()
        print("Example:")
        print('  python gemini-vision.py screenshot.png "Describe this UI"')
        sys.exit(1)
    
    image_path = sys.argv[1]
    prompt = " ".join(sys.argv[2:])  # Join remaining args as prompt
    
    try:
        result = analyze_image(image_path, prompt)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
