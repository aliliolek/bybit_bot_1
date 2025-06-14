import time
from bybit_p2p._exceptions import FailedRequestError


def safe_call(func, max_retries=3, delay=1.0, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(**kwargs)
        except FailedRequestError as e:
            print(f"⚠️ Retry {attempt+1}/{max_retries} failed: {e}")
            time.sleep(delay)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break
    print("⛔️ All retries failed.")
    return None
