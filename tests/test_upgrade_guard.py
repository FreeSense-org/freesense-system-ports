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

        self.assertRegex(upgrade_makefile, r"(?m)^PORTREVISION=\s*12$")
        self.assertRegex(repoc_makefile, r"(?m)^PORTREVISION=\s*7$")

    def test_exit_starts_services_queued_by_pkg_scripts(self) -> None:
        exit_body = UPGRADE[UPGRADE.index("_exit() {"):]
        self.assertIn("start_queued_services", exit_body[:200])
        self.assertIn("/var/run/pkg_service_start.queue", UPGRADE)

    def test_unreadable_catalogue_is_not_reported_as_a_php_change(self) -> None:
        guard = UPGRADE.index('if [ -z "${new_php_pkg}" ]; then')
        php_check = UPGRADE.index('if [ "${cur_php_pkg}" != "${new_php_pkg}" ]; then')
        self.assertLess(guard, php_check)
        self.assertIn("Unable to read the package catalogue", UPGRADE[guard:php_check])

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


class RepositorySetupEnvironmentTests(unittest.TestCase):
    def test_repo_setup_never_inherits_the_pkg_only_settings(self) -> None:
        # The upgrader exports REPOS_DIR (a comma list) and FETCH_TIMEOUT for
        # pkg; FreeSense-repoc 1.0.0_6 read the same names and lost the
        # selected channel ("still pending"), so no update could start.
        self.assertIn(
            "env -u REPOS_DIR -u FETCH_TIMEOUT /usr/local/sbin/${product}-repo-setup",
            UPGRADE,
        )
        repoc = (
            ROOT / "sysutils" / "FreeSense-repoc" / "files" / "FreeSense-repoc"
        ).read_text(encoding="utf-8")
        self.assertIn('REPOS_DIR="${FREESENSE_REPOS_DIR:-', repoc)
        self.assertIn('FETCH_TIMEOUT="${REPOC_FETCH_TIMEOUT:-15}"', repoc)
        self.assertNotIn('"${REPOS_DIR:-', repoc)

    def test_exit_status_reaches_the_log_and_the_caller(self) -> None:
        self.assertIn("trap '_exit $?' EXIT", UPGRADE)
        self.assertNotIn("trap _exit 1 2 15 EXIT", UPGRADE)
        self.assertNotIn("\ttrap - EXIT", UPGRADE)
        setup = UPGRADE.index("-repo-setup ${dont_update}")
        failure = UPGRADE[setup:UPGRADE.index("11)", setup)]
        self.assertIn("_exit 1", failure)
        self.assertNotIn("\texit 1", failure)
        busy = UPGRADE.index("if pgrep -qF ${pid_file}")
        self.assertIn("exit 75", UPGRADE[busy:UPGRADE.index("\nfi\n", busy)])


if __name__ == "__main__":
    unittest.main()
