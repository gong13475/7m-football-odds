import threading
from datetime import timedelta

import collector


class CollectorWorker:

    def __init__(self, start_date, end_date, cid=""):

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

        current = self.start_date

        try:

            while (
                current <= self.end_date
                and not self.stop_event.is_set()
            ):

                self.message = (
                    f"{current.isoformat()} 수집 중"
                )

                try:

                    result = collector.collect_day(
                        current,
                        self.cid
                    )

                    if not isinstance(
                        result,
                        dict
                    ):
                        result = {
                            "success": False,
                            "found": 0,
                            "saved": 0,
                            "error":
                                "잘못된 수집 결과"
                        }

                    if result.get(
                        "success",
                        False
                    ):

                        self.success_days += 1

                    else:

                        self.failed_days += 1

                    self.found_rows += int(
                        result.get(
                            "found",
                            0
                        )
                    )

                    self.saved_rows += int(
                        result.get(
                            "saved",
                            0
                        )
                    )

                    error = result.get(
                        "error"
                    )

                    if error:

                        self.message = (
                            f"{current.isoformat()} "
                            f"오류: {error}"
                        )

                except Exception as error:

                    self.failed_days += 1

                    self.message = (
                        f"{current.isoformat()} "
                        f"오류: {error}"
                    )

                self.completed_days += 1

                current += timedelta(
                    days=1
                )

            if self.stop_event.is_set():

                self.message = "사용자에 의해 중지됨"

            else:

                self.message = (
                    f"수집 완료 "
                    f"(발견 {self.found_rows}, "
                    f"저장 {self.saved_rows})"
                )

        except Exception as error:

            self.message = (
                f"Worker 오류: {error}"
            )

        finally:

            self.running = False
