#!/usr/bin/env python3
"""Check security/FreeSense-webui against the freesense-webui commit it pins.

The port installs a committed freesense-webui tree (dist/ is built there), so
the pinned archive decides what the package contains. This audit downloads
that archive (or reads --archive), checks it against distinfo, and checks
that pkg-plist lists exactly what do-install copies:

  app/public/index.php                  -> www-ui/index.php
  dist/public/{ui,themes}/**            -> www-ui/{ui,themes}/**
  app/{bootstrap.php,nav.json,pages.php,src/**,pages/**,templates/**}
                                        -> %%DATADIR%%/app/...
  LICENSE, NOTICE                       -> %%DATADIR%%/

freesense-webui's `npm run port` writes the same three files from the same
rules.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "security" / "FreeSense-webui"
APP_FILES = ("bootstrap.php", "nav.json", "pages.php")
APP_DIRS = ("src/", "pages/", "templates/")


def makefile_vars(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"^([A-Z_]+)=\s*(.*)$", text, re.M)}


def expected_plist(names: list[str]) -> list[str]:
    out = []
    for name in names:
        if name == "app/public/index.php":
            out.append("www-ui/index.php")
        elif name.startswith(("dist/public/ui/", "dist/public/themes/")):
            out.append("www-ui/" + name[len("dist/public/"):])
        elif name.startswith("app/") and (name[4:] in APP_FILES or name[4:].startswith(APP_DIRS)):
            out.append("%%DATADIR%%/" + name)
        elif name in ("LICENSE", "NOTICE"):
            out.append("%%DATADIR%%/" + name)
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", type=Path, help="the pinned archive (default: download it from GitHub)")
    args = parser.parse_args()

    make = makefile_vars((PORT / "Makefile").read_text())
    tag = make.get("GH_TAGNAME", "")
    if not re.fullmatch(r"[0-9a-f]{40}", tag):
        print("FreeSense-webui: GH_TAGNAME must be a full freesense-webui commit hash", file=sys.stderr)
        return 1
    distfile = f"{make['GH_ACCOUNT']}-{make['GH_PROJECT']}-{tag}_GH0.tar.gz"
    distinfo = (PORT / "distinfo").read_text()
    want_sha = re.search(rf"^SHA256 \({re.escape(distfile)}\) = ([0-9a-f]{{64}})$", distinfo, re.M)
    want_size = re.search(rf"^SIZE \({re.escape(distfile)}\) = (\d+)$", distinfo, re.M)
    if not (want_sha and want_size):
        print(f"FreeSense-webui: distinfo has no SHA256/SIZE for {distfile}", file=sys.stderr)
        return 1

    if args.archive:
        data = args.archive.read_bytes()
    else:
        url = f"https://codeload.github.com/{make['GH_ACCOUNT']}/{make['GH_PROJECT']}/tar.gz/{tag}"
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
    errors = []
    if hashlib.sha256(data).hexdigest() != want_sha.group(1) or len(data) != int(want_size.group(1)):
        errors.append(f"the archive of {tag} does not match distinfo")

    archive = Path(tempfile.gettempdir()) / distfile if not args.archive else args.archive
    if not args.archive:
        archive.write_bytes(data)
    prefix = f"{make['GH_PROJECT']}-{tag}/"
    with tarfile.open(archive) as tar:
        names = [m.name[len(prefix):] for m in tar.getmembers() if m.isfile() and m.name.startswith(prefix)]
    want = expected_plist(names)
    have = [line for line in (PORT / "pkg-plist").read_text().splitlines() if line and not line.startswith("@")]
    for line in sorted(set(want) - set(have)):
        errors.append(f"pkg-plist is missing {line}")
    for line in sorted(set(have) - set(want)):
        errors.append(f"pkg-plist lists {line}, which the pinned commit does not install")
    if have != sorted(have):
        errors.append("pkg-plist is not sorted")
    if "www-ui/index.php" not in want or not any(n.startswith("www-ui/ui/") for n in want):
        errors.append("the pinned commit has no app/public/index.php or dist/public/ui (not a freesense-webui release tree)")

    if errors:
        print("FreeSense-webui port audit failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1
    print(f"FreeSense-webui port matches freesense-webui {tag[:12]} ({len(want)} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
