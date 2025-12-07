import secrets
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import AccessToken, Image, ExtractedText
from .serializers import *
from .utils.common import *
from .utils.ollama_ocr import llava_extract_text, check_ollama

# --------------------------------------------------------
# OCR ONLY (no saving, just extract text from image)
# --------------------------------------------------------
class OCRExtractView(APIView):
    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            return Response({"error": "Image is required"}, status=400)

        # Save temporarily for LLaVA processing
        tmp_path = save_file(image, image.name)

        # Call LLaVA OCR
        ocr = llava_extract_text(tmp_path)

        return Response({
            "success": True,
            "extracted_text": ocr["extracted_text"],
            "model_version": ocr["model_version"],
            "tokens_count": ocr["tokens_count"],
        })

# --------------------------------------------------------
# LOGIN (returns API token)
# --------------------------------------------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate

        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password")
        )

        if not user:
            return Response({"detail": "Invalid credentials"}, status=401)

        raw_token = "sk_" + secrets.token_hex(32)

        expiry = timezone.now() + timezone.timedelta(hours=24)

        token = AccessToken(
            user=user,
            name="Login Token",
            expires_at=expiry
        )
        token.set_token(raw_token)
        token.save()

        return Response({
            "token": raw_token,
            "expires_at": expiry,
            "user": UserSerializer(user).data,
        })


# --------------------------------------------------------
# UPLOAD IMAGE + OCR
# --------------------------------------------------------
class UploadImageView(APIView):
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file"}, status=400)

        # Rate limit (per IP — 5 uploads / day)
        ip = get_client_ip(request)
        key = f"upload:{ip}"
        # if cache_incr(key, 86400) > 5:
        #     return Response({"detail": "Daily upload limit reached"}, status=429)

        sha = compute_sha256(file)
        stored_path = save_file(file, file.name)

        image = Image.objects.create(
            user=request.user,
            filename=file.name,
            content_type=file.content_type,
            size_bytes=file.size,
            storage_key=stored_path,
            sha256_hash=sha,
            ocr_status="processing",
        )

        # Run OCR
        ocr = llava_extract_text(image.storage_key)

        image.ocr_status = "done"
        image.ocr_completed_at = timezone.now()
        image.model_version = ocr["model_version"]
        image.ollama_response = ocr["raw_response"]
        image.save()

        text = ExtractedText.objects.create(
            image=image,
            user=request.user,
            extracted_text=ocr["extracted_text"],
            language="en",
            confidence=0.99,
            tokens_count=ocr["tokens_count"],
        )

        return Response({
            "image": ImageSerializer(image).data,
            "extracted_text": ExtractedTextSerializer(text).data,
        })


# --------------------------------------------------------
# DASHBOARD
# --------------------------------------------------------
class DashboardView(APIView):
    def get(self, request):
        return Response({
            "total_images": Image.objects.filter(user=request.user).count(),
            "total_texts": ExtractedText.objects.filter(user=request.user).count(),
        })


class OllamaHealthView(APIView):
    """Health-check endpoint to verify Ollama connectivity."""

    permission_classes = [AllowAny]

    def get(self, request):
        status = check_ollama()
        code = 200 if status.get("ok") else 502
        return Response({"ok": status.get("ok"), "status_code": status.get("status_code"), "details": status.get("details")}, status=code)
