"""Dedup manifest: tracks every asset already fetched so we never re-download it."""
import json
import os

MANIFEST_PATH = os.environ.get("MANIFEST_PATH", "manifest.jsonl")


def load_seen_ids():
    """Return a set of 'source:source_id' strings already recorded."""
    seen = set()
    if not os.path.exists(MANIFEST_PATH):
        return seen
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                seen.add(f"{entry['source']}:{entry['source_id']}")
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def append_entry(entry: dict):
    """Append one manifest record. Required keys:
    source, source_id, category, license, commercial_ok,
    file_name, duration, resolution, tags, date
    Extra keys used here: creator, source_url, attribution_required
    """
    with open(MANIFEST_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
