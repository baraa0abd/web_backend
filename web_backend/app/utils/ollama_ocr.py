import os
import time
import base64
import requests
from django.conf import settings


def _safe_extract_text_from_response(data):
    # Try several common response shapes that Ollama/llava may return
    if not data:
        return ""

    # shape: { "message": { "content": "..." } }
    try:
        msg = data.get("message")
        if isinstance(msg, dict) and msg.get("content"):
            return msg.get("content")
    except Exception:
        pass

    # shape: { "output": { "content": "..." } }
    try:
        out = data.get("output")
        if isinstance(out, dict) and out.get("content"):
            return out.get("content")
    except Exception:
        pass

    # shape: { "choices": [ { "message": { "content": "..." } } ] }
    try:
        choices = data.get("choices")
        if isinstance(choices, list) and len(choices) > 0:
            first = choices[0]
            if isinstance(first, dict):
                m = first.get("message") or first.get("output")
                if isinstance(m, dict) and m.get("content"):
                    return m.get("content")
    except Exception:
        pass

    # If data itself is a string
    if isinstance(data, str):
        return data

    # Fallback: try to stringify the whole response
    try:
        return str(data)
    except Exception:
        return ""


def llava_extract_text(storage_key, model_name="llava:latest", timeout=30, retries=3):
    """Extract text from an image using Ollama LLaVA model.

    This function is defensive: it retries, validates HTTP status codes,
    and supports multiple response shapes. It always returns a dict with
    the keys: extracted_text, tokens_count, model_version, raw_response.
    """
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

    last_exc = None
    url = f"{base_url}/api/chat"
    for attempt in range(1, retries + 1):
        try:
            res = requests.post(url, json=payload, timeout=timeout)
            # Try to parse JSON; if that fails, we'll capture raw text
            try:
                data = res.json()
            except Exception:
                data = None

            if res.status_code != 200:
                # return a consistent structure when an error occurs
                return {
                    "extracted_text": "",
                    "tokens_count": 0,
                    "model_version": model_name,
                    "raw_response": {"status_code": res.status_code, "body": data or res.text},
                }

            extracted = _safe_extract_text_from_response(data)

            tokens = 0
            try:
                if isinstance(extracted, str) and extracted.strip():
                    tokens = len(extracted.split())
            except Exception:
                tokens = 0

            return {
                "extracted_text": extracted,
                "tokens_count": tokens,
                "model_version": model_name,
                "raw_response": data,
            }

        except requests.exceptions.RequestException as e:
            last_exc = e
            # simple backoff
            if attempt < retries:
                time.sleep(attempt * 0.5)
            continue

    # All retries failed
    return {
        "extracted_text": "",
        "tokens_count": 0,
        "model_version": model_name,
        "raw_response": {"error": str(last_exc) if last_exc else "unknown"},
    }


def check_ollama(timeout=3):
    """Quick health check for an Ollama server.

    Returns a dict: { ok: bool, status_code: int|None, details: str }
    """
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    # try a lightweight endpoint if available
    urls_to_try = [f"{base_url}/api/models", base_url]
    for u in urls_to_try:
        try:
            r = requests.get(u, timeout=timeout)
            return {"ok": r.status_code == 200, "status_code": r.status_code, "details": r.text[:200]}
        except requests.exceptions.RequestException as e:
            # try next
            last_err = e
            continue
    return {"ok": False, "status_code": None, "details": str(last_err)}
