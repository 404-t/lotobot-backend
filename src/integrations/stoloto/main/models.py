from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class Image(BaseModel):
    model_config = ConfigDict(extra='ignore')

    image: str
    imageFormat: str | None = None


class Spinner(BaseModel):
    model_config = ConfigDict(extra='ignore')

    name: str
    link: str
    superPrize: str | None = None
    publishStartDate: str | None = None
    publishEndDate: str | None = None
    images: list[Image] = []


class Button(BaseModel):
    model_config = ConfigDict(extra='ignore')

    link: str


class Item1(BaseModel):
    model_config = ConfigDict(extra='ignore')

    buttons: list[Button] = []


class Content1(BaseModel):
    model_config = ConfigDict(extra='ignore')

    item: Item1


class Story(BaseModel):
    model_config = ConfigDict(extra='ignore')

    contents: list[Content1] = []


class SpecialCard(BaseModel):
    model_config = ConfigDict(extra='ignore')

    name: str
    link: str
    superPrize: str | None = None
    promoStartDate: str | None = None
    promoEndDate: str | None = None


class LinearColor(BaseModel):
    model_config = ConfigDict(extra='ignore')


class Lottery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: str
    name: str
    lotteryType: str


class StickerImage(BaseModel):
    model_config = ConfigDict(extra='ignore')


class Lottery1(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: str
    name: str
    lotteryType: str


class Lottery2(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: str
    name: str
    lotteryType: str


class LotteryCard(BaseModel):
    model_config = ConfigDict(extra='ignore')

    name: str
    lottery: Lottery2
    prizeTitle: str | None = None
    prizeSum: str | None = None
    prizeSubtitle: str | None = None
    prizeExtraInfo: str | None = None
    superPrize: str | None = None
    superPrizeInfo: str | None = None
    draw: str | None = None
    anyDraw: bool | None = None


class Content2(BaseModel):
    model_config = ConfigDict(extra='ignore')

    name: str | None = None
    lottery: Lottery | None = None
    prizeTitle: str | None = None
    prizeSum: str | None = None
    prizeSubtitle: str | None = None
    prizeExtraInfo: str | None = None
    superPrize: str | None = None
    superPrizeInfo: str | None = None
    draw: str | None = None
    anyDraw: bool | None = None
    link: str | None = None
    promoStartDate: str | None = None
    promoEndDate: str | None = None
    packetPriceInfo: str | None = None
    packetTitle: str | None = None
    packetSubtitle: str | None = None
    lotteries: list[Lottery1] | None = None
    lotteryCards: list[LotteryCard] | None = None


class Lottery3(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: str
    name: str
    lotteryType: str


class BannerImage(BaseModel):
    model_config = ConfigDict(extra='ignore')


class Packet(BaseModel):
    model_config = ConfigDict(extra='ignore')

    packetTitle: str
    packetSubtitle: str | None = None
    packetPriceInfo: str | None = None
    packetTeaser: str | None = None
    lotteries: list[Lottery3] = []


class SpecialGame(BaseModel):
    model_config = ConfigDict(extra='ignore')

    name: str
    prizeTitle: str
    prizeExtraInfo: str | None = None
    drawId: str | None = None
    prizeType: str | None = None


class Ticket(BaseModel):
    model_config = ConfigDict(extra='ignore')

    lotteryCode: str
    superprizeText: str | None = None
    ticketPriceInfo: str | None = None


class IntCard(BaseModel):
    model_config = ConfigDict(extra='ignore')

    link: str


class Item(BaseModel):
    model_config = ConfigDict(extra='ignore')

    spinners: list[Spinner] | None = None
    stories: list[Story] | None = None
    specialCards: list[SpecialCard] | None = None
    contents: list[Content2] | None = None
    packets: list[Packet] | None = None
    specialGames: list[SpecialGame] | None = None
    tickets: list[Ticket] | None = None
    intCards: list[IntCard] | None = None


class Ab(BaseModel):
    model_config = ConfigDict(extra='ignore')


class Content(BaseModel):
    model_config = ConfigDict(extra='ignore')

    item: Item
    ab: Ab


class Datum(BaseModel):
    model_config = ConfigDict(extra='ignore')

    contents: list[Content]


class MainCategoriesResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    data: list[Datum]
