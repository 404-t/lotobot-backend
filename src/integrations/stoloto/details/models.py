from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class Combination(BaseModel):
    model_config = ConfigDict(extra='ignore')

    serialized: list[str]


class Title(BaseModel):
    model_config = ConfigDict(extra='ignore')

    ru: str


class WinCategory(BaseModel):
    model_config = ConfigDict(extra='ignore')

    number: int
    participants: int
    amount: int
    totalAmount: int
    title: Title
    altPrize: str | None = None


class Winner(BaseModel):
    model_config = ConfigDict(extra='ignore')

    participants: int
    amount: int
    totalAmount: int
    category: int


class Draw(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: int
    number: int
    date: str
    status: str
    completed: bool
    superPrize: int
    prize: int
    superPrizeWon: bool
    secondPrizeWon: bool
    ticketsCount: int
    betsCount: int
    winningCombination: list[str]
    combination: Combination | None = None
    winners: list[Winner] = []
    winCategories: list[WinCategory] = []


class MainCategoriesResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    draws: list[Draw]
    hasMore: bool
