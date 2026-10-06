"""Licence filter: keep only what is safe to drop into a monetised video.

Allowed: CC0, Public Domain, CC BY (attribution needed -> stored in manifest).
Rejected: NC (non-commercial), ND (no derivatives), SA (share-alike), unknown.
"""
import re


def commons_license_ok(short_name: str):
    """Returns (ok, attribution_required) for a Wikimedia Commons LicenseShortName."""
    tokens = [t for t in re.split(r"[\s\-_/]+", (short_name or "").lower()) if t]
    if not tokens:
        return False, False
    if "cc0" in tokens or "pd" in tokens or ("public" in tokens and "domain" in tokens):
        return True, False
    if tokens[:2] == ["cc", "by"] and not ({"nc", "nd", "sa"} & set(tokens)):
        return True, True
    return False, False


OPENVERSE_OK = {"cc0": False, "pdm": False, "by": True}  # value = attribution required
