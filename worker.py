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
