from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
import secrets

from .models import AccessToken
from .serializers import AccessTokenSerializer


class AccessTokenViewSet(viewsets.ModelViewSet):
    serializer_class = AccessTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AccessToken.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request):
        raw_token = "sk_" + secrets.token_hex(32)

        expiry = timezone.now() + timezone.timedelta(
            hours=request.data.get("expires_in", 24)
        )

        token = AccessToken.objects.create(
            user=request.user,
            name=request.data.get("name", "API Token"),
            expires_at=expiry
        )

        token.set_token(raw_token)
        token.save()

        return Response({
            "token": raw_token,
            "meta": AccessTokenSerializer(token).data
        }, status=201)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        token = self.get_object()
        token.revoked = True
        token.save()
        return Response({"revoked": True})
