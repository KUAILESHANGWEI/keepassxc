#!/usr/bin/env python3
"""Rewrite KeePassXC upstream download/update links to this isolated mirror."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import unquote


TEXT_EXTENSIONS = {
    ".1",
    ".bat",
    ".cmake",
    ".conf",
    ".cpp",
    ".css",
    ".desktop",
    ".hpp",
    ".h",
    ".in",
    ".ini",
    ".json",
    ".md",
    ".nsi",
    ".plist",
    ".po",
    ".pri",
    ".pro",
    ".ps1",
    ".py",
    ".qml",
    ".qrc",
    ".rst",
    ".sh",
    ".txt",
    ".xml",
    ".yml",
    ".yaml",
}

SKIP_DIRS = {
    ".git",
    ".github",  # workflow files intentionally keep the upstream source URL.
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
}


def is_text_file(path: Path) -> bool:
    if path.name in {"CMakeLists.txt", "Dockerfile", "PKGBUILD"}:
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in sample


def safe_asset_name(owner: str, repo: str, tag: str, asset: str) -> str:
    asset_name = unquote(asset.rsplit("/", 1)[-1])
    raw = f"{owner}-{repo}-{tag}-{asset_name}"
    return re.sub(r"[^A-Za-z0-9._+-]+", "-", raw).strip("-")


def rewrite_text(text: str, args: argparse.Namespace, third_party: dict[str, str]) -> str:
    upstream = f"{args.upstream_owner}/{args.upstream_repo}"
    target = f"{args.target_owner}/{args.target_repo}"

    replacements = [
        (f"git@github.com:{upstream}.git", f"git@github.com:{target}.git"),
        (f"https://github.com/{upstream}.git", f"https://github.com/{target}.git"),
        (f"https://github.com/{upstream}", f"https://github.com/{target}"),
        (f"http://github.com/{upstream}", f"https://github.com/{target}"),
        (f"github.com/{upstream}", f"github.com/{target}"),
        (
            f"https://raw.githubusercontent.com/{upstream}",
            f"https://raw.githubusercontent.com/{target}",
        ),
        (f"raw.githubusercontent.com/{upstream}", f"raw.githubusercontent.com/{target}"),
        (
            f"https://cdn.jsdelivr.net/gh/{upstream}",
            f"https://raw.githubusercontent.com/{target}",
        ),
        (f"cdn.jsdelivr.net/gh/{upstream}", f"raw.githubusercontent.com/{target}"),
        (upstream, target),
        ("https://github.com/KUAILESHANGWEI/keepassxc/releases/latest/", f"https://github.com/{target}/releases/latest/"),
        ("https://github.com/KUAILESHANGWEI/keepassxc/releases/latest", f"https://github.com/{target}/releases/latest"),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    release_url = re.compile(
        r"https://github\.com/"
        r"(?P<owner>[^/\s\"'<>]+)/(?P<repo>[^/\s\"'<>]+)"
        r"/releases/download/(?P<tag>[^/\s\"'<>]+)/(?P<asset>[^)\]\s\"'<>]+)"
    )

    def replace_release(match: re.Match[str]) -> str:
        owner = match.group("owner")
        repo = match.group("repo")
        if f"{owner}/{repo}" == target:
            return match.group(0)
        if f"{owner}/{repo}" == upstream:
            return match.group(0).replace(
                f"https://github.com/{upstream}", f"https://github.com/{target}"
            )
        tag = match.group("tag")
        asset = match.group("asset")
        mirrored_asset = safe_asset_name(owner, repo, tag, asset)
        source = match.group(0)
        mirror = f"https://github.com/{target}/releases/download/third-party-assets/{mirrored_asset}"
        third_party[source] = mirror
        return mirror

    return release_url.sub(replace_release, text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-owner", required=True)
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--upstream-owner", required=True)
    parser.add_argument("--upstream-repo", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    changed: list[str] = []
    third_party: dict[str, str] = {}

    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            path = Path(current_root) / filename
            if not is_text_file(path):
                continue
            try:
                original = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    original = path.read_text(encoding="latin-1")
                except UnicodeDecodeError:
                    continue
            updated = rewrite_text(original, args, third_party)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed.append(str(path.relative_to(root)))

    manifest = root / ".github" / "third-party-release-assets.tsv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if third_party:
        rows = ["source_url\tmirror_url"]
        rows.extend(f"{src}\t{dst}" for src, dst in sorted(third_party.items()))
        manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
        changed.append(str(manifest.relative_to(root)))
    elif manifest.exists():
        manifest.unlink()

    print(f"Localized {len(changed)} files")
    for item in changed:
        print(f" - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
