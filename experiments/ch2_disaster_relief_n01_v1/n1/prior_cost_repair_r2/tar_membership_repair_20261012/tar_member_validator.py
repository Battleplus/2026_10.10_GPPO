"""Offline checker matching the deployment tar-member validation rules."""

from __future__ import annotations

import argparse
import json
import pathlib
import tarfile


def validate_members(members: list[tarfile.TarInfo]) -> dict[str, tarfile.TarInfo]:
    kinds: dict[str, str] = {}
    by_name: dict[str, tarfile.TarInfo] = {}
    seen: set[str] = set()
    for member in members:
        raw = member.name
        if not raw or "\x00" in raw or "\\" in raw or raw.startswith("/"):
            raise ValueError(f"unsafe member name: {raw!r}")
        name = raw[:-1] if member.isdir() and raw.endswith("/") else raw
        parts = name.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"non-canonical member path: {raw!r}")
        if name != "package" and not name.startswith("package/"):
            raise ValueError(f"member outside package root: {raw!r}")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"unsupported member type: {raw!r}")
        if name in seen:
            raise ValueError(f"duplicate member: {name!r}")
        seen.add(name)
        kinds[name] = "dir" if member.isdir() else "file"
        by_name[name] = member

    if kinds.get("package") != "dir":
        raise ValueError("package root directory missing")
    for name in seen:
        parts = name.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            if kinds.get(parent) == "file":
                raise ValueError(f"file is parent of another member: {parent!r}")
    return by_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=pathlib.Path)
    args = parser.parse_args()
    with tarfile.open(args.archive, "r:gz") as tar:
        members = tar.getmembers()
        validate_members(members)
        file_count = sum(member.isfile() for member in members)
        directory_count = sum(member.isdir() for member in members)
        if (len(members), file_count, directory_count) != (594, 560, 34):
            raise ValueError("archive member counts do not match frozen package")
    print(json.dumps({
        "status": "archive-members-valid",
        "member_count": len(members),
        "file_count": file_count,
        "directory_count": directory_count,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
