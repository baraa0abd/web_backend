import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import hashlib



class OCRStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
    CACHED = "cached", "Cached"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    is_admin = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email or self.username

class Image(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL,
        related_name="images", db_index=True
    )

    filename = models.CharField(max_length=255, db_index=True)
    content_type = models.CharField(max_length=255, null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    storage_provider = models.CharField(max_length=50, null=True, blank=True)
    storage_key = models.CharField(max_length=500, null=True, blank=True)

    sha256_hash = models.CharField(max_length=200, unique=True, db_index=True)

    deduplicated_to = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
        db_index=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    ocr_status = models.CharField(
        max_length=20, choices=OCRStatus.choices,
        default=OCRStatus.PENDING, db_index=True
    )
    ocr_started_at = models.DateTimeField(null=True, blank=True)
    ocr_completed_at = models.DateTimeField(null=True, blank=True)

    model_version = models.CharField(max_length=100, null=True, blank=True)

    ollama_response = models.JSONField(null=True, blank=True)
    additional_meta = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.filename} ({self.sha256_hash[:10]}...)"


class ExtractedText(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    image = models.ForeignKey(
        Image, on_delete=models.CASCADE, related_name="texts", db_index=True
    )
    user = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL,
        related_name="texts", db_index=True
    )

    extracted_text = models.TextField(null=True, blank=True)
    pages = models.PositiveIntegerField(default=1)
    language = models.CharField(max_length=20, null=True, blank=True, db_index=True)

    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    tokens_count = models.IntegerField(null=True, blank=True)

    structured = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model_version = models.CharField(max_length=100, null=True, blank=True)

    source = models.CharField(max_length=50, default="ollama", db_index=True)
    is_cached = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"Text for {self.image.filename}"


class AccessToken(models.Model):
    """
    Secure API token stored as SHA256 hash.
    Never store raw token in DB.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="access_tokens",
        db_index=True,
    )

    # Secure hashed token
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)

    name = models.CharField(max_length=255, null=True, blank=True)
    scopes = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    revoked = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    # ---------------------------------------------------
    # TOKEN HELPERS
    # ---------------------------------------------------

    def set_token(self, raw_token: str):
        """Hash and store token securely."""
        self.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    def check_token(self, raw_token: str) -> bool:
        return hashlib.sha256(raw_token.encode()).hexdigest() == self.token_hash

    def is_expired(self):
        return self.expires_at and timezone.now() >= self.expires_at

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])