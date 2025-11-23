from src.integrations.redis import RedisClient
from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.client import StolotoClient
from src.integrations.stoloto.details.models import MainCategoriesResponse


class DetailsStolotoClient(BaseStolotoSection[MainCategoriesResponse]):
    """Client for fetching draw details from Stoloto."""

    cache_key: str = "stoloto:details:draws"
    cache_ttl: int = 600
    response_model = MainCategoriesResponse

    def __init__(
        self,
        stoloto_client: StolotoClient,
        redis_client: RedisClient,
        lottery_code: str = "ruslotto",
        count: int = 5
    ):
        """
        Initialize client for draw details.

        Args:
            stoloto_client: Client for Stoloto API
            redis_client: Client for Redis
            lottery_code: Lottery code (ruslotto, gzhl, 5x36, etc.)
            count: Number of draws to fetch
        """
        super().__init__(stoloto_client, redis_client)
        self.lottery_code = lottery_code
        self.count = count
        self.cache_key = f"stoloto:details:draws:{lottery_code}:{count}"

    async def _fetch_from_api(self) -> MainCategoriesResponse:
        """Fetch draw details from Stoloto API."""
        url = f'https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/{self.lottery_code}/details?count={self.count}'
        
        response = await self.stoloto_client.get(url)
        data = response.json()
        
        return MainCategoriesResponse(**data)

