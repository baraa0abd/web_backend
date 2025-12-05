import hashlib
from django.conf import settings


def compute_sha256_file(file_obj) -> str:
    """
    Compute SHA-256 of uploaded file in chunks.
    Ensures pointer is reset for later use.
    """
    sha = hashlib.sha256()
    file_obj.seek(0)

    for chunk in iter(lambda: file_obj.read(8192), b""):
        sha.update(chunk)

    file_obj.seek(0)
    return sha.hexdigest()


def store_file_to_storage(file_obj, filename, storage_provider="local"):
    """
    Saves the uploaded file to Django's default storage (local filesystem or S3 if configured).

    Returns:
        storage_key (path inside storage backend)
        content_type
        size_bytes
    """
    from django.core.files.storage import default_storage

    # Where the image will be stored
    storage_key = f"uploads/{filename}"

    # Save to storage (this handles filesystem or S3 depending on settings)
    saved_path = default_storage.save(storage_key, file_obj)

    # Try to get file size reliably
    try:
        size = default_storage.size(saved_path)
    except Exception:
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0)

    content_type = getattr(file_obj, "content_type", None)

    return saved_path, content_type, size


# -------------------------------------------------------------------
#  REAL LLaVA OCR WRAPPER
# -------------------------------------------------------------------
from .ollama_ocr import llava_extract_text


def call_ollama_ocr(storage_key, model_version=None):
    """
    Call LLaVA OCR implemented in ollama_ocr.py.

    Must return the unified OCR object expected by your project:
        - extracted_text
        - pages
        - language
        - confidence
        - tokens_count
        - structured
        - model_version
        - raw_response
    """
    result = llava_extract_text(storage_key, model_version or "llava:latest")

    return {
        "extracted_text": result["extracted_text"],
        "pages": 1,                      # LLaVA does not provide page count
        "language": None,                # Could be added later
        "confidence": None,              # LLaVA does not output numeric confidence
        "tokens_count": result["tokens_count"],
        "structured": None,              # Reserved for future structured OCR output
        "model_version": result["model_version"],
        "raw_response": result["raw_response"],
    }


# -------------------------------------------------------------------
#  CLIENT IP DETECTION
# -------------------------------------------------------------------
def get_client_ip_from_request(request):
    """
    Extract real client IP, considering proxies such as Cloudflare or Nginx.
    """
    # Trusted header if behind Cloudflare
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


# -------------------------------------------------------------------
#  SAFE REDIS/DJANGO-CACHE COUNTER (USED FOR RATE LIMITING)
# -------------------------------------------------------------------
def cache_incr_with_ttl(key, timeout, delta=1, initial=1):
    """
    Increment key with TTL safely.

    - Sets initial value if absent
    - Uses atomic INCR when supported (Redis)
    - Falls back to get/set for local cache
    """
    from django.core.cache import cache

    # Try atomic add (sets TTL)
    created = cache.add(key, initial, timeout)
    if created:
        return initial

    # Try atomic increment
    try:
        return cache.incr(key, delta)
    except Exception:
        current = cache.get(key, 0) or 0
        new_value = current + delta
        cache.set(key, new_value, timeout)
        return new_value
