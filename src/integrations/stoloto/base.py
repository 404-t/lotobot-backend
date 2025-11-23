from abc import ABC, abstractmethod
from typing import TypeVar, Generic

from pydantic import BaseModel

from src.integrations.redis import RedisClient
from src.integrations.stoloto.client import StolotoClient
from src.core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)


class BaseStolotoSection(ABC, Generic[T]):
    """
    Base class for Stoloto sections.
    Provides Redis caching functionality.
    """

    cache_key: str = ""
    cache_ttl: int = 3600
    response_model: type[T]

    def __init__(self, stoloto_client: StolotoClient, redis_client: RedisClient):
        """
        Initialize section.

        Args:
            stoloto_client: Client for Stoloto API
            redis_client: Client for Redis
        """
        self.stoloto_client = stoloto_client
        self.redis_client = redis_client

        if not self.response_model:
            raise ValueError(f"response_model должен быть задан в классе {self.__class__.__name__}")

    def _validate_cache_key(self):
        """Validates that cache_key is set."""
        if not self.cache_key:
            raise ValueError(f"cache_key должен быть задан в классе {self.__class__.__name__}")

    async def _get_from_cache(self) -> T | None:
        """
        Get data from cache.

        Returns:
            Deserialized model or None if not cached
        """
        self._validate_cache_key()
        try:
            cached_data = await self.redis_client.get_json(self.cache_key)
            if cached_data:
                logger.debug(f"Data found in cache for key: {self.cache_key}")
                return self.response_model(**cached_data)
            return None
        except Exception as e:
            logger.warning(f"Error getting data from cache: {e}")
            return None

    async def _save_to_cache(self, data: T):
        """
        Save data to cache.

        Args:
            data: Data model to save
        """
        self._validate_cache_key()
        try:
            data_dict = data.model_dump()
            await self.redis_client.set_json(self.cache_key, data_dict, self.cache_ttl)
            logger.debug(f"Data saved to cache with key: {self.cache_key}, TTL: {self.cache_ttl}s")
        except Exception as e:
            logger.error(f"Error saving data to cache: {e}")

    @abstractmethod
    async def _fetch_from_api(self) -> T:
        """
        Fetch data from Stoloto API.
        Must be implemented in subclasses.

        Returns:
            Data model
        """
        pass

    async def get(self, force_refresh: bool = False) -> T:
        """
        Get data from cache or API.

        Args:
            force_refresh: If True, ignores cache and fetches fresh data

        Returns:
            Data model
        """
        if not force_refresh:
            cached_data = await self._get_from_cache()
            if cached_data:
                return cached_data

        logger.info(f"Fetching data from API for section: {self.__class__.__name__}")
        fresh_data = await self._fetch_from_api()
        await self._save_to_cache(fresh_data)
        return fresh_data

