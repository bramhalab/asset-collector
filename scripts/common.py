"""Shared HTTP helpers: polite User-Agent, retries, size-capped downloads."""
import os
import re
import time

import requests

# Wikimedia (and good manners generally) want a descriptive User-Agent.
UA = os.environ.get(
    "COLLECTOR_UA",
    "asset-collector/1.0 (personal video-editing asset archive; python-requests)",
)

session = requests.Session()
session.headers.update({"User-Agent": UA})


class RateLimited(Exception):
    """Raised on HTTP 429 so a source can stop gracefully instead of crashing."""


def get_json(url, params=None, retries=3, timeout=30):
    last = None
    for attempt in range(retries):
        r = session.get(url, params=params, timeout=timeout)
        if r.status_code == 429:
            raise RateLimited(url)
        if r.status_code >= 500:
            last = r
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    last.raise_for_status()


def download(url, path, max_bytes):
    """Stream url to path. Returns False (and deletes the partial file) if it exceeds max_bytes."""
    too_big = False
    with session.get(url, stream=True, timeout=60) as r:
        if r.status_code == 429:
            raise RateLimited(url)
        r.raise_for_status()
        size = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                size += len(chunk)
                if size > max_bytes:
                    too_big = True
                    break
                f.write(chunk)
    if too_big:
        os.remove(path)
        return False
    return True


GENERIC_QUERIES = {"sound effect"}


def folder_for(query):
    """Search query -> safe subfolder name ('ui sound' -> 'ui_sound', generic -> 'general')."""
    q = query.strip().lower()
    if q in GENERIC_QUERIES:
        return "general"
    return re.sub(r"[^a-z0-9]+", "_", q).strip("_") or "general"
