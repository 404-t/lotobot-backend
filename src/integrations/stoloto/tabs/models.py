from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class Tab(BaseModel):
    model_config = ConfigDict(extra='ignore')

    lotteryCode: str
    draw: int
    prizeTitle: str | None = None
    prizeSubtitle: str | None = None
    value: str | None = None
    text: str | None = None
    tvChannel: str | None = None
    offerText: str | None = None


class TabsResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    data: list[Tab]

