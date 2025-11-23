from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.tabs.models import TabsResponse


class TabsStolotoClient(BaseStolotoSection[TabsResponse]):
    """Client for fetching tabs (active draws and promotions) from Stoloto."""

    cache_key: str = "stoloto:tabs:active"
    cache_ttl: int = 600
    response_model = TabsResponse

    async def _fetch_from_api(self) -> TabsResponse:
        """Fetch tabs data from Stoloto API."""
        url = 'https://api.stoloto.ru/cms/api/tabs?platform=OS&user-segment=ALL'
        
        response = await self.stoloto_client.get(url)
        data = response.json()
        
        return TabsResponse(**data)

