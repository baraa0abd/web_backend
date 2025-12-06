import os
import base64
import requests
from django.conf import settings


def llava_extract_text(storage_key, model_name="llava:latest"):
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    img_path = settings.MEDIA_ROOT / storage_key

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": "Extract all readable text from the image.",
                "images": [img_b64],
            }
        ],
    }

    res = requests.post(f"{base_url}/api/chat", json=payload)
    data = res.json()

    return {
        "extracted_text": data["message"]["content"],
        "tokens_count": len(data["message"]["content"].split()),
        "model_version": model_name,
        "raw_response": data,
    }
