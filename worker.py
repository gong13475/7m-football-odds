import threading

from datetime import timedelta

import collector
import database

from retry_manager import RetryManager


class CollectorWorker:

    def __init__(
        self,
        start_date,
        end_date,
        cid="",
        retries=3,
        delay=1.0
    ):

        self.start_date = start_date
        self.end_date = end_date
        self.cid = cid

        self.retry = RetryManager(
            retries=retries,
            delay=delay,
            backoff=2.0
        )

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

        self.last_completed_date = None

        self.running = False
        self.finished = False
        self.stopped = False

        self.message = "대기 중"

        self.error = ""

        self.lock = threading.RLock()


    # ========================================================
    # START
    # ========================================================

    def start(self):

        with self.lock:

            if self.running:
                return False

            self.running = True
            self.finished = False
            self.stopped = False
            self.error = ""
            self.message = "수집 준비 중"

            self.stop_event.clear()

            self.thread = threading.Thread(
                target=self.run,
                daemon=True
            )

            self.thread.start()

            return True


    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        self.stop_event.set()

        with self.lock:

            self.message = (
                "중지 요청 중..."
            )


    # ========================================================
    # PROGRESS
    # ========================================================

    def progress(self):

        if self.total_days <= 0:
            return 0.0

        return min(
            self.completed_days
            / self.total_days,
            1.0
        )


    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        current = self.start_date

        database.save_collection_state(
            start_date=self.start_date,
            end_date=self.end_date,
            last_completed_date=None,
            running=True,
            stopped=False
        )

        database.add_log(
            f"수집 시작: "
            f"{self.start_date} ~ "
            f"{self.end_date}"
        )

        try:

            while current <= self.end_date:

                if self.stop_event.is_set():

                    with self.lock:

                        self.stopped = True

                        self.message = (
                            "수집 중지됨"
                        )

                    break

                with self.lock:

                    self.message = (
                        f"{current} 수집 중"
                    )

                try:

                    result = self.retry.run(
                        collector.collect_day,
                        current,
                        self.cid
                    )

                    if not result.get(
                        "success",
                        False
                    ):

                        raise RuntimeError(
                            result.get(
                                "error",
                                "수집 실패"
                            )
                        )

                    value = result.get(
                        "value",
                        {}
                    )

                    found = int(
                        value.get(
                            "found",
                            0
                        )
                    )

                    saved = int(
                        value.get(
                            "saved",
                            0
                        )
                    )

                    with self.lock:

                        self.found_rows += found
                        self.saved_rows += saved
                        self.success_days += 1

                    database.add_log(
                        f"{current}: "
                        f"발견 {found}, "
                        f"신규 {saved}"
                    )

                except Exception as exc:

                    with self.lock:

                        self.failed_days += 1

                    database.add_log(
                        f"{current}: "
                        f"최종 실패 → 건너뛰기: "
                        f"{exc}",
                        "ERROR"
                    )

                with self.lock:

                    self.completed_days += 1

                    self.last_completed_date = (
                        current
                    )

                database.save_collection_state(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    last_completed_date=current,
                    running=True,
                    stopped=False
                )

                current += timedelta(
                    days=1
                )

            with self.lock:

                if self.stopped:

                    self.message = (
                        "수집 중지됨"
                    )

                else:

                    self.message = (
                        "수집 완료"
                    )

        except Exception as exc:

            with self.lock:

                self.error = str(exc)

                self.message = (
                    "수집 오류"
                )

            database.add_log(
                f"Worker 오류: {exc}",
                "ERROR"
            )

        finally:

            with self.lock:

                self.running = False
                self.finished = True

            database.save_collection_state(
                start_date=self.start_date,
                end_date=self.end_date,
                last_completed_date=
                    self.last_completed_date,
                running=False,
                stopped=self.stopped
            )


    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        with self.lock:

            return {

                "running":
                    self.running,

                "finished":
                    self.finished,

                "stopped":
                    self.stopped,

                "total_days":
                    self.total_days,

                "completed_days":
                    self.completed_days,

                "success_days":
                    self.success_days,

                "failed_days":
                    self.failed_days,

                "found_rows":
                    self.found_rows,

                "saved_rows":
                    self.saved_rows,

                "last_completed_date":
                    self.last_completed_date,

                "progress":
                    self.progress(),

                "message":
                    self.message,

                "error":
                    self.error
            }
