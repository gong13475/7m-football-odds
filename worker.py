import time
from datetime import date, timedelta

from retry_manager import run_with_retry


class CollectionWorker:

    def __init__(self):
        self.running = False
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0

    def start(
        self,
        start_date: date,
        end_date: date,
        companies: list
    ):
        self.running = True

        current = start_date

        while self.running and current <= end_date:

            for company in companies:

                if not self.running:
                    break

                success, result, error = run_with_retry(
                    lambda: self.collect_day(
                        current,
                        company
                    ),
                    max_retries=3
                )

                self.total += 1

                if success:
                    self.success += 1
                else:
                    self.failed += 1
                    self.skipped += 1

            current += timedelta(days=1)

    def stop(self):
        self.running = False

    def collect_day(
        self,
        target_date: date,
        company: str
    ):
        """
        실제 7M 데이터 수집 모듈을 연결하는 부분입니다.

        현재는 임의의 데이터를 생성하지 않습니다.
        실제 허용된 데이터 소스 연결 후 이 함수에서
        최종배당 자료를 반환하도록 연결합니다.
        """

        raise NotImplementedError(
            "실제 데이터 소스 연결이 필요합니다."
        )


if __name__ == "__main__":
    worker = CollectionWorker()

    worker.start(
        date(2010, 1, 1),
        date(2010, 1, 2),
        ["10Bet"]
    )
