from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class OddsRecord:
    match_key: str
    match_date: str
    bookmaker: str

    home_odds: float
    draw_odds: float
    away_odds: float

    result: Optional[str] = None


class SevenMOddsCollector:
    """
    7M 실제 데이터 연결용 수집기.

    주의:
    실제로 접근이 허용된 데이터 소스/API가 연결되기 전에는
    임의의 배당 데이터를 생성하지 않습니다.
    """

    def __init__(self):
        self.running = False

    def stop(self):
        self.running = False

    def collect(
        self,
        target_date: date,
        bookmaker: str
    ):
        """
        target_date의 축구 최종배당을 가져옵니다.

        반환:
            OddsRecord 리스트

        실제 7M 데이터 접근 방식이 확인되면
        이 부분에 연결합니다.
        """

        self.running = True

        raise NotImplementedError(
            "실제 7M 데이터 소스를 연결해야 합니다."
        )


def validate_record(record: OddsRecord) -> bool:
    """
    저장 전에 데이터가 정상적인지 검사합니다.
    """

    if not record.match_key:
        return False

    if not record.match_date:
        return False

    if not record.bookmaker:
        return False

    odds = (
        record.home_odds,
        record.draw_odds,
        record.away_odds
    )

    if any(value <= 1.0 for value in odds):
        return False

    if record.result not in (None, "H", "D", "A"):
        return False

    return True
