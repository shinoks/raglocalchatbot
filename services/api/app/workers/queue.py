from redis import Redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()


def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_ingestion_queue() -> Queue:
    return Queue("ingestion", connection=get_redis_connection())
