import secrets
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.conf import settings
from .models import AccessToken


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"detail": "Missing username or password"}, status=400)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=401)

        # Create a secure random token
        raw_token = "sk_" + secrets.token_hex(32)

        expiry = timezone.now() + timezone.timedelta(
            hours=getattr(settings, "ACCESS_TOKEN_EXPIRATION_HOURS", 24)
        )

        token = AccessToken.objects.create(
            user=user,
            name="Login Token",
            expires_at=expiry,
        )

        token.set_token(raw_token)
        token.save()

        return Response({
            "token": raw_token,
            "expires_at": expiry,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
            }
        }, status=200)
