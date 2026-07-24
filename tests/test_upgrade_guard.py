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


if __name__ == "__main__":
    unittest.main()
