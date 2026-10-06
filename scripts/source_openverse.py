"""Openverse plugin -- sound effects (aggregates Freesound, Jamendo, Wikimedia etc.).

Anonymous access works with no key, but the anonymous rate limit is low, so this
plugin uses few requests and stops quietly on HTTP 429.
"""
import datetime
import os
import time

from common import RateLimited, download, folder_for, get_json
from convert import normalize, probe
from licenses import OPENVERSE_OK
from manifest import append_entry, load_seen_ids

API = "https://api.openverse.org/v1/audio/"
LIMIT = int(os.environ.get("OPENVERSE_DAILY_LIMIT", "10"))
QUERIES = ["whoosh", "transition", "impact", "riser", "click", "ui sound",
           "swoosh", "notification", "ambience", "foley"]
QUERIES_PER_RUN = 2
MAX_PAGES = 2
MAX_SECONDS = 30
MAX_BYTES = 15 * 1024 * 1024
OUT_DIR = "downloads/sound_effects"


def run():
    seen = load_seen_ids()
    fetched = errors = 0

    start = datetime.date.today().toordinal() % len(QUERIES)
    queries = (QUERIES[start:] + QUERIES[:start])[:QUERIES_PER_RUN]

    try:
        for q in queries:
            qdir = os.path.join(OUT_DIR, folder_for(q))
            os.makedirs(qdir, exist_ok=True)
            for page in range(1, MAX_PAGES + 1):
                if fetched >= LIMIT:
                    break
                data = get_json(API, params={
                    "q": q, "license": "cc0,pdm,by",
                    "page_size": 20, "page": page,
                })
                for item in data.get("results", []):
                    if fetched >= LIMIT:
                        break
                    source_id = str(item["id"])
                    key = f"openverse:{source_id}"
                    if key in seen:
                        continue
                    lic = (item.get("license") or "").lower()
                    if lic not in OPENVERSE_OK:
                        continue
                    secs = (item.get("duration") or 0) / 1000
                    if secs <= 0 or secs > MAX_SECONDS:
                        continue
                    url = item.get("url")
                    if not url:
                        continue

                    ext = "." + (item.get("filetype") or os.path.splitext(url)[1].lstrip(".") or "mp3")
                    tmp = os.path.join(qdir, f"ov_{source_id}{ext.lower()}")
                    final = None
                    try:
                        if not download(url, tmp, MAX_BYTES):
                            continue
                        final = normalize(tmp, qdir, "audio_mp3")
                        pr = probe(final)
                        append_entry({
                            "source": "openverse",
                            "source_id": source_id,
                            "category": "sound_effects",
                            "license": (("CC " if lic != "pdm" else "") + lic.upper() + " " + (item.get("license_version") or "")).strip(),
                            "commercial_ok": True,
                            "attribution_required": OPENVERSE_OK[lic],
                            "creator": item.get("creator"),
                            "source_url": item.get("foreign_landing_url"),
                            "file_name": os.path.basename(final),
                            "path": os.path.relpath(final, "downloads").replace(os.sep, "/"),
                            "duration": pr["duration"] or secs,
                            "resolution": None,
                            "tags": [t.get("name") for t in item.get("tags", []) if t.get("name")] or [q],
                            "date": datetime.date.today().isoformat(),
                        })
                        seen.add(key)
                        fetched += 1
                        time.sleep(1)
                    except RateLimited:
                        raise
                    except Exception as e:
                        errors += 1
                        print(f"[openverse] skipped {source_id}: {e}")
                        for p in (tmp, final):
                            if p and os.path.exists(p):
                                os.remove(p)
    except RateLimited:
        print("[openverse] rate limited (anonymous limit), stopping for today")

    print(f"[openverse] fetched {fetched} new files ({errors} errors)")
    if fetched == 0 and errors > 0:
        raise RuntimeError(f"openverse: 0 files fetched, {errors} errors")


if __name__ == "__main__":
    run()
