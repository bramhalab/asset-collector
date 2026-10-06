"""Daily entrypoint: run every source plugin, then push new files + manifest to HF in ONE commit."""
import os
import shutil
import sys
import traceback

from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download

HF_REPO = os.environ["HF_DATASET_REPO"]  # e.g. "Brand1809/video-edit-assets"
HF_TOKEN = os.environ["HF_TOKEN"]
MANIFEST_PATH = os.environ.get("MANIFEST_PATH", "manifest.jsonl")

SOURCES = [
    "source_commons",
    "source_openverse",
]


def pull_existing_manifest(api):
    """Create the dataset repo if needed, then pull the manifest so dedup works across days."""
    api.create_repo(HF_REPO, repo_type="dataset", private=True, exist_ok=True)
    try:
        path = hf_hub_download(
            repo_id=HF_REPO, filename=MANIFEST_PATH,
            repo_type="dataset", token=HF_TOKEN,
        )
        shutil.copy(path, MANIFEST_PATH)
        print("[run] pulled existing manifest from HF")
    except Exception as e:
        print(f"[run] no existing manifest found on HF ({e}), starting fresh")


def main():
    api = HfApi(token=HF_TOKEN)
    pull_existing_manifest(api)

    failures = []
    for mod_name in SOURCES:
        try:
            __import__(mod_name).run()
        except Exception as e:
            failures.append((mod_name, str(e)))
            print(f"[ERROR] {mod_name} failed: {e}")
            traceback.print_exc()

    # One atomic commit: files + manifest together, so the manifest never
    # claims a file that failed to upload.
    ops = []
    for root, _, files in os.walk("downloads"):
        for fn in files:
            local = os.path.join(root, fn)
            ops.append(CommitOperationAdd(
                path_in_repo=local.replace(os.sep, "/"), path_or_fileobj=local))
    if ops:
        ops.append(CommitOperationAdd(path_in_repo=MANIFEST_PATH, path_or_fileobj=MANIFEST_PATH))
        api.create_commit(
            repo_id=HF_REPO, repo_type="dataset", operations=ops,
            commit_message=f"Daily collect: {len(ops) - 1} new files",
        )
        print(f"[run] uploaded {len(ops) - 1} files + manifest")
    else:
        print("[run] nothing new to upload")

    if failures:
        print("\n=== SOURCES THAT FAILED ===")
        for name, err in failures:
            print(f"- {name}: {err}")
        sys.exit(1)  # fail loudly, don't pretend everything worked


if __name__ == "__main__":
    main()
