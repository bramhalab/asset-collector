# Video Editing Asset Collector (no API keys)

Daily GitHub Actions job that pulls new sound effects (MP3) and B-roll
video (MP4) from **open-licence sources that need no API key**, dedupes
against a manifest, and pushes everything to a Hugging Face dataset.

Sources:
- **Wikimedia Commons** (public MediaWiki API) -> B-roll video + sound effects
- **Openverse** (anonymous API) -> sound effects (aggregates Freesound, Jamendo, etc.)

Only CC0 / Public Domain / CC BY are kept. NC, ND, SA and unknown licences
are skipped. CC BY items have `attribution_required: true` plus `creator`
and `source_url` in the manifest, so you know whom to credit.

## Setup (only Hugging Face is needed)

1. Hugging Face -> Settings -> Access Tokens -> create a token with **Write** access.
2. Create a GitHub repo and push this folder to it.
3. GitHub repo -> Settings -> Secrets and variables -> Actions:
   - **Secret**: `HF_TOKEN` = your HF write token
   - **Variable**: `HF_DATASET_REPO` = `yourname/video-edit-assets`
     (the dataset repo is auto-created as private if it doesn't exist)
4. Actions tab -> "Daily Asset Collection" -> **Run workflow** to test.
   After that it runs daily at 21:00 UTC (2:30 AM IST).

## Folder layout on Hugging Face

```
downloads/
  broll/<query>/<id>.mp4            e.g. broll/timelapse/12345.mp4
  sound_effects/<query>/<id>.mp3    e.g. sound_effects/whoosh/67890.mp3
manifest.jsonl                      (each entry has a `path` field)
```
Generic queries (e.g. "sound effect") go into `general/`. A file lives in
exactly one folder (dedupe is by ID).

## How it works

- `run.py` pulls `manifest.jsonl` from HF, runs each `source_*.py` plugin,
  then uploads new files + manifest in ONE commit.
- Plugins rotate their search queries daily, skip already-seen IDs, filter
  by licence/size/duration, convert via ffmpeg (video -> MP4 max 1920px wide,
  audio -> MP3).
- If a plugin crashes, other sources still run and the job ends red.
  Rate-limit (HTTP 429) is treated as a soft stop, not a failure.

## Env knobs (optional, in the workflow `env:`)

`COMMONS_VIDEO_LIMIT` (5), `COMMONS_AUDIO_LIMIT` (10), `OPENVERSE_DAILY_LIMIT` (10)

## Adding a new source

Copy `source_commons.py`, point at the new API, keep the same manifest
entry shape, add the module name to `SOURCES` in `run.py`.
