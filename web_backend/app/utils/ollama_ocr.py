import os
import base64
import requests
from django.conf import settings


def llava_extract_text(storage_key, model_name="llava:latest"):
    """
    Perform OCR using Ollama's LLaVA Vision model.

    - Takes an image saved locally (storage_key under MEDIA_ROOT)
    - Sends it to LLaVA through /api/chat
    - Returns ONLY extracted text (cleaned)

    Output:
      {
        "extracted_text": "...",
        "tokens_count": int,
        "model_version": "llava:latest",
        "raw_response": {...}
      }
    """
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    image_path = settings.MEDIA_ROOT / storage_key
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found for OCR: {image_path}")

    # Encode image as base64
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    # OCR Prompt
    prompt = (
        "Extract ALL readable text from this image. "
        "Return ONLY the text with line breaks preserved. "
        "Do NOT include explanations or comments."
    )

    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_b64],
            }
        ],
    }

    # Call Ollama
    response = requests.post(f"{base_url}/api/chat", json=payload, timeout=240)
    response.raise_for_status()
    data = response.json()

    text = data.get("message", {}).get("content", "").strip()
    tokens = len(text.split())

    return {
        "extracted_text": text,
        "tokens_count": tokens,
        "model_version": model_name,
        "raw_response": data
    }
