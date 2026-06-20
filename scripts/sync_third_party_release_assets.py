#!/usr/bin/env python3
"""Mirror hardcoded third-party GitHub Release assets into this repository."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: sync_third_party_release_assets.py MANIFEST TARGET_REPO", file=sys.stderr)
        return 2

    manifest = Path(sys.argv[1])
    target_repo = sys.argv[2]
    if not manifest.exists():
        print("No third-party release asset manifest found.")
        return 0

    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    if not rows:
        print("Third-party release asset manifest is empty.")
        return 0

    release_exists = subprocess.run(
        ["gh", "release", "view", "third-party-assets", "--repo", target_repo],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not release_exists:
        run(
            [
                "gh",
                "release",
                "create",
                "third-party-assets",
                "--repo",
                target_repo,
                "--title",
                "Mirrored third-party release assets",
                "--notes",
                "Assets mirrored from hardcoded third-party GitHub Release URLs used by this project.",
            ]
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for row in rows:
            source_url = row["source_url"]
            mirror_url = row["mirror_url"]
            asset_name = mirror_url.rsplit("/", 1)[-1]
            asset_path = tmp / asset_name
            print(f"Downloading {source_url}")
            with urlopen(source_url, timeout=120) as response:
                asset_path.write_bytes(response.read())
            run(["gh", "release", "upload", "third-party-assets", str(asset_path), "--repo", target_repo, "--clobber"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
