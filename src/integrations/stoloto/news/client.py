import re
from datetime import datetime
from urllib.parse import urljoin

from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.news.models import NewsResponse, NewsItem


def clean_html_text(text: str) -> str:
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


def parse_news_html(html: str, base_url: str = "https://www.stoloto.ru") -> list[NewsItem]:
    """Parse news HTML page and extract information."""
    news_items = []

    news_with_titles = re.findall(
        r'<a[^>]+href=[\"\']([^\"\']*press/news/[^\"\']+)[\"\'][^>]*>(.*?)</a>',
        html,
        re.I | re.DOTALL
    )

    for link, title_html in news_with_titles:
        link = link.split('?')[0].split('#')[0]

        if link.startswith('/'): # noqa
            full_link = urljoin(base_url, link)
        else:
            full_link = link

        if not re.search(r'/press/news/\d{4}/\d{2}/\d{2}/', link):
            continue

        title = clean_html_text(title_html)

        if not title or len(title) < 5:
            continue

        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
        date_str = None
        if date_match:
            year, month, day = date_match.groups()
            try: # noqa
                date_str = datetime(int(year), int(month), int(day)).strftime("%d.%m.%Y")
            except Exception:
                pass

        news_items.append(NewsItem(
            title=title,
            link=full_link,
            date=date_str,
        ))

    unique_news = {}
    for item in news_items:
        link = item.link
        if link not in unique_news or not unique_news[link].title:
            unique_news[link] = item

    return list(unique_news.values())


class NewsStolotoClient(BaseStolotoSection[NewsResponse]):
    """Client for fetching news from Stoloto."""

    cache_key: str = "stoloto:news:list"
    cache_ttl: int = 600
    response_model = NewsResponse

    async def _fetch_from_api(self) -> NewsResponse:
        """Fetch news by parsing Stoloto HTML page."""
        url = 'https://www.stoloto.ru/press/news'
        
        response = await self.stoloto_client.get(url)
        news_items = parse_news_html(response.text)
        
        return NewsResponse(news=news_items)

