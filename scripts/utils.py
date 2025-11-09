import json
import time
from typing import Any, Dict, Optional, Tuple
import requests
from urllib.parse import quote_plus

from . import config


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "X-Algolia-API-Key": config.ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": config.ALGOLIA_APP_ID,
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Mimic navigateur pour clés restreintes par origine
        "Origin": "https://www.aldi.be",
        "Referer": "https://www.aldi.be/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    })
    return s


def log_event(level: str, message: str, **kwargs: Any) -> None:
    data = {"level": level, "message": message, "timestamp": int(time.time())}
    if kwargs:
        data.update(kwargs)
    print(json.dumps(data, ensure_ascii=False))


RETRY_STATUS = {429} | set(range(500, 600))


def post_algolia_queries(session: requests.Session, body: Dict[str, Any], timeout: int = 15, max_retries: int = 4, backoff: float = 0.8) -> Dict[str, Any]:
    agent = quote_plus("Algolia for JavaScript (4.14.2); Browser; JS Helper (3.11.1); react (18.2.0); react-instantsearch (6.33.0)")
    url = f"{config.ALGOLIA_HOST}/1/indexes/*/queries?x-algolia-agent={agent}"
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = session.post(url, json=body, timeout=timeout)
            # Retry on 429/5xx
            if resp.status_code in RETRY_STATUS:
                raise requests.HTTPError(f"status={resp.status_code}")
            # Fail fast on non-2xx
            if not resp.ok:
                try:
                    err_body = resp.json()
                except Exception:
                    err_body = resp.text
                log_event("error", "algolia_http_error", status=resp.status_code, body=str(err_body))
                resp.raise_for_status()
            data = resp.json()
            # Basic schema validation: ensure 'results' present
            if "results" not in data:
                log_event("error", "algolia_unexpected_response", keys=list(data.keys()))
                raise RuntimeError("Unexpected Algolia response: missing 'results'")
            return data
        except Exception as e:
            last_err = e
            sleep = backoff * (2 ** attempt)
            log_event("warning", "algolia_request_retry", attempt=attempt + 1, sleep_seconds=sleep)
            time.sleep(sleep)
    raise RuntimeError(f"Algolia request failed after retries: {last_err}")


def get_first(d: Dict[str, Any], keys: Tuple[str, ...], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default