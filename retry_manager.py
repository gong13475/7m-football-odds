import time
from typing import Callable, Any


MAX_RETRIES = 3


def run_with_retry(
    task: Callable[[], Any],
    max_retries: int = MAX_RETRIES,
    delay_seconds: float = 2.0
):
    """
    작업 실패 시 최대 3회까지 재시도합니다.

    성공:
        (True, 결과, None)

    계속 실패:
        (False, None, 마지막 오류)
    """

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            result = task()

            return True, result, None

        except Exception as error:
            last_error = error

            if attempt < max_retries:
                time.sleep(delay_seconds * attempt)

    return False, None, last_error
