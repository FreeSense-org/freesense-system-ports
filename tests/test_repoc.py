#!/usr/bin/env python3
"""End-to-end safety tests for the signed repository-channel client."""

from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPOC = ROOT / "sysutils/FreeSense-repoc/files/FreeSense-repoc"
SYSTEM_SHA = "a" * 64
PACKAGES_SHA = "b" * 64
STABLE_SYSTEM_SHA = "c" * 64
STABLE_PACKAGES_SHA = "d" * 64
FREEBSD_PIN = "9" * 64
OSVERSION = 1600019


def component_url(kind: str, fingerprint: str, train: str = "1.1",
                  package_arch: str = "amd64") -> str:
    if kind == "system":
        return f"https://pkg.freesense.org/v1/artifacts/system/{fingerprint}/{package_arch}"
    return (
        "https://pkg.freesense.org/v1/artifacts/packages/"
        f"{train}/{fingerprint}/{package_arch}"
    )


def complete_channel(
    name: str,
    description: str,
    train: str,
    default: bool,
    system_sha: str = SYSTEM_SHA,
    packages_sha: str = PACKAGES_SHA,
    system_generation: int = 12,
    packages_generation: int = 8,
) -> dict[str, object]:
    return {
        "name": name,
        "description": description,
        "package_train": train,
        "abi": "FreeBSD:16:amd64",
        "altabi": "freebsd:16:x86:64",
        "default": default,
        "system": {
            "fingerprint": system_sha,
            "url": component_url("system", system_sha),
            "generation": system_generation,
            "published_at": "2026-07-22T08:00:00Z",
            "verified": True,
        },
        "packages": {
            "fingerprint": packages_sha,
            "system_fingerprint": system_sha,
            "url": component_url("packages", packages_sha, train),
            "generation": packages_generation,
            "published_at": "2026-07-22T09:00:00Z",
            "verified": True,
        },
    }


def valid_payload(
    system_sha: str = SYSTEM_SHA,
    packages_sha: str = PACKAGES_SHA,
    system_generation: int = 12,
    packages_generation: int = 8,
) -> dict[str, object]:
    return {
        "schema_version": "freesense.channels/v1",
        "channels": {
            "devel": complete_channel(
                "devel",
                "Development version",
                "1.1",
                True,
                system_sha,
                packages_sha,
                system_generation,
                packages_generation,
            )
        },
    }


def v2_payload(**kwargs: object) -> dict[str, object]:
    payload = valid_payload(**kwargs)
    payload["schema_version"] = "freesense.channels/v2"
    for channel in payload["channels"].values():
        system = channel["system"]
        packages = channel["packages"]
        system["freebsd_pin_id"] = FREEBSD_PIN
        packages["freebsd_pin_id"] = FREEBSD_PIN
        packages["built_against_system"] = system["fingerprint"]
    return payload


def v3_payload() -> dict[str, object]:
    payload = v2_payload()
    payload["schema_version"] = "freesense.channels/v3"
    devel = payload["channels"]["devel"]
    devel["version"] = "1.1.0"
    stable = complete_channel(
        "stable", "FreeSense 1.0.0 stable", "1.0", False,
        STABLE_SYSTEM_SHA, STABLE_PACKAGES_SHA, 6, 4,
    )
    stable["version"] = "1.0.0"
    stable["system"]["freebsd_pin_id"] = FREEBSD_PIN
    stable["system"]["osversion"] = OSVERSION
    stable["packages"]["freebsd_pin_id"] = FREEBSD_PIN
    stable["packages"]["built_against_system"] = STABLE_SYSTEM_SHA
    payload["channels"]["stable"] = stable
    payload["channels"]["devel"]["system"]["osversion"] = OSVERSION
    return payload


def stable_complete_devel_pending_payload() -> dict[str, object]:
    devel = complete_channel("devel", "Development version", "1.1", True)
    devel.pop("packages")
    return {
        "schema_version": "freesense.channels/v1",
        "channels": {
            "devel": devel,
            "stable": complete_channel(
                "stable",
                "Stable version",
                "1.0",
                False,
                STABLE_SYSTEM_SHA,
                STABLE_PACKAGES_SHA,
                6,
                4,
            ),
        },
    }


def payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()


class RepocSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.name != "posix":
            raise unittest.SkipTest("the installed updater is a POSIX-shell program")
        cls.php = shutil.which("php")
        cls.openssl = shutil.which("openssl")
        cls.shell = shutil.which("sh")
        cls.flock = shutil.which("flock")
        cls.real_mv = shutil.which("mv")
        if not cls.php or not cls.openssl or not cls.shell or not cls.real_mv:
            raise unittest.SkipTest("php, openssl, sh, and mv are required")
        cls.key_directory = tempfile.TemporaryDirectory()
        key_root = Path(cls.key_directory.name)
        cls.private_key = key_root / "private.pem"
        cls.public_key = key_root / "public.pem"
        subprocess.run(
            [
                cls.openssl,
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                cls.private_key,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                cls.openssl,
                "pkey",
                "-in",
                cls.private_key,
                "-pubout",
                "-out",
                cls.public_key,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "key_directory"):
            cls.key_directory.cleanup()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def signed_envelope(
        self,
        case: Path,
        payload: dict[str, object],
        *,
        corrupt_signature: bool = False,
        invalid_envelope: bool = False,
    ) -> tuple[Path, bytes]:
        raw = payload_bytes(payload)
        payload_file = case / "signed-payload.json"
        signature_file = case / "signature.bin"
        envelope_file = case / "envelope.json"
        payload_file.write_bytes(raw)
        subprocess.run(
            [
                self.openssl,
                "dgst",
                "-sha256",
                "-sign",
                self.private_key,
                "-out",
                signature_file,
                payload_file,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        signature = bytearray(signature_file.read_bytes())
        if corrupt_signature:
            signature[0] ^= 1
        envelope = {
            "schema_version": "freesense.repositories/v3",
            "payload": base64.b64encode(raw).decode(),
            "signature": base64.b64encode(signature).decode(),
        }
        if invalid_envelope:
            envelope["schema_version"] = "freesense.repositories/invalid"
        envelope_file.write_text(json.dumps(envelope), encoding="utf-8")
        return envelope_file, raw

    def run_repoc(
        self,
        name: str,
        payload: dict[str, object],
        *,
        cached: dict[str, object] | None = None,
        local_seed: dict[str, object] | None = None,
        fetch_failure: bool = False,
        corrupt_signature: bool = False,
        invalid_envelope: bool = False,
        local_only: bool = False,
        selected: str | None = None,
        installed_version: str = "1.0.0-RELEASE",
        fail_swap: bool = False,
        lock_hold: float = 0,
        machine_arch: str | None = None,
        processor_arch: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path, bytes]:
        case = self.root / name
        case.mkdir()
        repos = case / "repos"
        repos.mkdir()
        sentinel = repos / "FreeSense-repo-existing.conf"
        sentinel.write_text("existing repository configuration\n", encoding="utf-8")
        if selected is not None:
            (repos / f"FreeSense-repo-{selected}.default").touch()
        local = case / "share/channel/repos.manifest.json"
        cache = case / "state/repos.manifest.json"
        if cached is not None:
            cache.parent.mkdir(parents=True)
            cache.write_bytes(payload_bytes(cached))
        if local_seed is not None:
            local.parent.mkdir(parents=True)
            local.write_bytes(payload_bytes(local_seed))
        envelope, live_raw = self.signed_envelope(
            case,
            payload,
            corrupt_signature=corrupt_signature,
            invalid_envelope=invalid_envelope,
        )
        fake_bin = case / "bin"
        fake_bin.mkdir()
        curl = fake_bin / "curl"
        curl.write_text(
            """#!/bin/sh
if [ "${FAKE_CURL_FAIL:-}" = 1 ]; then
    exit 22
fi
output=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = -o ]; then
        shift
        output="$1"
    fi
    shift
done
[ -n "$output" ] || exit 2
cp "$FAKE_CURL_SOURCE" "$output"
""",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        mv = fake_bin / "mv"
        mv.write_text(
            """#!/bin/sh
if [ "${FAKE_MV_FAIL_NEW:-}" = 1 ]; then
    for argument in "$@"; do
        case "$argument" in
            */.repos.new.*) exit 70 ;;
        esac
    done
fi
exec "$REAL_MV" "$@"
""",
            encoding="utf-8",
        )
        mv.chmod(0o755)
        lock_file = case / "repoc.lock"
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": str(fake_bin) + os.pathsep + environment["PATH"],
                "PHP": self.php,
                "OPENSSL": self.openssl,
                "PRODUCT": "FreeSense",
                "REPOS_DIR": str(repos),
                "SHARE_DIR": str(case / "share"),
                "MANIFEST_LOCAL": str(local),
                "MANIFEST_CACHE": str(cache),
                "MANIFEST_URL": "https://pkg.freesense.org/v1/repos.manifest.json",
                "CHANNEL_KEY": str(self.public_key),
                "LOCK_FILE": str(lock_file),
                "FAKE_CURL_SOURCE": str(envelope),
                "FAKE_CURL_FAIL": "1" if fetch_failure else "0",
                "FAKE_MV_FAIL_NEW": "1" if fail_swap else "0",
                "REAL_MV": self.real_mv,
                # Exercise the exact value read from /etc/version. repoc must
                # normalize lifecycle suffixes itself before version checks.
                "INSTALLED_VERSION": installed_version,
            }
        )
        if machine_arch is not None:
            environment["MACHINE_ARCH"] = machine_arch
        if processor_arch is not None:
            environment["PROCESSOR_ARCH"] = processor_arch
        command = [self.shell, REPOC]
        if local_only:
            command.append("-l")
        holder = None
        if lock_hold:
            if not self.flock:
                self.skipTest("flock is required for the Linux concurrency test")
            ready = case / "lock-ready"
            holder = subprocess.Popen(
                [
                    self.flock,
                    lock_file,
                    self.shell,
                    "-c",
                    'touch "$1"; sleep "$2"',
                    "holder",
                    ready,
                    str(lock_hold),
                ]
            )
            deadline = time.monotonic() + 3
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "test lock holder did not start")
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            if holder is not None:
                holder.wait(timeout=3)
        self.last_elapsed = time.monotonic() - started
        return result, repos, cache, local, live_raw

    def assert_repositories_unchanged(self, repos: Path) -> None:
        self.assertEqual(
            (repos / "FreeSense-repo-existing.conf").read_text(encoding="utf-8"),
            "existing repository configuration\n",
        )
        self.assertFalse((repos / "FreeSense-repo-devel.conf").exists())

    def test_complete_verified_live_payload_is_retained_and_materialized(self) -> None:
        baseline = valid_payload(
            system_sha="c" * 64,
            packages_sha="d" * 64,
            system_generation=10,
            packages_generation=6,
        )
        live = valid_payload()
        local_seed = valid_payload(
            system_sha="e" * 64,
            packages_sha="f" * 64,
            system_generation=1,
            packages_generation=1,
        )
        result, repos, cache, local, _ = self.run_repoc(
            "complete", live, cached=baseline, local_seed=local_seed
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(live))
        self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o644)
        self.assertEqual(list(cache.parent.glob(".repos.manifest.json.tmp.*")), [])
        self.assertEqual(local.read_bytes(), payload_bytes(local_seed))
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn(component_url("system", SYSTEM_SHA), config)
        self.assertIn(component_url("packages", PACKAGES_SHA), config)
        self.assertTrue((repos / "FreeSense-repo-devel.default").exists())
        self.assertFalse((repos / "FreeSense-repo-existing.conf").exists())

    def test_arm64_payload_uses_only_aarch64_repositories(self) -> None:
        payload = v3_payload()
        for channel in payload["channels"].values():
            channel["architecture"] = "arm64"
            channel["package_arch"] = "aarch64"
            channel["abi"] = "FreeBSD:16:aarch64"
            channel["altabi"] = "freebsd:16:aarch64:64"
            train = channel["package_train"]
            channel["system"]["url"] = component_url(
                "system", channel["system"]["fingerprint"], train, "aarch64"
            )
            channel["packages"]["url"] = component_url(
                "packages", channel["packages"]["fingerprint"], train, "aarch64"
            )
        result, repos, _, _, _ = self.run_repoc(
            "arm64", payload, machine_arch="arm64", processor_arch="aarch64"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn("/aarch64", config)
        self.assertNotIn("/amd64", config)

    def test_selected_complete_channel_works_while_default_channel_is_pending(self) -> None:
        live = stable_complete_devel_pending_payload()
        result, repos, cache, _, _ = self.run_repoc(
            "stable-with-pending-devel",
            live,
            selected="stable",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(live))
        stable_config = (repos / "FreeSense-repo-stable.conf").read_text(
            encoding="utf-8"
        )
        self.assertIn(component_url("system", STABLE_SYSTEM_SHA), stable_config)
        self.assertIn(
            component_url("packages", STABLE_PACKAGES_SHA, "1.0"), stable_config
        )
        self.assertTrue((repos / "FreeSense-repo-stable.default").exists())
        self.assertFalse((repos / "FreeSense-repo-devel.conf").exists())

    def test_selected_pending_live_channel_uses_retained_complete_channel(self) -> None:
        live = valid_payload()
        live["channels"]["devel"].pop("packages")
        retained = valid_payload(
            system_sha=STABLE_SYSTEM_SHA,
            packages_sha=STABLE_PACKAGES_SHA,
            system_generation=10,
            packages_generation=6,
        )
        result, repos, cache, _, _ = self.run_repoc(
            "selected-pending-live",
            live,
            cached=retained,
            selected="devel",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("selected live channel is still pending", result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(retained))
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn(component_url("system", STABLE_SYSTEM_SHA), config)
        self.assertIn(component_url("packages", STABLE_PACKAGES_SHA), config)

    def test_transport_envelope_and_signature_failures_use_cached_payload(self) -> None:
        retained = valid_payload()
        for name, options in (
            ("transport", {"fetch_failure": True}),
            ("envelope", {"invalid_envelope": True}),
            ("signature", {"corrupt_signature": True}),
        ):
            with self.subTest(name=name):
                result, repos, cache, _, _ = self.run_repoc(
                    name, valid_payload(), cached=retained, **options
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("trying trusted fallback", result.stderr)
                self.assertEqual(cache.read_bytes(), payload_bytes(retained))
                self.assertTrue((repos / "FreeSense-repo-devel.conf").exists())

    def test_fetch_failure_uses_local_seed_only_when_cache_is_absent(self) -> None:
        seed = valid_payload()
        result, repos, cache, local, _ = self.run_repoc(
            "local-fallback",
            valid_payload(),
            local_seed=seed,
            fetch_failure=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((repos / "FreeSense-repo-devel.conf").exists())
        self.assertFalse(cache.exists())
        self.assertEqual(local.read_bytes(), payload_bytes(seed))

    def test_structurally_valid_pending_live_payload_uses_retained_channel(self) -> None:
        mutations = [
            ("missing-packages", lambda p: p["channels"]["devel"].pop("packages")),
            (
                "system-unverified",
                lambda p: p["channels"]["devel"]["system"].__setitem__(
                    "verified", False
                ),
            ),
            (
                "packages-unverified",
                lambda p: p["channels"]["devel"]["packages"].__setitem__(
                    "verified", False
                ),
            ),
            (
                "components-missing",
                lambda p: (
                    p["channels"]["devel"].pop("system"),
                    p["channels"]["devel"].pop("packages"),
                ),
            ),
        ]
        retained = valid_payload(
            system_sha=STABLE_SYSTEM_SHA,
            packages_sha=STABLE_PACKAGES_SHA,
        )
        retained_raw = payload_bytes(retained)
        for name, mutate in mutations:
            with self.subTest(name=name):
                candidate = valid_payload()
                mutate(candidate)
                result, repos, cache, _, _ = self.run_repoc(
                    f"pending-{name}", candidate, cached=retained
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("selected live channel is still pending", result.stderr)
                self.assertEqual(cache.read_bytes(), retained_raw)
                config = (repos / "FreeSense-repo-devel.conf").read_text(
                    encoding="utf-8"
                )
                self.assertIn(component_url("system", STABLE_SYSTEM_SHA), config)

    def test_inconsistent_signed_live_payload_changes_nothing(self) -> None:
        mutations = [
            ("missing-system", lambda p: p["channels"]["devel"].pop("system")),
            (
                "packages-not-strict-boolean",
                lambda p: p["channels"]["devel"]["packages"].__setitem__("verified", 1),
            ),
            (
                "noncanonical-fingerprint",
                lambda p: p["channels"]["devel"]["system"].__setitem__(
                    "fingerprint", SYSTEM_SHA.upper()
                ),
            ),
            (
                "noncanonical-packages-fingerprint",
                lambda p: p["channels"]["devel"]["packages"].__setitem__(
                    "fingerprint", PACKAGES_SHA.upper()
                ),
            ),
            (
                "system-url-mismatch",
                lambda p: p["channels"]["devel"]["system"].__setitem__(
                    "url", component_url("system", "e" * 64)
                ),
            ),
            (
                "packages-url-mismatch",
                lambda p: p["channels"]["devel"]["packages"].__setitem__(
                    "url", component_url("packages", PACKAGES_SHA, "9.9")
                ),
            ),
            (
                "packages-binding-mismatch",
                lambda p: p["channels"]["devel"]["packages"].__setitem__(
                    "system_fingerprint", "e" * 64
                ),
            ),
            (
                "zero-generation",
                lambda p: p["channels"]["devel"]["system"].__setitem__("generation", 0),
            ),
            (
                "string-generation",
                lambda p: p["channels"]["devel"]["packages"].__setitem__(
                    "generation", "8"
                ),
            ),
        ]
        retained = valid_payload()
        retained_raw = payload_bytes(retained)
        local_seed = valid_payload(
            system_sha="e" * 64,
            packages_sha="f" * 64,
            system_generation=1,
            packages_generation=1,
        )
        local_raw = payload_bytes(local_seed)
        for name, mutate in mutations:
            with self.subTest(name=name):
                candidate = copy.deepcopy(retained)
                mutate(candidate)
                result, repos, cache, local, _ = self.run_repoc(
                    name, candidate, cached=retained, local_seed=local_seed
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing changes", result.stderr)
                self.assert_repositories_unchanged(repos)
                self.assertEqual(cache.read_bytes(), retained_raw)
                self.assertEqual(local.read_bytes(), local_raw)

    def test_retained_generation_cannot_roll_back_or_change_identity(self) -> None:
        baseline = valid_payload()
        cases = []
        older_system = valid_payload(
            system_sha="c" * 64,
            packages_sha="d" * 64,
            system_generation=11,
            packages_generation=9,
        )
        cases.append(("older-system", older_system))
        older_packages = valid_payload(
            system_sha=SYSTEM_SHA,
            packages_sha="d" * 64,
            system_generation=12,
            packages_generation=7,
        )
        cases.append(("older-packages", older_packages))
        reused_generation = valid_payload(
            system_sha="c" * 64,
            packages_sha="d" * 64,
            system_generation=12,
            packages_generation=9,
        )
        cases.append(("generation-reused-for-new-identity", reused_generation))
        changed_generation = valid_payload(
            system_sha=SYSTEM_SHA,
            packages_sha=PACKAGES_SHA,
            system_generation=13,
            packages_generation=8,
        )
        cases.append(("identity-reused-with-new-generation", changed_generation))
        baseline_raw = payload_bytes(baseline)
        for name, candidate in cases:
            with self.subTest(name=name):
                result, repos, cache, _, _ = self.run_repoc(
                    name, candidate, cached=baseline
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("rolled back", result.stderr)
                self.assert_repositories_unchanged(repos)
                self.assertEqual(cache.read_bytes(), baseline_raw)

    def test_v2_reuses_optional_packages_across_system_updates_on_same_pin(self) -> None:
        baseline = v2_payload()
        live = v2_payload(
            system_sha=STABLE_SYSTEM_SHA,
            packages_sha=PACKAGES_SHA,
            system_generation=13,
            packages_generation=8,
        )
        packages = live["channels"]["devel"]["packages"]
        packages["built_against_system"] = SYSTEM_SHA
        result, repos, cache, _, _ = self.run_repoc(
            "v2-same-pin-package-reuse", live, cached=baseline
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(live))
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn(component_url("system", STABLE_SYSTEM_SHA), config)
        self.assertIn(component_url("packages", PACKAGES_SHA), config)

    def test_v2_rejects_reused_optional_packages_if_pin_changes(self) -> None:
        baseline = v2_payload()
        live = copy.deepcopy(baseline)
        live["channels"]["devel"]["system"]["freebsd_pin_id"] = "8" * 64
        live["channels"]["devel"]["packages"]["freebsd_pin_id"] = "8" * 64
        result, repos, cache, _, _ = self.run_repoc(
            "v2-changed-pin-package-reuse", live, cached=baseline
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing changes", result.stderr)
        self.assert_repositories_unchanged(repos)
        self.assertEqual(cache.read_bytes(), payload_bytes(baseline))

    def test_v3_booted_1_1_cannot_materialize_or_select_1_0(self) -> None:
        live = v3_payload()
        result, repos, cache, _, _ = self.run_repoc(
            "v3-no-downgrade", live, selected="stable", installed_version="1.1.0-DEVELOPMENT"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(live))
        self.assertTrue((repos / "FreeSense-repo-devel.conf").exists())
        self.assertTrue((repos / "FreeSense-repo-devel.default").exists())
        self.assertEqual(
            (repos / "FreeSense-repo-devel.version").read_text(encoding="utf-8").strip(),
            "1.1.0",
        )
        self.assertFalse((repos / "FreeSense-repo-stable.conf").exists())

    def test_v3_booted_1_0_can_select_stable_or_upgrade_to_1_1(self) -> None:
        live = v3_payload()
        result, repos, _, _, _ = self.run_repoc(
            "v3-booted-stable", live, selected="stable", installed_version="1.0.0-RELEASE"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((repos / "FreeSense-repo-stable.default").exists())
        self.assertTrue((repos / "FreeSense-repo-stable.conf").exists())
        self.assertTrue((repos / "FreeSense-repo-devel.conf").exists())
        self.assertEqual(
            (repos / "FreeSense-repo-stable.osversion").read_text(
                encoding="utf-8"
            ).strip(),
            str(OSVERSION),
        )
        self.assertEqual(
            (repos / "FreeSense-repo-devel.osversion").read_text(
                encoding="utf-8"
            ).strip(),
            str(OSVERSION),
        )

    def test_v3_rejects_invalid_exact_osversion(self) -> None:
        for name, value in (
            ("string", str(OSVERSION)),
            ("previous-major", 1599999),
            ("next-major", 1700000),
        ):
            with self.subTest(name=name):
                live = v3_payload()
                live["channels"]["stable"]["system"]["osversion"] = value
                result, repos, _, _, _ = self.run_repoc(
                    f"v3-osversion-{name}",
                    live,
                    selected="stable",
                    installed_version="1.0.0-RELEASE",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing changes", result.stderr)
                self.assert_repositories_unchanged(repos)

    def test_v3_rejects_stable_patch_rollback(self) -> None:
        baseline = v3_payload()
        baseline["channels"]["stable"]["version"] = "1.0.1"
        candidate = v3_payload()
        result, repos, cache, _, _ = self.run_repoc(
            "v3-stable-rollback", candidate, cached=baseline, selected="stable"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rolled back", result.stderr)
        self.assert_repositories_unchanged(repos)
        self.assertEqual(cache.read_bytes(), payload_bytes(baseline))

    def test_invalid_retained_payload_is_not_used_after_fetch_failure(self) -> None:
        retained = valid_payload()
        retained["channels"]["devel"]["packages"]["fingerprint"] = (
            PACKAGES_SHA.upper()
        )
        retained_raw = payload_bytes(retained)
        local_seed = valid_payload()
        result, repos, cache, local, _ = self.run_repoc(
            "invalid-retained",
            valid_payload(),
            cached=retained,
            local_seed=local_seed,
            fetch_failure=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("retained channel payload is invalid", result.stderr)
        self.assert_repositories_unchanged(repos)
        self.assertEqual(cache.read_bytes(), retained_raw)
        self.assertEqual(local.read_bytes(), payload_bytes(local_seed))

    def test_pending_retained_payload_uses_complete_baked_channel(self) -> None:
        retained = valid_payload()
        retained["channels"]["devel"].pop("packages")
        local_seed = valid_payload(
            system_sha=STABLE_SYSTEM_SHA,
            packages_sha=STABLE_PACKAGES_SHA,
        )
        result, repos, cache, local, _ = self.run_repoc(
            "pending-retained",
            valid_payload(),
            cached=retained,
            local_seed=local_seed,
            fetch_failure=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("trying baked channel", result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(retained))
        self.assertEqual(local.read_bytes(), payload_bytes(local_seed))
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn(component_url("system", STABLE_SYSTEM_SHA), config)

    def test_local_only_uses_baked_seed_without_reading_or_writing_cache(self) -> None:
        cached = valid_payload(
            system_sha="c" * 64,
            packages_sha="d" * 64,
            system_generation=20,
            packages_generation=20,
        )
        seed = valid_payload()
        result, repos, cache, local, _ = self.run_repoc(
            "local-only",
            valid_payload(),
            cached=cached,
            local_seed=seed,
            local_only=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = (repos / "FreeSense-repo-devel.conf").read_text(encoding="utf-8")
        self.assertIn(component_url("system", SYSTEM_SHA), config)
        self.assertNotIn(component_url("system", "c" * 64), config)
        self.assertEqual(cache.read_bytes(), payload_bytes(cached))
        self.assertEqual(local.read_bytes(), payload_bytes(seed))

    def test_local_only_accepts_selected_stable_while_devel_is_pending(self) -> None:
        cached = valid_payload()
        cached["channels"]["devel"]["system"]["fingerprint"] = "INVALID"
        seed = stable_complete_devel_pending_payload()
        result, repos, cache, local, _ = self.run_repoc(
            "local-only-selected-stable",
            valid_payload(),
            cached=cached,
            local_seed=seed,
            local_only=True,
            selected="stable",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cache.read_bytes(), payload_bytes(cached))
        self.assertEqual(local.read_bytes(), payload_bytes(seed))
        self.assertTrue((repos / "FreeSense-repo-stable.default").exists())
        self.assertTrue((repos / "FreeSense-repo-stable.conf").exists())
        self.assertFalse((repos / "FreeSense-repo-devel.conf").exists())

    def test_pending_baked_seed_fails_local_only_without_using_cache(self) -> None:
        cached = valid_payload()
        seed = valid_payload()
        seed["channels"]["devel"]["packages"]["verified"] = False
        result, repos, cache, local, _ = self.run_repoc(
            "pending-local-only",
            valid_payload(),
            cached=cached,
            local_seed=seed,
            local_only=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baked channel payload is pending or invalid", result.stderr)
        self.assert_repositories_unchanged(repos)
        self.assertEqual(cache.read_bytes(), payload_bytes(cached))
        self.assertEqual(local.read_bytes(), payload_bytes(seed))

    def test_failed_repository_swap_recovers_previous_directory(self) -> None:
        result, repos, _, _, _ = self.run_repoc(
            "failed-swap",
            valid_payload(),
            fail_swap=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repository swap failed", result.stderr)
        self.assert_repositories_unchanged(repos)
        self.assertEqual(list(repos.parent.glob(".repos.new.*")), [])
        self.assertEqual(list(repos.parent.glob(".repos.old.*")), [])

    def test_concurrent_run_waits_for_repository_lock(self) -> None:
        result, repos, _, _, _ = self.run_repoc(
            "serialized",
            valid_payload(),
            lock_hold=0.35,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(self.last_elapsed, 0.25)
        self.assertTrue((repos / "FreeSense-repo-devel.conf").exists())


if __name__ == "__main__":
    unittest.main()
