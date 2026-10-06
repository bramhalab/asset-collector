"""Wikimedia Commons plugin -- B-roll video + sound effects. No API key needed.

Uses the public MediaWiki API (https://commons.wikimedia.org/w/api.php).
"""
import datetime
import os
import re
import time

from common import RateLimited, download, folder_for, get_json
from convert import normalize, probe
from licenses import commons_license_ok
from manifest import append_entry, load_seen_ids

API = "https://commons.wikimedia.org/w/api.php"
MB = 1024 * 1024

KINDS = [
    {
        "category": "broll", "filetype": "video", "mediatype": "VIDEO",
        "limit": int(os.environ.get("COMMONS_VIDEO_LIMIT", "5")),
        "queries": ["timelapse", "aerial view", "city traffic", "ocean waves",
                    "clouds sky", "forest nature", "waterfall", "sunset", "street night"],
        "out_dir": "downloads/broll", "target": "video_mp4",
        "max_bytes": 80 * MB, "max_duration": 120, "min_height": 720,
    },
    {
        "category": "sound_effects", "filetype": "audio", "mediatype": "AUDIO",
        "limit": int(os.environ.get("COMMONS_AUDIO_LIMIT", "10")),
        "queries": ["sound effect", "whoosh", "click", "impact", "ambience",
                    "explosion", "footsteps", "door", "rain", "wind"],
        "out_dir": "downloads/sound_effects", "target": "audio_mp3",
        "max_bytes": 15 * MB, "max_duration": 30, "min_height": 0,
    },
]
QUERIES_PER_RUN = 3
MAX_PAGES = 3


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _rotated(queries):
    """Different queries each day so results stay fresh."""
    start = datetime.date.today().toordinal() % len(queries)
    rot = queries[start:] + queries[:start]
    return rot[:QUERIES_PER_RUN]


def _search(kind, query):
    """Yield imageinfo records for one query, following API continuation."""
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"filetype:{kind['filetype']} {query}",
        "prop": "imageinfo",
        "iiprop": "url|size|mediatype|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|ObjectName",
    }
    for _ in range(MAX_PAGES):
        data = get_json(API, params=params)
        pages = data.get("query", {}).get("pages", [])
        for p in sorted(pages, key=lambda p: p.get("index", 0)):
            if p.get("imageinfo"):
                yield p["pageid"], p["title"], p["imageinfo"][0]
        if "continue" not in data:
            return
        params.update(data["continue"])
        time.sleep(1)


def _collect(kind, seen):
    fetched = errors = 0

    for query in _rotated(kind["queries"]):
        if fetched >= kind["limit"]:
            break
        qdir = os.path.join(kind["out_dir"], folder_for(query))
        os.makedirs(qdir, exist_ok=True)
        for pageid, title, info in _search(kind, query):
            if fetched >= kind["limit"]:
                break
            source_id = str(pageid)
            key = f"commons:{source_id}"
            if key in seen:
                continue
            if info.get("mediatype") != kind["mediatype"]:
                continue
            if (info.get("size") or 0) > kind["max_bytes"]:
                continue
            if (info.get("height") or 9999) < kind["min_height"]:
                continue
            dur = info.get("duration")
            if dur and dur > kind["max_duration"]:
                continue

            meta = info.get("extmetadata", {})
            lic_name = meta.get("LicenseShortName", {}).get("value", "")
            ok, attribution = commons_license_ok(lic_name)
            if not ok:
                continue

            ext = os.path.splitext(info["url"])[1].lower() or ".bin"
            tmp = os.path.join(qdir, f"{source_id}{ext}")
            final = None
            try:
                if not download(info["url"], tmp, kind["max_bytes"]):
                    continue
                final = normalize(tmp, qdir, kind["target"])
                pr = probe(final)
                if pr["duration"] and pr["duration"] > kind["max_duration"]:
                    os.remove(final)
                    continue
                res = f"{pr['width']}x{pr['height']}" if pr["width"] else None
                append_entry({
                    "source": "commons",
                    "source_id": source_id,
                    "category": kind["category"],
                    "license": lic_name,
                    "commercial_ok": True,
                    "attribution_required": attribution,
                    "creator": _strip_html(meta.get("Artist", {}).get("value")),
                    "source_url": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
                    "file_name": os.path.basename(final),
                    "path": os.path.relpath(final, "downloads").replace(os.sep, "/"),
                    "duration": pr["duration"],
                    "resolution": res,
                    "tags": [query],
                    "date": datetime.date.today().isoformat(),
                })
                seen.add(key)
                fetched += 1
                time.sleep(1)
            except RateLimited:
                raise
            except Exception as e:  # one bad file must not kill the whole source
                errors += 1
                print(f"[commons] skipped {title}: {e}")
                for p in (tmp, final):
                    if p and os.path.exists(p):
                        os.remove(p)
    return fetched, errors


def run():
    seen = load_seen_ids()
    total = total_err = 0
    for kind in KINDS:
        try:
            n, e = _collect(kind, seen)
        except RateLimited:
            print(f"[commons] rate limited on {kind['category']}, stopping this kind for today")
            continue
        print(f"[commons] {kind['category']}: fetched {n} new files ({e} errors)")
        total += n
        total_err += e
    if total == 0 and total_err > 0:
        raise RuntimeError(f"commons: 0 files fetched, {total_err} errors")


if __name__ == "__main__":
    run()
