from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,  # values come back as str instead of bytes
    max_connections=20,  # cap on open connections per process
    socket_connect_timeout=5,  # seconds to open a connection
    socket_timeout=5,  # seconds per command (without this a hung Redis blocks forever)
    retry_on_timeout=True,  # retry a command once if it timed out (needs socket_timeout)
    health_check_interval=30,  # ping idle connections every 30s so dead sockets are replaced
)
async def init_redis() -> None:
    """Verify Redis connection on application startup."""
    try:
        await redis_client.ping()
        logger.info("Connected to Redis successfully.")
    except RedisError as exc:
        logger.error("Failed to connect to Redis: %s", exc)
        raise


async def close_redis() -> None:
    """Close Redis connection pool on application shutdown."""
    await redis_client.aclose()
    logger.info("Redis connection closed.")
