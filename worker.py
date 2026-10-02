import threading
from datetime import timedelta

import collector

from database import (
    update_collection_status
)


class CollectorWorker:

    def __init__(
        self,
        start_date,
        end_date,
        cid=""
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.cid = cid

        self.stop_event = threading.Event()
        self.thread = None

        self.total_days = (
            end_date - start_date
        ).days + 1

        self.completed_days = 0
        self.success_days = 0
        self.failed_days = 0
        self.found_rows = 0
        self.saved_rows = 0

        self.last_date = None

        self.running = False
        self.message = "대기 중"

    def start(self):

        if self.running:
            return

        self.stop_event.clear()

        self.thread = threading.Thread(
            target=self.run,
            daemon=True
        )

        self.thread.start()

    def stop(self):

        self.stop_event.set()

        self.message = "중지 요청"

    def progress(self):

        if self.total_days <= 0:
            return 0.0

        return min(
            self.completed_days /
            self.total_days,
            1.0
        )

    def run(self):

        self.running = True
        self.message = "수집 중"

        update_collection_status(
            start_date=
                self.start_date.isoformat(),
            end_date=
                self.end_date.isoformat(),
            running=True,
            completed=False,
            found=0,
            saved=0,
            failed=0
        )

        current = self.start_date

        while current <= self.end_date:

            if self.stop_event.is_set():

                self.running = False
                self.message = (
                    f"중단됨 "
                    f"(마지막 정상 날짜: "
                    f"{self.last_date or '없음'})"
                )

                update_collection_status(
                    last_date=self.last_date,
                    running=False,
                    completed=False,
                    found=self.found_rows,
                    saved=self.saved_rows,
                    failed=self.failed_days
                )

                return

            self.message = (
                f"{current.isoformat()} 수집 중"
            )

            result = collector.collect_day(
                current,
                self.cid
            )

            if result["success"]:

                self.success_days += 1

                self.found_rows += (
                    result["found"]
                )

                self.saved_rows += (
                    result["saved"]
                )

                self.last_date = (
                    current.isoformat()
                )

            else:

                self.failed_days += 1

            self.completed_days += 1

            update_collection_status(
                last_date=self.last_date,
                running=True,
                completed=False,
                found=self.found_rows,
                saved=self.saved_rows,
                failed=self.failed_days
            )

            current += timedelta(days=1)

        self.running = False
        self.message = (
            f"수집 완료 "
            f"(발견 {self.found_rows}, "
            f"저장 {self.saved_rows})"
        )

        update_collection_status(
            last_date=self.last_date,
            running=False,
            completed=True,
            found=self.found_rows,
            saved=self.saved_rows,
            failed=self.failed_days
        )
