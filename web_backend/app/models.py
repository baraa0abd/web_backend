import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# -------------------------
# OCR Status Enum
# -------------------------
class OCRStatus(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CACHED = "cached"

# -------------------------
# CUSTOM USER
# -------------------------
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.ip_address})"


# -------------------------
# IMAGES Table
# -------------------------
class Image(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="images")

    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255, null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    storage_provider = models.CharField(max_length=50, null=True, blank=True)
    storage_key = models.CharField(max_length=500, null=True, blank=True)

    sha256_hash = models.CharField(max_length=200, unique=True)

    deduplicated_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    ocr_status = models.CharField(
        max_length=20, choices=OCRStatus.choices, default=OCRStatus.PENDING
    )
    ocr_started_at = models.DateTimeField(null=True, blank=True)
    ocr_completed_at = models.DateTimeField(null=True, blank=True)

    model_version = models.CharField(max_length=100, null=True, blank=True)

    ollama_response = models.JSONField(null=True, blank=True)
    additional_meta = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.filename} ({self.sha256_hash[:10]}...)"


# -------------------------
# TEXTS Table
# -------------------------
class ExtractedText(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name="texts")
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="texts")

    extracted_text = models.TextField(null=True, blank=True)
    pages = models.IntegerField(default=1)
    language = models.CharField(max_length=20, null=True, blank=True)

    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    tokens_count = models.IntegerField(null=True, blank=True)

    structured = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=100, null=True, blank=True)

    source = models.CharField(max_length=50, default="ollama")
    is_cached = models.BooleanField(default=False)

    def __str__(self):
        return f"Text for {self.image.filename}"


# -------------------------
# ACCESS TOKENS
# -------------------------
class AccessToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_tokens")
    token = models.CharField(max_length=255)   # *Store hashed token in production*
    name = models.CharField(max_length=255, null=True, blank=True)

    scopes = models.JSONField(null=True, blank=True)  # e.g. ['ocr:read', 'ocr:write']

    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)

    def __str__(self):
        return f"Token ({self.name}) for {self.user}"


# -------------------------
# RATE LIMIT TABLE
# -------------------------
class RateLimit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ip_address = models.GenericIPAddressField()
    bucket_key = models.CharField(max_length=100)

    remaining = models.IntegerField()
    limit_value = models.IntegerField()
    reset_at = models.DateTimeField()

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ip_address", "bucket_key")

    def __str__(self):
        return f"{self.ip_address} / {self.bucket_key}"
