from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import AccessToken
import hashlib


class BearerTokenAuthentication(BaseAuthentication):
    """
    Header format:
    Authorization: Bearer sk_xxxxxxx
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth = request.headers.get("Authorization")

        if not auth or not auth.startswith(self.keyword):
            return None

        raw_token = auth.split(" ", 1)[1].strip()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        try:
            token = AccessToken.objects.select_related("user").get(token_hash=token_hash)
        except AccessToken.DoesNotExist:
            raise AuthenticationFailed("Invalid or expired token")

        if token.revoked:
            raise AuthenticationFailed("Token has been revoked")

        if token.expires_at and token.is_expired():
            raise AuthenticationFailed("Token expired")

        token.mark_used()
        return (token.user, token)
