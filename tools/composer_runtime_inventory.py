#!/usr/bin/env python3
# Copyright (c) 2026 The FreeSense Project
# SPDX-License-Identifier: Apache-2.0
"""Generate the audited Composer inventory from the actual System port, not a development lock."""

import argparse
import json
import re
from pathlib import Path


def runtime_packages(makefile: str) -> dict[str, str]:
    variables = dict(re.findall(r"^([A-Z][A-Z0-9_]*)\s*=\s*([^\s#]+)", makefile, re.M))
    logical = makefile.replace("\\\n", " ")
    entries = " ".join(re.findall(r"^GH_TUPLE\+?=\s*(.*)$", logical, re.M)).split()
    tuples = []
    for entry in entries:
        match = re.fullmatch(r"([\w.-]+):([\w.-]+):\$\{([A-Z][A-Z0-9_]*)\}:([\w.-]+)", entry)
        if match is None:
            raise ValueError(f"Unrecognized shipped dependency: {entry}")
        tuples.append(match.groups())
    if not tuples:
        raise ValueError("No runtime dependencies found in the System port")
    packages = {}
    for owner, repo, variable, _ in tuples:
        name = ("psr/" if owner == "php-fig" else owner.lower() + "/") + repo.lower()
        version = variables.get(variable, "").removeprefix("v")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version):
            raise ValueError(f"Unresolved runtime version for {name}: {variable}")
        if name in packages:
            raise ValueError(f"Duplicate runtime dependency: {name}")
        packages[name] = version
    return packages


def check_source_lock(packages: dict[str, str], source_lock: dict) -> None:
    for package in source_lock["packages"]:
        name, version = package["name"], package["version"].removeprefix("v")
        if packages.get(name) != version:
            raise ValueError(f"Shipped dependency differs from composer.lock: {name} {version}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=Path, default=Path(__file__).resolve().parents[1] / "devel/FreeSense-composer-deps/Makefile")
    parser.add_argument("--source-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    packages = runtime_packages(args.port.read_text(encoding="utf-8"))
    check_source_lock(packages, json.loads(args.source_lock.read_text(encoding="utf-8")))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "composer.json").write_text(json.dumps({"name": "freesense/runtime-audit", "require": packages}, indent=2) + "\n")
    lock = {"packages": [{"name": name, "version": version, "type": "library"} for name, version in sorted(packages.items())], "packages-dev": []}
    (args.output / "composer.lock").write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Runtime inventory covers all {len(packages)} shipped Composer dependencies.")


if __name__ == "__main__":
    main()
