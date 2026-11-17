# Copyright (c) 2026 The FreeSense Project
# SPDX-License-Identifier: Apache-2.0
"""Verify that the vulnerability inventory follows shipped versions and fails on drift."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("runtime_inventory", Path(__file__).resolve().parents[1] / "tools/composer_runtime_inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class RuntimeInventoryTests(unittest.TestCase):
    def test_inventory_includes_the_additional_shipped_psr_package(self):
        port = Path(__file__).resolve().parents[1] / "devel/FreeSense-composer-deps/Makefile"
        packages = inventory.runtime_packages(port.read_text())
        self.assertEqual(packages["psr/simple-cache"], "3.0.0")
        self.assertEqual(packages["simplepie/simplepie"], "1.9.0")
        self.assertEqual(len(packages), 20)

    def test_mismatched_source_version_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            inventory.check_source_lock({"nette/utils": "4.1.5"}, {"packages": [{"name": "nette/utils", "version": "v4.1.4"}]})

    def test_missing_shipped_package_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            inventory.check_source_lock({}, {"packages": [{"name": "nette/utils", "version": "4.1.5"}]})

    def test_unresolved_version_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            inventory.runtime_packages("GH_TUPLE= symfony:cache:${MISSING}:cache")

    def test_unrecognized_tuple_cannot_disappear_from_inventory(self):
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            inventory.runtime_packages("GH_TUPLE= vendor:repo:1.0.0:group")

    def test_duplicate_dependency_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            inventory.runtime_packages("VER=1.0.0\nGH_TUPLE= symfony:cache:${VER}:one symfony:cache:${VER}:two")

    def test_normalized_versions_match(self):
        inventory.check_source_lock({"nette/utils": "4.1.5"}, {"packages": [{"name": "nette/utils", "version": "v4.1.5"}]})


if __name__ == "__main__":
    unittest.main()
