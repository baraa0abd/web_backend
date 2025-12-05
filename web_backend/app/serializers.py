from rest_framework import serializers
from .models import Image, ExtractedText, AccessToken, User
from django.utils import timezone


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff", "is_superuser")


class ImageUploadSerializer(serializers.ModelSerializer):
    file = serializers.ImageField(write_only=True, required=True)
    class Meta:
        model = Image
        fields = ("id", "file", "filename", "content_type", "size_bytes",
                  "storage_provider", "storage_key", "sha256_hash", "uploaded_at", "ocr_status")
        read_only_fields = ("id", "sha256_hash", "uploaded_at", "ocr_status")

    def create(self, validated_data):
        return super().create(validated_data)


class ImageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ("id", "filename", "sha256_hash", "uploaded_at", "ocr_status", "model_version")


class ExtractedTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedText
        fields = ("id", "image", "user", "extracted_text", "pages", "language",
                  "confidence", "tokens_count", "structured", "created_at", "model_version", "is_cached")
        read_only_fields = ("id", "created_at")


class AccessTokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessToken
        fields = ("id", "name", "scopes", "expires_at")
        read_only_fields = ("id",)

    def create(self, validated_data):
        user = self.context["request"].user
        import secrets
        raw = secrets.token_urlsafe(32)
        token_obj = AccessToken.objects.create(user=user, token=raw, **validated_data)
        token_obj._raw_token = raw 
        return token_obj


class AccessTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessToken
        fields = ("id", "name", "scopes", "last_used_at", "expires_at", "created_at", "revoked")
        read_only_fields = fields
