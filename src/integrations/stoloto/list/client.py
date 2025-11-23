import re

from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.list.models import PacketsResponse, Packet, Bet


def clean_html(text: str) -> str:
    """Remove HTML tags and entities from text."""
    if not text:
        return ""

    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&laquo;', '"')
    text = text.replace('&raquo;', '"')
    text = text.replace('&quot;', '"')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')

    return re.sub(r'\s+', ' ', text).strip()

class ListStolotoClient(BaseStolotoSection[PacketsResponse]):
    """Client for fetching packet list from Stoloto."""

    cache_key: str = "stoloto:list:packets"
    cache_ttl: int = 600
    response_model = PacketsResponse

    async def _fetch_from_api(self) -> PacketsResponse:
        """Fetch packet list from Stoloto API."""
        url = 'https://www.stoloto.ru/p/api/mobile/api/v35/packets/list'
        
        response = await self.stoloto_client.get(url)
        data = response.json()

        packets = []
        for packet_data in data.get('packets', []):
            name = packet_data.get('name', {}).get('ru', '')
            description = packet_data.get('description', {}).get('ru') or None

            name = clean_html(name)
            if description:
                description = clean_html(description)

            bets = []
            for bet_data in packet_data.get('bets', []):
                bets.append(Bet(**bet_data))

            packet = Packet(
                price=packet_data['price'],
                name=name,
                description=description,
                bets=bets,
                forMain=packet_data.get('forMain', False),
            )
            packets.append(packet)

        return PacketsResponse(packets=packets)

