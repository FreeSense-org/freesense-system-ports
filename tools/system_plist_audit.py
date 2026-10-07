#!/usr/bin/env python3
"""Check that security/FreeSense-system/pkg-plist lists exactly the files the
FreeSense source tree installs (git-tracked files under src/).

The port installs src/etc and src/usr with COPYTREE_SHARE, and pkg packages only
what the plist names: a stale entry fails the package build ("Unable to access
file"), and a file missing from the plist is silently left out of the package.

usage: system_plist_audit.py --source <freesense checkout> [--plist <pkg-plist>]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

DATADIR = "usr/local/share/FreeSense/"


def plist_path(src_path):
    p = src_path[len("src/"):]
    if p.startswith(DATADIR):
        return "%%DATADIR%%/" + p[len(DATADIR):]
    if p.startswith("usr/local/"):
        return p[len("usr/local/"):]
    return "/" + p


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="path to a FreeSense-org/freesense checkout")
    ap.add_argument("--plist", default=str(here / "security/FreeSense-system/pkg-plist"))
    args = ap.parse_args()

    out = subprocess.run(["git", "-C", args.source, "ls-files", "-s", "src"],
                         capture_output=True, text=True, check=True).stdout
    expected = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        expected[plist_path(path)] = meta.split()[0]

    listed = {}
    for n, line in enumerate(Path(args.plist).read_text(encoding="utf-8").splitlines(), 1):
        if not line or (line.startswith("@") and not line.startswith("@(")):
            continue
        m = re.match(r"^(@\(([^)]*)\)\s+)?(.*)$", line)
        listed[m.group(3)] = (n, m.group(2) or "")

    errors = []
    for entry in sorted(set(listed) - set(expected)):
        errors.append(f"pkg-plist:{listed[entry][0]}: {entry} is listed but not in the source tree (the package build fails)")
    for entry in sorted(set(expected) - set(listed)):
        prefix = "@(,,755) " if expected[entry] == "100755" else ""
        errors.append(f"missing from pkg-plist: {prefix}{entry} (the file would be left out of the package)")
    warnings = []
    for entry in sorted(set(expected) & set(listed)):
        if expected[entry] == "100755" and "755" not in listed[entry][1]:
            warnings.append(f"warning: pkg-plist:{listed[entry][0]}: {entry} is executable in the source but installed 0644; "
                            f"consider @(,,755) {entry}")
    if warnings:
        print("\n".join(warnings), file=sys.stderr)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} pkg-plist problem(s)", file=sys.stderr)
        return 1
    print(f"pkg-plist matches the source tree ({len(expected)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
