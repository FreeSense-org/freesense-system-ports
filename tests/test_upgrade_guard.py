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


class OptionalPackageSystemGuardTests(unittest.TestCase):
    def test_optional_installs_lock_the_system_closure(self) -> None:
        install_start = UPGRADE.index("pkg_install() {")
        install_end = UPGRADE.index("\npkg_reinstall_all() {", install_start)
        install = UPGRADE[install_start:install_end]

        required = (
            'case "${_pkg_name}" in',
            '"${pkg_prefix}"*)',
            'is_pkg_installed "${product}"',
            '_pkg query %k "${product}"',
            'unlock_optional_system_pkg="${product}"',
            'pkg_lock "${product}"',
            'pkg_unlock "${unlock_optional_system_pkg}"',
            "unset unlock_optional_system_pkg",
        )
        for contract in required:
            self.assertIn(contract, install)

        self.assertLess(
            install.index('pkg_lock "${product}"'),
            install.index('pkg_with_pb "${_cmd}'),
        )
        self.assertGreater(
            install.index('pkg_unlock "${unlock_optional_system_pkg}"'),
            install.index('pkg_with_pb "${_cmd}'),
        )

    def test_failure_cleanup_releases_the_temporary_lock(self) -> None:
        exit_start = UPGRADE.index("_exit() {")
        exit_end = UPGRADE.index("\n#\n# Returns the current root filesystem", exit_start)
        exit_function = UPGRADE[exit_start:exit_end]

        self.assertIn(
            'pkg_unlock "${unlock_optional_system_pkg}"',
            exit_function,
        )


if __name__ == "__main__":
    unittest.main()
