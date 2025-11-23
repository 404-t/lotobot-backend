from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class NewsItem(BaseModel):
    """Single news item."""
    model_config = ConfigDict(extra='ignore')

    title: str
    link: str
    date: str | None = None
    description: str | None = None


class NewsResponse(BaseModel):
    """Response with news list."""
    model_config = ConfigDict(extra='ignore')

    news: list[NewsItem]
