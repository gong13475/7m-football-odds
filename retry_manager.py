import time


def retry(
    function,
    attempts=3,
    delay=2
):
    last_error = None

    for attempt in range(attempts):

        try:
            return True, function()

        except Exception as error:

            last_error = error

            if attempt < attempts - 1:
                time.sleep(delay)

    return False, last_error
