from rest_framework.throttling import BaseThrottle
from django.utils import timezone
from ipaddress import ip_address

# `RateLimit` model may be removed; import lazily to allow migrations that delete it.
def _get_rate_limit_model():
    try:
        from .models import RateLimit
        return RateLimit
    except Exception:
        return None


class IPRateLimitThrottle(BaseThrottle):
    """
    Throttle by IP using the RateLimit DB table.
    Expect view to set `bucket_key` attribute (e.g. 'upload:minute' or 'upload:day').
    """

    def allow_request(self, request, view):
        bucket = getattr(view, "bucket_key", "upload:minute")
        ip = self.get_ident(request)
        now = timezone.now()

        # Try to use DB-backed RateLimit when available; otherwise skip throttling.
        RateLimit = _get_rate_limit_model()
        if RateLimit is None:
            # No DB model available (likely being removed) — allow request.
            return True

        # Simple policy: create or fetch a bucket.
        rl, created = RateLimit.objects.get_or_create(
            ip_address=ip,
            bucket_key=bucket,
            defaults={
                "remaining": 5,
                "limit_value": 5,
                "reset_at": now + timezone.timedelta(minutes=1),
            },
        )

        # Reset if past reset_at
        if rl.reset_at <= now:
            # reset bucket
            # choose reset interval based on bucket naming
            if "minute" in bucket:
                interval = timezone.timedelta(minutes=1)
            elif "hour" in bucket:
                interval = timezone.timedelta(hours=1)
            elif "day" in bucket:
                interval = timezone.timedelta(days=1)
            else:
                interval = timezone.timedelta(minutes=1)

            rl.remaining = rl.limit_value
            rl.reset_at = now + interval
            rl.save()

        if rl.remaining <= 0:
            return False

        # decrement and save
        rl.remaining -= 1
        rl.updated_at = now
        rl.save()
        return True
