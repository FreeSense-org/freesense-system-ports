import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
UPGRADE = (
    ROOT
    / "sysutils"
    / "FreeSense-upgrade"
    / "files"
    / "FreeSense-upgrade"
).read_text(encoding="utf-8")
REPO_SETUP = (
    ROOT
    / "sysutils"
    / "FreeSense-upgrade"
    / "files"
    / "FreeSense-repo-setup"
).read_text(encoding="utf-8")


class OptionalPackageInstallTests(unittest.TestCase):
    def test_optional_installs_do_not_lock_the_system_meta_package(self) -> None:
        install_start = UPGRADE.index("pkg_install() {")
        install_end = UPGRADE.index("\npkg_reinstall_all() {", install_start)
        install = UPGRADE[install_start:install_end]

        self.assertIn(
            'pkg_with_pb "${_cmd}${dry_run:+ }${dry_run} ${_pkg_name}"',
            install,
        )
        self.assertNotIn('pkg_lock "${product}"', install)
        self.assertNotIn("unlock_optional_system_pkg", UPGRADE)

    def test_system_upgrade_does_not_orphan_optional_packages(self) -> None:
        orphan_loop = (
            "for _package in $(_pkg query %n "
            "$(_pkg info -E -g ${pkg_prefix}\\*)); do"
        )

        self.assertNotIn(orphan_loop, UPGRADE)
        self.assertNotIn(
            '"Scheduling package ${_package} for removal"',
            UPGRADE,
        )
        self.assertEqual(
            UPGRADE.count(
                "A System-only repository query must never classify them as orphans."
            ),
            2,
        )


class RepositoryOSVersionTests(unittest.TestCase):
    def test_changed_repository_tools_have_hotfix_revisions(self) -> None:
        upgrade_makefile = (
            ROOT / "sysutils" / "FreeSense-upgrade" / "Makefile"
        ).read_text(encoding="utf-8")
        repoc_makefile = (
            ROOT / "sysutils" / "FreeSense-repoc" / "Makefile"
        ).read_text(encoding="utf-8")

        self.assertRegex(upgrade_makefile, r"(?m)^PORTREVISION=\s*8$")
        self.assertRegex(repoc_makefile, r"(?m)^PORTREVISION=\s*5$")

    def test_running_userland_is_the_legacy_fallback(self) -> None:
        self.assertIn('OSVERSION="$(uname -U 2>/dev/null || true)"', REPO_SETUP)
        self.assertIn(
            'OSVERSION="$(echo "${ABI}" | cut -f2 -d:)00000"',
            REPO_SETUP,
        )

    def test_signed_repository_osversion_overrides_the_fallback(self) -> None:
        self.assertIn(
            '[ -r "${_repo_conf_file%%.conf}.osversion" ]',
            REPO_SETUP,
        )
        self.assertIn('OSVERSION="${_repo_osversion}"', REPO_SETUP)


if __name__ == "__main__":
    unittest.main()
