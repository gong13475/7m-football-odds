import time


class RetryManager:

    def __init__(
        self,
        retries=3,
        delay=1.0,
        backoff=2.0
    ):

        self.retries = max(
            1,
            int(retries)
        )

        self.delay = max(
            0.0,
            float(delay)
        )

        self.backoff = max(
            1.0,
            float(backoff)
        )


    def run(
        self,
        function,
        *args,
        **kwargs
    ):

        last_error = None

        current_delay = self.delay


        for attempt in range(
            1,
            self.retries + 1
        ):

            try:

                value = function(
                    *args,
                    **kwargs
                )


                return {

                    "success":
                        True,

                    "attempt":
                        attempt,

                    "value":
                        value,

                    "error":
                        None
                }


            except Exception as error:

                last_error = error


                if attempt >= self.retries:
                    break


                if current_delay > 0:

                    time.sleep(
                        current_delay
                    )

                    current_delay *= (
                        self.backoff
                    )


        return {

            "success":
                False,

            "attempt":
                self.retries,

            "value":
                None,

            "error":
                str(last_error)
        }
