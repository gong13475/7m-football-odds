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


    def start(self):

        with self.lock:

            if self.running:
                return False

            self.running = True
            self.finished = False
            self.stopped = False
            self.error = ""

            self.stop_event.clear()

            self.thread = threading.Thread(
                target=self.run,
                daemon=True
            )

            self.thread.start()

            return True


    def stop(self):

        self.stop_event.set()

        with self.lock:

            self.message = (
                "중지 요청 중..."
            )


    def progress(self):

        if self.total_days <= 0:
            return 0.0

        return min(
            self.completed_days
            / self.total_days,
            1.0
        )


    def run(self):

        current = self.start_date


        database.save_collection_state(
            start_date=self.start_date,
            end_date=self.end_date,
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

                    self.stopped = True

                    self.message = (
                        "수집 중지됨"
                    )

                    break


                self.message = (
                    f"{current} 수집 중"
                )


                result = self.retry.run(
                    collector.collect_day,
                    current,
                    self.cid
                )


                if result["success"]:

                    value = result["value"]


                    self.found_rows += int(
                        value.get(
                            "found",
                            0
                        )
                    )


                    self.saved_rows += int(
                        value.get(
                            "saved",
                            0
                        )
                    )


                    self.success_days += 1


                    database.add_log(
                        f"{current}: "
                        f"발견 "
                        f"{value.get('found', 0)}, "
                        f"신규 "
                        f"{value.get('saved', 0)}"
                    )


                else:

                    self.failed_days += 1


                    error = result["error"]


                    database.add_log(
                        f"{current}: "
                        f"재시도 실패 → 건너뛰기: "
                        f"{error}",
                        "ERROR"
                    )


                self.completed_days += 1

                self.last_completed_date = current


                database.save_collection_state(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    last_completed_date=current,
                    running=True,
                    stopped=False
                )


                current += timedelta(days=1)


            if self.stopped:

                self.message = (
                    "수집 중지됨"
                )

            else:

                self.message = (
                    "수집 완료"
                )


        except Exception as error:

            self.error = str(error)

            self.message = (
                "수집 오류"
            )


            database.add_log(
                f"Worker 오류: {error}",
                "ERROR"
            )


        finally:

            self.running = False
            self.finished = True


            database.save_collection_state(
                start_date=self.start_date,
                end_date=self.end_date,
                last_completed_date=self.last_completed_date,
                running=False,
                stopped=self.stopped
            )


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
