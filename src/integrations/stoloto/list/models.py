from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class Bet(BaseModel):
    """Bet in a packet."""
    model_config = ConfigDict(extra='ignore')

    game: str
    count: int
    draw: int
    prize: int
    drawDate: int


class Packet(BaseModel):
    """Ticket packet."""
    model_config = ConfigDict(extra='ignore')

    price: int
    name: str
    description: str | None = None
    bets: list[Bet]
    forMain: bool | None = False


class PacketsResponse(BaseModel):
    """Response with packet list."""
    model_config = ConfigDict(extra='ignore')

    packets: list[Packet]
