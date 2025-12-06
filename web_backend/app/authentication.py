from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import AccessToken
from django.utils import timezone
import hashlib


class BearerTokenAuthentication(BaseAuthentication):

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith(self.keyword):
            return None

        raw_token = auth_header.split(" ")[1].strip()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        try:
            token = AccessToken.objects.select_related("user").get(token_hash=token_hash)
        except AccessToken.DoesNotExist:
            raise AuthenticationFailed("Invalid token")

        if token.revoked:
            raise AuthenticationFailed("Token is revoked")

        if token.is_expired():
            raise AuthenticationFailed("Token expired")

        token.mark_used()

        return (token.user, token)
