from rest_framework import generics, status, viewsets, permissions, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.utils import timezone

from .serializers import (
    ImageUploadSerializer, ImageListSerializer, ExtractedTextSerializer,
    AccessTokenCreateSerializer, AccessTokenSerializer, UserSerializer
)
from .models import Image, ExtractedText, AccessToken, User
from .permissions import IsOwnerOrAdmin
from .utils import compute_sha256_file, store_file_to_storage, call_ollama_ocr, get_client_ip_from_request, cache_incr_with_ttl
from .throttling import IPRateLimitThrottle
from rest_framework.parsers import MultiPartParser, FormParser


class UploadImageView(generics.GenericAPIView):
    """
    POST /api/images/upload/
    - Enforce demo limit: max 5 images per user
    - Check sha256 cache: if exists, link or return cached result
    - Store file, create Image row, trigger OCR (sync here; replace with background task if desired)
    """
    serializer_class = ImageUploadSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = (permissions.IsAuthenticated,)
    throttle_classes = (IPRateLimitThrottle,)
    bucket_key = "upload:minute"  # used by throttling

    def post(self, request, *args, **kwargs):
        user = request.user

        # Enforce per-IP upload limit without using the database.
        # Allow up to 5 uploads per IP per WINDOW_SECONDS interval.
        UPLOAD_LIMIT = 5
        WINDOW_SECONDS = 60 * 60 * 24  # 1 day; change to 60 for per-minute

        ip = get_client_ip_from_request(request) or "unknown"
        cache_key = f"uploads:ip:{ip}"
        count_for_ip = cache_incr_with_ttl(cache_key, WINDOW_SECONDS, delta=1, initial=1)
        if count_for_ip > UPLOAD_LIMIT:
            # Optionally provide Retry-After header: remaining TTL
            from django.core.cache import cache
            retry_after = None
            try:
                # Some cache backends support ttl()
                retry_after = cache.ttl(cache_key)
            except Exception:
                retry_after = WINDOW_SECONDS

            return Response({"detail": "Upload limit exceeded for your IP."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                            headers={"Retry-After": str(retry_after)})

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # compute sha256
        sha = compute_sha256_file(file_obj)

        # check cache by hash
        try:
            existing = Image.objects.get(sha256_hash=sha)
            # if existing has OCR done, create a new deduplicated image record pointing to it OR reuse its text
            if existing.ocr_status in ("done", "cached"):
                # Option A: create a new Image row referencing the original (deduplication)
                new_img = Image.objects.create(
                    user=user,
                    filename=file_obj.name,
                    content_type=getattr(file_obj, "content_type", None),
                    size_bytes=getattr(file_obj, "size", None),
                    storage_provider=existing.storage_provider,
                    storage_key=existing.storage_key,
                    sha256_hash=sha,
                    deduplicated_to=existing,
                    ocr_status="cached",
                    ocr_completed_at=existing.ocr_completed_at,
                    model_version=existing.model_version,
                    ollama_response=existing.ollama_response,
                    additional_meta=existing.additional_meta,
                )
                # Optionally create ExtractedText pointing to the same result
                # copy latest text
                latest_text = existing.texts.order_by("-created_at").first()
                if latest_text:
                    copied = ExtractedText.objects.create(
                        image=new_img,
                        user=user,
                        extracted_text=latest_text.extracted_text,
                        pages=latest_text.pages,
                        language=latest_text.language,
                        confidence=latest_text.confidence,
                        tokens_count=latest_text.tokens_count,
                        structured=latest_text.structured,
                        model_version=latest_text.model_version,
                        source=latest_text.source,
                        is_cached=True,
                    )
                    serializer = ExtractedTextSerializer(copied)
                    return Response({
                        "cached": True,
                        "image": ImageListSerializer(new_img).data,
                        "extracted_text": serializer.data,
                    }, status=status.HTTP_200_OK)

                return Response({
                    "cached": True,
                    "image": ImageListSerializer(new_img).data,
                }, status=status.HTTP_200_OK)

        except Image.DoesNotExist:
            existing = None

        # store file to storage (S3/local)
        storage_key, content_type, size = store_file_to_storage(file_obj, file_obj.name)

        # create Image row with pending processing
        new_img = Image.objects.create(
            user=user,
            filename=file_obj.name,
            content_type=content_type or getattr(file_obj, "content_type", None),
            size_bytes=size,
            storage_provider="default",
            storage_key=storage_key,
            sha256_hash=sha,
            ocr_status="processing",
            ocr_started_at=timezone.now(),
        )

        # Trigger OCR (synchronous here; switch to Celery for async)
        try:
            ocr_result = call_ollama_ocr(storage_key, model_version=None)
        except Exception as e:
            new_img.ocr_status = "failed"
            new_img.ollama_response = {"error": str(e)}
            new_img.save(update_fields=["ocr_status", "ollama_response"])
            return Response({"detail": "OCR failed", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Save results
        new_img.ocr_status = "done"
        new_img.ocr_completed_at = timezone.now()
        new_img.model_version = ocr_result.get("model_version")
        new_img.ollama_response = ocr_result.get("raw_response")
        new_img.save()

        extracted = ExtractedText.objects.create(
            image=new_img,
            user=user,
            extracted_text=ocr_result.get("extracted_text"),
            pages=ocr_result.get("pages", 1),
            language=ocr_result.get("language"),
            confidence=ocr_result.get("confidence"),
            tokens_count=ocr_result.get("tokens_count"),
            structured=ocr_result.get("structured"),
            model_version=ocr_result.get("model_version"),
            source="ollama",
            is_cached=False,
        )

        return Response({
            "cached": False,
            "image": ImageListSerializer(new_img).data,
            "extracted_text": ExtractedTextSerializer(extracted).data,
        }, status=status.HTTP_201_CREATED)


class ImageListView(generics.ListAPIView):
    serializer_class = ImageListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Image.objects.filter(user=self.request.user).order_by("-uploaded_at")


class ImageDetailView(generics.RetrieveAPIView):
    serializer_class = ImageListSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrAdmin)
    lookup_field = "id"
    queryset = Image.objects.all()

    def get(self, request, *args, **kwargs):
        img = self.get_object()
        latest_text = img.texts.order_by("-created_at").first()
        data = self.get_serializer(img).data
        data["latest_text"] = ExtractedTextSerializer(latest_text).data if latest_text else None
        return Response(data)


class ExtractedTextDetailView(generics.RetrieveAPIView):
    serializer_class = ExtractedTextSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrAdmin)
    queryset = ExtractedText.objects.all()


class AccessTokenViewSet(viewsets.ModelViewSet):
    serializer_class = AccessTokenSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return AccessToken.objects.filter(user=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return AccessTokenCreateSerializer
        return AccessTokenSerializer

    def perform_create(self, serializer):
        token_obj = serializer.save()
        # return raw token to user only once
        data = AccessTokenSerializer(instance=token_obj).data
        raw = getattr(token_obj, "_raw_token", None)
        resp = {"token": raw, "meta": data}
        # DRF doesn't let us return a custom body from perform_create; we instead set it on the view
        self._created_response = resp

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(getattr(self, "_created_response", {}), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        obj = self.get_object()
        obj.revoked = True
        obj.save()
        return Response({"revoked": True}, status=status.HTTP_200_OK)


class DashboardView(generics.GenericAPIView):
    """
    GET /api/dashboard/ -> returns user uploads, total counts, recent texts
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        user = request.user
        images = Image.objects.filter(user=user).order_by("-uploaded_at")[:50]
        texts = ExtractedText.objects.filter(user=user).order_by("-created_at")[:50]
        return Response({
            "user": UserSerializer(user).data,
            "images": ImageListSerializer(images, many=True).data,
            "recent_texts": ExtractedTextSerializer(texts, many=True).data,
            "counts": {
                "images_total": Image.objects.filter(user=user).count(),
                "texts_total": ExtractedText.objects.filter(user=user).count(),
            }
        })
