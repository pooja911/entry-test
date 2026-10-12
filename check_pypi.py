#!/usr/bin/env python3
"""Check each line of a requirements file against PyPI.

Usage:
    python check_pypi.py requirements.txt

Reports:
  - dependencies checked (lines in the file)
  - packages not on PyPI
  - pinned versions (==x.y.z) not on PyPI
  - the oldest pinned release, by upload date
"""

import sys
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

PYPI_URL = "https://pypi.org/pypi/{name}/json"

LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)"   
    r"(?:\[[^\]]*\])?"                     
    r"\s*(?:==\s*([A-Za-z0-9._-]+))?"     
)


def parse_line(line):
    """Return (name, pinned_version_or_None), or None to skip the line."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        return None
    match = LINE_RE.match(stripped)
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_pypi(name, timeout=10):
    """Return parsed PyPI JSON for the package, or None if it doesn't exist."""
    url = PYPI_URL.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def release_date(data, version):
    """Earliest upload datetime for a version, or None if no files/not found."""
    files = data.get("releases", {}).get(version)
    if not files:
        return None
    times = []
    for f in files:
        ts = f.get("upload_time_iso_8601") or f.get("upload_time")
        if ts:
            times.append(ts.replace("Z", "+00:00"))
    if not times:
        return None
    return min(datetime.fromisoformat(t) for t in times)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <requirements-file>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"Could not open {path}: {e}", file=sys.stderr)
        sys.exit(1)

    total_lines = len(lines)
    checked = 0
    missing_packages = []     
    missing_versions = []      
    pinned_releases = []       

    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            continue
        name, version = parsed
        checked += 1

        try:
            data = fetch_pypi(name)
        except Exception as e:
            print(f"  ERROR   {name} ({e})", file=sys.stderr)
            missing_packages.append(name)
            continue

        if data is None:
            missing_packages.append(name)
            continue

        if version is not None:
            date = release_date(data, version)
            if date is None:
                missing_versions.append((name, version))
            else:
                pinned_releases.append((name, version, date))

    print(f"Dependencies checked (lines in file): {total_lines}")
    print(f"Dependencies parsed and checked:      {checked}")
    print()

    print(f"Packages not on PyPI ({len(missing_packages)}):")
    for name in missing_packages:
        print(f"  {name}")

    print()
    print(f"Pinned versions not on PyPI ({len(missing_versions)}):")
    for name, version in missing_versions:
        print(f"  {name}=={version}")

    print()
    if pinned_releases:
        name, version, date = min(pinned_releases, key=lambda r: r[2])
        print("Oldest pinned release:")
        print(f"  {name}=={version}  released {date.date()}")
    else:
        print("Oldest pinned release: none (no valid pinned versions found)")


if __name__ == "__main__":
    main()
