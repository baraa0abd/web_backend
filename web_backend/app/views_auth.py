from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import AccessToken
from django.utils import timezone
import secrets


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

        # ----- CREATE TOKEN -----
        raw_token = secrets.token_hex(32)  # 64-char secure token

        token_record = AccessToken.objects.create(
            user=user,
            name="login-token",
            expires_at=None,  # You can add expiry later
        )

        # store token hash
        token_record.set_token(raw_token)
        token_record.save()

        return Response({
            "token": raw_token,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        }, status=200)
