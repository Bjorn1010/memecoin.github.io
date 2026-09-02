"""Small, dependency-light HTTP helper with retries and an on-disk cache.

Every data source in this project is a free, keyless public endpoint. That means
rate limits are real and unforgiving, so we (a) back off exponentially, (b) cache
immutable archive files on disk forever, and (c) never hammer an endpoint in a loop
without a floor on the gap between calls.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

import requests

from ..config import CONFIG


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int, body: str = "") -> None:
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.url = url
        self.status = status


_session: requests.Session | None = None
_last_call: dict[str, float] = {}


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": CONFIG.user_agent, "Accept-Encoding": "gzip, deflate"})
        _session = s
    return _session


def _throttle(host: str, min_gap: float) -> None:
    if min_gap <= 0:
        return
    prev = _last_call.get(host)
    now = time.monotonic()
    if prev is not None:
        wait = min_gap - (now - prev)
        if wait > 0:
            time.sleep(wait)
    _last_call[host] = time.monotonic()


def request(
    method: str,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    json_body: Any | None = None,
    min_gap: float = 0.25,
    retries: int | None = None,
    allow_status: tuple[int, ...] = (),
) -> requests.Response:
    """Perform a request, retrying transient failures with exponential backoff.

    `allow_status` lists non-2xx codes the caller handles itself (typically 404,
    which for an archive simply means "that month does not exist").
    """
    retries = CONFIG.http_retries if retries is None else retries
    host = url.split("/")[2] if "//" in url else url
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        _throttle(host, min_gap)
        try:
            resp = session().request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=CONFIG.http_timeout,
            )
        except requests.RequestException as exc:  # network-level failure
            last_exc = exc
        else:
            if resp.status_code < 400 or resp.status_code in allow_status:
                return resp
            # 429/5xx are worth retrying; 4xx (other than allowed) are not.
            if resp.status_code != 429 and resp.status_code < 500:
                raise HttpError(url, resp.status_code, resp.text)
            last_exc = HttpError(url, resp.status_code, resp.text)

        if attempt < retries:
            time.sleep(min(2**attempt, 30) + 0.25 * attempt)

    raise last_exc if last_exc else HttpError(url, 0, "exhausted retries")


def get_json(url: str, *, params: Mapping[str, Any] | None = None, min_gap: float = 0.25) -> Any:
    return request("GET", url, params=params, min_gap=min_gap).json()


def post_json(url: str, body: Any, *, min_gap: float = 0.25) -> Any:
    return request("POST", url, json_body=body, min_gap=min_gap).json()


def get_text(url: str, *, params: Mapping[str, Any] | None = None, min_gap: float = 0.25) -> str:
    return request("GET", url, params=params, min_gap=min_gap).text


def cached_download(url: str, *, subdir: str = "http", min_gap: float = 0.1) -> Path | None:
    """Download `url` into the cache and return the local path.

    Archive files are content-immutable, so a cache hit skips the network entirely.
    Returns None on 404 — a normal, expected outcome when probing which months of an
    archive exist.
    """
    CONFIG.ensure_dirs()
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    name = url.rsplit("/", 1)[-1]
    dest_dir = CONFIG.cache_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{key}-{name}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    resp = request("GET", url, min_gap=min_gap, allow_status=(403, 404))
    if resp.status_code in (403, 404):
        return None
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)
    return dest


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
