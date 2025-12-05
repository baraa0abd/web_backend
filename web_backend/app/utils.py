import hashlib
from django.conf import settings
import io

def compute_sha256_file(file_obj) -> str:
    """
    Compute sha256 of a file-like object. The view should ensure file_obj.seek(0)
    """
    sha = hashlib.sha256()
    # read in chunks
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(8192), b""):
        sha.update(chunk)
    file_obj.seek(0)
    return sha.hexdigest()


def store_file_to_storage(file_obj, filename, storage_provider="local"):
    """
    Replace with actual storage (S3/GCS) logic. Returns storage_key and content_type and size.
    For now assume default Django storage or local filesystem.
    """
    # Example using default storage:
    from django.core.files.storage import default_storage
    path = f"uploads/{filename}"
    saved_path = default_storage.save(path, file_obj)
    # get size
    try:
        size = default_storage.size(saved_path)
    except Exception:
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0)
    return saved_path, file_obj.content_type if hasattr(file_obj, "content_type") else None, size


def call_ollama_ocr(storage_key, model_version=None):
    """
    Placeholder function to call Ollama LLaVA OCR.
    Replace this with your real request to Ollama (HTTP/SDK).
    Should return dict with at minimum:
      - extracted_text (str)
      - structured (dict)
      - confidence (float)
      - tokens_count (int)
      - raw_response (dict)
    """
    # ---- Example dummy response ----
    import time
    time.sleep(1)  # simulate processing
    return {
        "extracted_text": f"Simulated extracted text for {storage_key}",
        "structured": {"blocks": []},
        "confidence": 0.98,
        "tokens_count": 42,
        "raw_response": {"ok": True},
        "model_version": model_version or "llava-ollama-v1",
    }


def get_client_ip_from_request(request):
    """Return the client's IP address from request, honoring X-Forwarded-For if present.

    Note: Only trust X-Forwarded-For if your deployment/front proxy is configured correctly.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # X-Forwarded-For may contain a comma separated list of IPs. First is client.
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def cache_incr_with_ttl(key, timeout, delta=1, initial=1):
    """Increment a cache key safely.

    - Uses `cache.add` to set the initial value with TTL if missing.
    - Uses `cache.incr` when available (atomic on many backends).
    - Falls back to get/set if incr isn't supported.
    Returns the new integer value.
    """
    from django.core.cache import cache

    added = cache.add(key, initial, timeout)
    if added:
        return initial
    try:
        return cache.incr(key, delta)
    except Exception:
        val = cache.get(key, 0) or 0
        val = val + delta
        cache.set(key, val, timeout)
        return val
