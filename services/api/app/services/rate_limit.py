from __future__ import annotations

from datetime import datetime, timezone

from redis import Redis

from app.core.config import get_settings
from app.workers.queue import get_redis_connection

settings = get_settings()


class RateLimitService:
    def __init__(self, redis_connection: Redis | None = None) -> None:
        self.redis = redis_connection or get_redis_connection()

    def allow(self, client_ip: str) -> bool:
        minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        key = f"public-rate:{client_ip}:{minute_bucket}"
        try:
            current = self.redis.incr(key)
            if current == 1:
                self.redis.expire(key, 90)
            return int(current) <= settings.public_rate_limit_per_minute
        except Exception:
            return True
