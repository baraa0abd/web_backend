import hashlib
from django.core.files.storage import default_storage
from django.core.cache import cache


def compute_sha256(file_obj):
    sha = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(8192), b""):
        sha.update(chunk)
    file_obj.seek(0)
    return sha.hexdigest()


def save_file(file_obj, filename):
    path = f"uploads/{filename}"
    saved = default_storage.save(path, file_obj)
    return saved


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0] if xff else request.META.get("REMOTE_ADDR")


def cache_incr(key, ttl):
    added = cache.add(key, 1, ttl)
    if added:
        return 1
    return cache.incr(key)
