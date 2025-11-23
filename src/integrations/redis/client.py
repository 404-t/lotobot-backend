import redis
import json

from src.core.logger import get_logger

logger = get_logger('RedisClient')


class RedisClient:
    def __init__(self, url):
        self.client: redis.asyncio.Redis = redis.asyncio.from_url(url, decode_responses=True)

    async def get_json(self, key: str):
        logger.debug(f'Get data for {key}')
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value, expire: int):
        logger.debug(f'Save data for {key}')
        await self.client.set(key, json.dumps(value), ex=expire)
