import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "sysutils/FreeSense-cloud-init/files/freesense_cloud_init.py"
PORT_MAKEFILE = ROOT / "sysutils/FreeSense-cloud-init/Makefile"
WRAPPER_TEMPLATE = (
    ROOT / "sysutils/FreeSense-cloud-init/files/freesense-cloud-init.in"
)
FIXTURES = ROOT / "tests/fixtures/cloud-init"
SPEC = importlib.util.spec_from_file_location("freesense_cloud_init", MODULE)
CLOUD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLOUD)

BASE_XML = """<?xml version="1.0"?>
<freesense><system><hostname>FreeSense</hostname><domain>home.arpa</domain>
<timezone>Etc/UTC</timezone><user><name>admin</name>
<bcrypt-hash>$2b$known-default</bcrypt-hash><uid>0</uid></user></system>
<interfaces><wan><if>em0</if><ipaddr>dhcp</ipaddr></wan></interfaces>
<filter><rule><descr>existing rule</descr></rule></filter></freesense>
"""


class CloudInitAdapterTests(unittest.TestCase):
    def test_port_keeps_guest_agent_as_an_independent_image_package(self):
        makefile = PORT_MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("RUN_DEPENDS=\tcloud-init:net/cloud-init", makefile)
        self.assertNotIn("qemu-guest-agent", makefile)
        self.assertNotIn("qemu@guestagent", makefile)

    def test_wrapper_uses_ports_selected_python(self):
        makefile = PORT_MAKEFILE.read_text(encoding="utf-8")
        wrapper = WRAPPER_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("PORTREVISION=\t2", makefile)
        self.assertIn("SUB_FILES=\tfreesense-cloud-init", makefile)
        self.assertIn("${WRKDIR}/freesense-cloud-init", makefile)
        self.assertIn("exec %%PYTHON_CMD%%", wrapper)
        self.assertNotIn("python3.11", wrapper)

    def test_local_datasource_is_initialized_before_query(self):
        with mock.patch.object(CLOUD.subprocess, "run") as run:
            CLOUD.initialize_cloud_init_local()
        run.assert_called_once_with(["cloud-init", "init", "--local"], check=True)

    def run_apply(self, fixture, detected):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = Path(directory.name, "config.xml")
        state = Path(directory.name, "instance.json")
        config.write_text(BASE_XML, encoding="utf-8")
        metadata = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        changed = CLOUD.apply(metadata, detected, config, state)
        return changed, config, state, ET.parse(config).getroot(), metadata

    def test_nocloud_two_nic_native_configuration(self):
        changed, config, state, root, metadata = self.run_apply(
            "nocloud-two-nic.json",
            [
                {"name": "vtnet0", "mac": "02:00:00:00:00:01"},
                {"name": "vtnet1", "mac": "02:00:00:00:00:02"},
            ],
        )
        self.assertTrue(changed)
        self.assertEqual(root.findtext("system/hostname"), "edge-1")
        self.assertEqual(root.findtext("system/domain"), "example.test")
        self.assertEqual(root.findtext("system/timezone"), "Europe/Copenhagen")
        self.assertEqual(root.findtext("interfaces/wan/if"), "vtnet0")
        self.assertEqual(root.findtext("interfaces/wan/ipaddr"), "dhcp")
        self.assertEqual(root.findtext("interfaces/wan/gateway"), "WAN_CLOUD_GW")
        self.assertEqual(root.findtext("gateways/gateway_item/gateway"), "192.0.2.1")
        self.assertEqual(root.findtext("interfaces/lan/ipaddr"), "10.20.0.1")
        self.assertEqual(root.findtext("interfaces/lan/ipaddrv6"), "2001:db8:20::1")
        self.assertEqual(
            [node.text for node in root.findall("system/dnsserver")],
            ["1.1.1.1", "2606:4700:4700::1111"],
        )
        self.assertIsNone(root.find("system/user/bcrypt-hash"))
        self.assertEqual(root.findtext("system/user/password"), "*LOCKED*")
        self.assertEqual(root.findtext("system/ssh/sshdkeyonly"), "enabled")
        self.assertNotIn(
            "FreeSense cloud temporary SSH",
            [rule.findtext("descr") for rule in root.findall("filter/rule")],
        )
        before = config.read_bytes()
        self.assertFalse(CLOUD.apply(metadata, [], config, state))
        self.assertEqual(config.read_bytes(), before)

    def test_configdrive_one_nic_limits_temporary_ssh(self):
        _, _, _, root, _ = self.run_apply(
            "configdrive-one-nic.json",
            [{"name": "vtnet0", "mac": "02:00:00:00:00:01"}],
        )
        rules = [
            rule for rule in root.findall("filter/rule")
            if rule.findtext("descr") == "FreeSense cloud temporary SSH"
        ]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].findtext("interface"), "wan")
        self.assertEqual(rules[0].findtext("protocol"), "tcp")
        self.assertEqual(rules[0].findtext("destination/port"), "22")
        self.assertEqual(rules[0].findtext("source/address"), "203.0.113.10/32")
        self.assertIsNone(rules[0].find("destination/port[.='443']"))

    def test_no_key_never_creates_wan_management(self):
        raw = json.loads((FIXTURES / "configdrive-one-nic.json").read_text())
        raw["instance_id"] = "no-key"
        raw["ssh_authorized_keys"] = []
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "config.xml")
            config.write_text(BASE_XML)
            CLOUD.apply(
                raw, [{"name": "vtnet0", "mac": "02:00:00:00:00:01"}],
                config, Path(directory, "state.json"),
            )
            root = ET.parse(config).getroot()
            self.assertNotIn(
                "FreeSense cloud temporary SSH",
                [rule.findtext("descr") for rule in root.findall("filter/rule")],
            )
            self.assertIsNone(root.find("system/ssh"))

    def test_ambiguous_mapping_does_not_rewrite_config(self):
        raw = json.loads((FIXTURES / "nocloud-two-nic.json").read_text())
        raw["freesense"]["interfaces"][1]["role"] = "wan"
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "config.xml")
            config.write_text(BASE_XML)
            before = config.read_bytes()
            with self.assertRaises(CLOUD.InvalidMetadata):
                CLOUD.apply(
                    raw,
                    [
                        {"name": "vtnet0", "mac": "02:00:00:00:00:01"},
                        {"name": "vtnet1", "mac": "02:00:00:00:00:02"},
                    ],
                    config, Path(directory, "state.json"),
                )
            self.assertEqual(config.read_bytes(), before)

    def test_openstack_network_data_is_normalized(self):
        interfaces = CLOUD.normalize_network({
            "links": [
                {"id": "wan0", "name": "vtnet0",
                 "ethernet_mac_address": "02:00:00:00:00:01", "mtu": 1450},
                {"id": "lan0", "name": "vtnet1",
                 "ethernet_mac_address": "02:00:00:00:00:02"},
            ],
            "networks": [
                {"link": "wan0", "type": "ipv4_dhcp"},
                {"link": "lan0", "type": "ipv4", "ip_address": "10.30.0.1",
                 "netmask": "255.255.255.0"},
            ],
            "services": [{"type": "dns", "address": "9.9.9.9"}],
        })
        self.assertTrue(interfaces[0]["dhcp4"])
        self.assertEqual(interfaces[0]["mtu"], 1450)
        self.assertEqual(str(interfaces[1]["addresses"][0]), "10.30.0.1/24")
        self.assertEqual(interfaces[1]["dns"], ["9.9.9.9"])

    def test_boot_environment_rollback_reapplies_shared_instance(self):
        changed, config, state, _, metadata = self.run_apply(
            "configdrive-one-nic.json",
            [{"name": "vtnet0", "mac": "02:00:00:00:00:01"}],
        )
        self.assertTrue(changed)
        config.write_text(BASE_XML, encoding="utf-8")
        self.assertTrue(CLOUD.apply(
            metadata,
            [{"name": "vtnet0", "mac": "02:00:00:00:00:01"}],
            config,
            state,
        ))
        self.assertEqual(
            ET.parse(config).getroot().findtext("cloudinit/instance_id"),
            metadata["instance_id"],
        )


if __name__ == "__main__":
    unittest.main()
