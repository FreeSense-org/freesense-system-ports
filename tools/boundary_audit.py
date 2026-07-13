#!/usr/bin/env python3
"""Reject optional-package content from the system ports overlay."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

for path in ROOT.rglob("*"):
    if ".git" in path.parts:
        continue
    relative = path.relative_to(ROOT).as_posix()
    if any(part.startswith("FreeSense-pkg-") for part in path.parts):
        errors.append(f"optional package path is not allowed: {relative}")
    if relative == "Mk/bsd.freesense-package.mk":
        errors.append(f"optional package framework is not allowed: {relative}")

if errors:
    print("System/package repository boundary violations:", file=sys.stderr)
    for error in sorted(set(errors)):
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print("System ports boundary audit passed.")
