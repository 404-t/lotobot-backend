import asyncio
import time
from collections import deque

import httpx
from fastapi import HTTPException

from src.core.logger import get_logger

logger = get_logger(__name__)


class StolotoClient:
    """
    Main client for Stoloto API.
    Manages request queue and provides rate limiting (1 request per second).
    """

    DEFAULT_HEADERS = {
        'gosloto-partner': 'bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize client.

        Args:
            rate_limit: Interval between requests in seconds
        """
        self.rate_limit = rate_limit
        self.request_queue: deque = deque()
        self.last_request_time: float = 0.0
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self.DEFAULT_HEADERS,
            )
        return self._client

    async def _wait_for_rate_limit(self):
        """Wait for rate limit before next request."""
        async with self._lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.rate_limit:
                wait_time = self.rate_limit - time_since_last_request
                logger.debug(f"Rate limit: ожидание {wait_time:.2f} секунд")
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()

    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Execute HTTP request with rate limiting.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional httpx parameters

        Returns:
            httpx Response object
        """
        await self._wait_for_rate_limit()

        client = await self._get_client()
        
        try:
            logger.debug(f"Executing request: {method} {url}")
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for request {url}: {e.response.status_code}")
            raise HTTPException(400, f'Error was occurred while getting data from {url}')
        except httpx.RequestError as e:
            logger.error(f"Request error to {url}: {e}")
            raise HTTPException(400, 'Error was occurred while getting data from {url}')

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Execute GET request."""
        return await self.request("GET", url, **kwargs)

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager support."""
        await self.close()

