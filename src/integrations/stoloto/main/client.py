from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.main.models import MainCategoriesResponse


class MainStolotoClient(BaseStolotoSection[MainCategoriesResponse]):
    """Client for fetching main categories from Stoloto."""

    cache_key: str = "stoloto:main:categories"
    cache_ttl: int = 600
    response_model = MainCategoriesResponse

    async def _fetch_from_api(self) -> MainCategoriesResponse:
        """Fetch main categories from Stoloto API."""
        url = 'https://api.stoloto.ru/cms/api/main-categories?platform=MS&user-segment=ALL'
        
        response = await self.stoloto_client.get(url)
        data = response.json()
        
        return MainCategoriesResponse(**data)

