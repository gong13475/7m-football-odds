# worker.py

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

        self.cid = (
            str(cid).strip()
            if cid
            else ""
        )

        self.retry = RetryManager(
            retries=int(retries),
            delay=float(delay),
            backoff=2.0
        )

        self.stop_event = (
            threading.Event()
        )

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

            self.message = (
                "수집 준비 중"
            )

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

        with self.lock:

            value = (
                self.completed_days
                / self.total_days
            )

        return min(
            max(value, 0.0),
            1.0
        )


    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        current = self.start_date

        database.save_collection_state(
            start_date=
                self.start_date,
            end_date=
                self.end_date,
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

                # ------------------------------------------------
                # STOP
                # ------------------------------------------------

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


                # ------------------------------------------------
                # ONE DAY
                # ------------------------------------------------

                result = self.retry.run(
                    collector.collect_day,
                    current,
                    self.cid
                )


                # ------------------------------------------------
                # RESULT
                # ------------------------------------------------

                if result["success"]:

                    value = result["value"]

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

                        self.found_rows += (
                            found
                        )

                        self.saved_rows += (
                            saved
                        )

                        self.success_days += 1


                    database.add_log(
                        f"{current}: "
                        f"발견 {found}, "
                        f"신규 {saved}"
                    )

                else:

                    error = str(
                        result.get(
                            "error",
                            "알 수 없는 오류"
                        )
                    )

                    with self.lock:

                        self.failed_days += 1


                    database.add_log(
                        f"{current}: "
                        f"재시도 실패 → "
                        f"건너뛰기: "
                        f"{error}",
                        "ERROR"
                    )


                # ------------------------------------------------
                # COMPLETE DAY
                # ------------------------------------------------

                with self.lock:

                    self.completed_days += 1

                    self.last_completed_date = (
                        current
                    )


                database.save_collection_state(
                    start_date=
                        self.start_date,
                    end_date=
                        self.end_date,
                    last_completed_date=
                        current,
                    running=True,
                    stopped=False
                )


                current += timedelta(
                    days=1
                )


            # ----------------------------------------------------
            # FINAL STATUS
            # ----------------------------------------------------

            with self.lock:

                if self.stopped:

                    self.message = (
                        "수집 중지됨"
                    )

                else:

                    self.message = (
                        "수집 완료"
                    )


        except Exception as error:

            error_text = str(error)

            with self.lock:

                self.error = error_text

                self.message = (
                    "수집 오류"
                )


            database.add_log(
                f"Worker 오류: "
                f"{error_text}",
                "ERROR"
            )


        finally:

            with self.lock:

                self.running = False

                self.finished = True


                stopped = self.stopped

                last_completed = (
                    self.last_completed_date
                )


            database.save_collection_state(
                start_date=
                    self.start_date,
                end_date=
                    self.end_date,
                last_completed_date=
                    last_completed,
                running=False,
                stopped=stopped
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
