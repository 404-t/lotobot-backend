from src.integrations.stoloto.client import StolotoClient
from src.integrations.stoloto.base import BaseStolotoSection
from src.integrations.stoloto.main.client import MainStolotoClient
from src.integrations.stoloto.news.client import NewsStolotoClient
from src.integrations.stoloto.tabs.client import TabsStolotoClient
from src.integrations.stoloto.details.client import DetailsStolotoClient
from src.integrations.stoloto.list.client import ListStolotoClient

__all__ = [
    "BaseStolotoSection",
    "DetailsStolotoClient",
    "ListStolotoClient",
    "MainStolotoClient",
    "NewsStolotoClient",
    "StolotoClient",
    "TabsStolotoClient",
]

