import logging
import time
import requests

logger = logging.getLogger("llmops")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

def http_post_with_retry(url, json_payload, headers=None, retries=3, backoff=2):
    last = None
    for i in range(retries):
        try:
            r = requests.post(url, json=json_payload, headers=headers, timeout=10)
            if r.status_code < 500:
                return r
        except Exception as e:
            last = e
        time.sleep(backoff ** i)
    if last:
        raise last
    return None
