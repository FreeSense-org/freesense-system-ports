#!/usr/bin/env python3
"""Translate cloud-init datasource data into native FreeSense config.xml."""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET


KEY = re.compile(
    r"^(ssh-(?:rsa|ed25519)|ecdsa-sha2-nistp(?:256|384|521)|sk-ssh-ed25519@openssh\.com) "
    r"[A-Za-z0-9+/]+={0,3}(?: .*)?$"
)
ROLE = re.compile(r"^(wan|lan|opt[1-9][0-9]*)$")
DEFAULT_CONFIG = Path("/conf/config.xml")
DEFAULT_STATE = Path("/var/db/freesense-cloud-init/instance.json")
DEFAULT_USER_DATA = Path("/var/lib/cloud/instance/user-data.txt")
DEFAULT_NETWORK_CONFIG_JSON = Path("/var/lib/cloud/instance/network-config.json")
DEFAULT_NETWORK_CONFIG = Path("/var/lib/cloud/instance/network-config")
REDACTED_USERDATA = frozenset({"redacted", "none", "null"})
CLOUD_CONFIG_KEYS = ("hostname", "fqdn", "timezone", "ssh_authorized_keys", "freesense")
SSH_AUTHORIZED_KEYS_MARK = re.compile(r"(?m)^\s*ssh_authorized_keys\s*:")


class InvalidMetadata(ValueError):
    pass


def child(parent: ET.Element, name: str) -> ET.Element:
    found = parent.find(name)
    return found if found is not None else ET.SubElement(parent, name)


def set_text(parent: ET.Element, name: str, value: object) -> None:
    child(parent, name).text = str(value)


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InvalidMetadata("metadata root must be an object")
    return value


def usable_user_data_text(value: object) -> str | None:
    """Return non-empty raw user-data text, treating redacted placeholders as missing."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in REDACTED_USERDATA or lowered.startswith("ci-b64-"):
        return None
    return value


def load_raw_user_data(query_all: dict) -> str | None:
    """Load raw cloud-config text from official query, query --all, then on-disk cache."""
    candidates: list[object] = []
    try:
        queried = subprocess.run(
            ["cloud-init", "query", "userdata"],
            check=False, text=True, capture_output=True,
        )
        if queried.returncode == 0:
            candidates.append(queried.stdout)
    except OSError:
        pass
    candidates.append(query_all.get("userdata"))
    if DEFAULT_USER_DATA.is_file():
        try:
            candidates.append(DEFAULT_USER_DATA.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            raise InvalidMetadata(f"user-data is unreadable: {error}") from error
    for candidate in candidates:
        text = usable_user_data_text(candidate)
        if text is not None:
            return text
    return None


def merge_cloud_config(value: dict, user_data: str | None) -> dict:
    """Merge selected cloud-config keys from raw user-data into a query document."""
    if user_data is None:
        return value
    try:
        import yaml
    except ImportError as error:
        raise InvalidMetadata("cloud-init YAML support is unavailable") from error
    try:
        configured = yaml.safe_load(user_data)
    except yaml.YAMLError as error:
        raise InvalidMetadata(f"cloud-config is unreadable: {error}") from error
    if not isinstance(configured, dict):
        raise InvalidMetadata("cloud-config user-data must be an object")
    for key in CLOUD_CONFIG_KEYS:
        if key in configured:
            value[key] = configured[key]
    value["_freesense_raw_user_data"] = user_data
    return value


def load_cached_network_config() -> dict | None:
    """Read the datasource network config from cloud-init's trusted cache.

    FreeBSD cloud-init 25.2 keeps this data on the cached datasource object but
    does not expose it through ``cloud-init query`` or write the Linux-style
    ``instance/network-config`` files.  Reuse cloud-init's own cache loader so
    multi-interface metadata remains available to the native adapter.
    """
    try:
        from cloudinit import sources
        from cloudinit.stages import Init
    except ImportError as error:
        raise InvalidMetadata("cloud-init Python API is unavailable") from error
    try:
        datasource = Init(ds_deps=[sources.DEP_FILESYSTEM]).fetch(existing="trust")
        network = datasource.network_config
    except Exception as error:
        raise InvalidMetadata(f"cached cloud-init network data is unavailable: {error}") from error
    if network is None:
        return None
    if not isinstance(network, dict):
        raise InvalidMetadata("cached cloud-init network data is not an object")
    return network


def query_cloud_init() -> dict:
    fixture = os.environ.get("FREESENSE_CLOUD_INIT_INPUT")
    if fixture:
        return load_json(Path(fixture))
    result = subprocess.run(
        ["cloud-init", "query", "--all"],
        check=True, text=True, capture_output=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise InvalidMetadata("cloud-init query did not return an object")
    try:
        import yaml
    except ImportError as error:
        raise InvalidMetadata("cloud-init YAML support is unavailable") from error
    value = merge_cloud_config(value, load_raw_user_data(value))
    network = None
    for network_config in (
        DEFAULT_NETWORK_CONFIG_JSON,
        DEFAULT_NETWORK_CONFIG,
    ):
        if not network_config.is_file():
            continue
        try:
            text = network_config.read_text(encoding="utf-8")
            network = (
                json.loads(text) if network_config.suffix == ".json"
                else yaml.safe_load(text)
            )
        except (OSError, ValueError) as error:
            raise InvalidMetadata(f"network-config is unreadable: {error}") from error
        break
    if network is None:
        network = load_cached_network_config()
    if network is not None:
        value["network"] = network
    return value


def initialize_cloud_init_local() -> None:
    """Discover local datasources before FreeSense configures networking."""
    subprocess.run(["cloud-init", "init", "--local"], check=True)


def normalize(raw: dict) -> dict:
    """Accept a stable adapter document or cloud-init query --all output."""
    if raw.get("schema_version") == "freesense.cloud-metadata/v1":
        return raw
    ds = raw.get("ds", {}) if isinstance(raw.get("ds"), dict) else {}
    meta = ds.get("meta_data", {}) if isinstance(ds.get("meta_data"), dict) else {}
    v1 = raw.get("v1", {}) if isinstance(raw.get("v1"), dict) else {}
    network = (
        raw.get("network")
        or ds.get("network_json")
        or ds.get("network_config")
        or {}
    )
    keys = raw.get("ssh_authorized_keys")
    if keys is None:
        keys = raw.get("public_ssh_keys") or meta.get("public_keys") or []
    if isinstance(keys, dict):
        keys = list(keys.values())
    normalized = {
        "schema_version": "freesense.cloud-metadata/v1",
        "instance_id": raw.get("instance_id") or meta.get("instance-id") or meta.get("uuid"),
        "hostname": (
            raw.get("fqdn")
            or raw.get("hostname")
            or raw.get("local_hostname")
            or raw.get("local-hostname")
            or meta.get("hostname")
            or meta.get("local_hostname")
            or meta.get("local-hostname")
            or v1.get("hostname")
            or v1.get("local_hostname")
            or v1.get("local-hostname")
        ),
        "timezone": raw.get("timezone"),
        "ssh_authorized_keys": keys,
        "network": network,
        "freesense": raw.get("freesense", {}),
    }
    raw_user_data = raw.get("_freesense_raw_user_data")
    if isinstance(raw_user_data, str) and raw_user_data.strip():
        normalized["_freesense_raw_user_data"] = raw_user_data
    return normalized


def valid_keys(values: object) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise InvalidMetadata("ssh_authorized_keys must be an array")
    keys = []
    for value in values:
        value = value.strip() if isinstance(value, str) else ""
        if not KEY.fullmatch(value):
            raise InvalidMetadata("invalid SSH public key")
        try:
            decoded = base64.b64decode(value.split()[1], validate=True)
        except (ValueError, IndexError):
            raise InvalidMetadata("invalid SSH public key encoding") from None
        if len(decoded) < 16:
            raise InvalidMetadata("invalid SSH public key encoding")
        if value not in keys:
            keys.append(value)
    return keys


def normalize_network(value: object) -> list[dict]:
    if value in ({}, None):
        return []
    if not isinstance(value, dict):
        raise InvalidMetadata("network metadata must be an object")
    if isinstance(value.get("links"), list) and isinstance(value.get("networks"), list):
        interfaces_by_id = {}
        for order, link in enumerate(value["links"]):
            if not isinstance(link, dict) or not isinstance(link.get("id"), str):
                raise InvalidMetadata("OpenStack network link is invalid")
            item = {
                "name": link.get("name") or link["id"],
                "mac": link.get("ethernet_mac_address"),
                "mtu": link.get("mtu"),
                "addresses": [],
                "order": order,
            }
            interfaces_by_id[link["id"]] = item
        for network in value["networks"]:
            if not isinstance(network, dict) or network.get("link") not in interfaces_by_id:
                raise InvalidMetadata("OpenStack network references an unknown link")
            item = interfaces_by_id[network["link"]]
            network_type = network.get("type")
            if network_type == "ipv4_dhcp":
                item["dhcp4"] = True
            elif network_type in {"ipv6_dhcp", "ipv6_slaac"}:
                item["dhcp6" if network_type == "ipv6_dhcp" else "slaac"] = True
            elif network_type in {"ipv4", "ipv6"}:
                address = network.get("ip_address")
                prefix = network.get("netmask")
                try:
                    if isinstance(prefix, str) and not prefix.isdigit():
                        prefix = ipaddress.ip_network(f"0.0.0.0/{prefix}").prefixlen
                    item["addresses"].append(f"{address}/{prefix}")
                except ValueError:
                    raise InvalidMetadata("OpenStack static network is invalid") from None
                if network.get("gateway"):
                    item["gateway4" if network_type == "ipv4" else "gateway6"] = network["gateway"]
                    item["default_route"] = True
        dns = [
            service.get("address") for service in value.get("services", [])
            if isinstance(service, dict) and service.get("type") == "dns"
        ]
        for item in interfaces_by_id.values():
            if dns:
                item["dns"] = dns
        interfaces = list(interfaces_by_id.values())
    elif isinstance(value.get("interfaces"), list):
        interfaces = value["interfaces"]
    else:
        ethernets = value.get("ethernets", {})
        if not isinstance(ethernets, dict):
            raise InvalidMetadata("network ethernets must be an object")
        interfaces = []
        for order, (name, item) in enumerate(ethernets.items()):
            if not isinstance(item, dict):
                raise InvalidMetadata("ethernet definition must be an object")
            match = item.get("match", {})
            match = match if isinstance(match, dict) else {}
            routes = item.get("routes", [])
            default = any(
                isinstance(route, dict)
                and route.get("to") in {"0.0.0.0/0", "::/0", "default"}
                for route in routes if isinstance(routes, list)
            )
            route_gateways = {}
            if isinstance(routes, list):
                for route in routes:
                    if not isinstance(route, dict) or route.get("to") not in {
                        "0.0.0.0/0", "::/0", "default"
                    } or not route.get("via"):
                        continue
                    try:
                        version = ipaddress.ip_address(route["via"]).version
                    except ValueError:
                        raise InvalidMetadata("default route gateway is invalid") from None
                    route_gateways["gateway4" if version == 4 else "gateway6"] = route["via"]
            interfaces.append({
                **item,
                **route_gateways,
                "name": item.get("set-name") or name,
                "mac": match.get("macaddress"),
                "default_route": default or bool(item.get("gateway4") or item.get("gateway6")),
                "order": order,
            })
    result = []
    seen_names: set[str] = set()
    seen_macs: set[str] = set()
    for order, item in enumerate(interfaces):
        if not isinstance(item, dict):
            raise InvalidMetadata("network interface must be an object")
        name = item.get("name")
        mac = item.get("mac")
        if name is not None and (not isinstance(name, str) or not name):
            raise InvalidMetadata("invalid interface name")
        if mac is not None:
            try:
                mac = ":".join(f"{int(part, 16):02x}" for part in mac.split(":"))
            except (AttributeError, ValueError):
                raise InvalidMetadata("invalid interface MAC address") from None
            if len(mac) != 17:
                raise InvalidMetadata("invalid interface MAC address")
        if name and name in seen_names or mac and mac in seen_macs:
            raise InvalidMetadata("duplicate interface mapping")
        if name:
            seen_names.add(name)
        if mac:
            seen_macs.add(mac)
        addresses = item.get("addresses", [])
        addresses = [addresses] if isinstance(addresses, str) else addresses
        if not isinstance(addresses, list):
            raise InvalidMetadata("addresses must be an array")
        parsed_addresses = []
        for address in addresses:
            try:
                parsed_addresses.append(ipaddress.ip_interface(address))
            except ValueError:
                raise InvalidMetadata(f"invalid address {address}") from None
        mtu = item.get("mtu")
        if mtu is not None and (not isinstance(mtu, int) or not 576 <= mtu <= 9216):
            raise InvalidMetadata("invalid MTU")
        result.append({
            **item, "name": name, "mac": mac, "addresses": parsed_addresses,
            "order": item.get("order", order),
        })
    return result


def resolve_interfaces(metadata: list[dict], detected: list[dict], extension: dict) -> list[tuple[str, dict]]:
    by_name = {item.get("name"): item for item in detected}
    by_mac = {str(item.get("mac", "")).lower(): item for item in detected}
    resolved: list[dict] = []
    used: set[str] = set()
    for item in metadata:
        candidates = []
        if item.get("name") in by_name:
            candidates.append(by_name[item["name"]])
        if item.get("mac") in by_mac:
            candidates.append(by_mac[item["mac"]])
        unique = {candidate["name"]: candidate for candidate in candidates}
        if len(unique) > 1:
            raise InvalidMetadata("interface name and MAC resolve to different devices")
        if not unique:
            raise InvalidMetadata("metadata interface is not present")
        device = next(iter(unique.values()))
        if device["name"] in used:
            raise InvalidMetadata("multiple metadata interfaces resolve to one device")
        used.add(device["name"])
        resolved.append({**item, "device": device["name"]})
    if not resolved:
        resolved = [
            {"device": item["name"], "name": item["name"], "order": order,
             "mac": str(item.get("mac", "")).lower() or None,
             "dhcp4": order == 0, "addresses": []}
            for order, item in enumerate(detected)
        ]
    mappings = extension.get("interfaces", []) if isinstance(extension, dict) else []
    if isinstance(mappings, dict):
        mappings = [{"match": key, "role": role} for key, role in mappings.items()]
    explicit: dict[str, str] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict) or not ROLE.fullmatch(str(mapping.get("role", ""))):
            raise InvalidMetadata("invalid FreeSense interface role mapping")
        match = str(mapping.get("match") or mapping.get("name") or mapping.get("mac") or "").lower()
        matches = [
            item for item in resolved
            if match in {str(item.get("device", "")).lower(), str(item.get("name", "")).lower(),
                         str(item.get("mac", "")).lower()}
        ]
        if len(matches) != 1:
            raise InvalidMetadata("ambiguous FreeSense interface role mapping")
        if mapping["role"] in explicit.values() or matches[0]["device"] in explicit:
            raise InvalidMetadata("duplicate FreeSense interface role mapping")
        explicit[matches[0]["device"]] = mapping["role"]
    result: list[tuple[str, dict]] = []
    remaining = [item for item in resolved if item["device"] not in explicit]
    assigned_roles = set(explicit.values())
    if "wan" not in assigned_roles and remaining:
        default = [item for item in remaining if item.get("default_route")]
        if len(default) > 1:
            raise InvalidMetadata("multiple interfaces carry the metadata default route")
        wan = default[0] if default else remaining[0]
        explicit[wan["device"]] = "wan"
        remaining.remove(wan)
        assigned_roles.add("wan")
    for item in remaining:
        if "lan" not in assigned_roles:
            role = "lan"
        else:
            index = 1
            while f"opt{index}" in assigned_roles:
                index += 1
            role = f"opt{index}"
        explicit[item["device"]] = role
        assigned_roles.add(role)
    for item in resolved:
        result.append((explicit[item["device"]], item))
    return result


def configure_interface(node: ET.Element, item: dict) -> None:
    set_text(node, "enable", "")
    set_text(node, "if", item["device"])
    for old in ("ipaddr", "subnet", "ipaddrv6", "subnetv6", "gateway", "gatewayv6", "mtu"):
        found = node.find(old)
        if found is not None:
            node.remove(found)
    v4 = [address for address in item["addresses"] if address.version == 4]
    v6 = [address for address in item["addresses"] if address.version == 6]
    if item.get("dhcp4", False):
        set_text(node, "ipaddr", "dhcp")
    elif v4:
        set_text(node, "ipaddr", v4[0].ip)
        set_text(node, "subnet", v4[0].network.prefixlen)
    if item.get("dhcp6", False):
        set_text(node, "ipaddrv6", "dhcp6")
    elif item.get("slaac", item.get("accept-ra", False)):
        set_text(node, "ipaddrv6", "slaac")
    elif v6:
        set_text(node, "ipaddrv6", v6[0].ip)
        set_text(node, "subnetv6", v6[0].network.prefixlen)
    if item.get("mtu"):
        set_text(node, "mtu", item["mtu"])


def configured_instance_id(config_path: Path) -> str | None:
    """Return the instance applied to the current boot environment."""
    try:
        return ET.parse(config_path).getroot().findtext("cloudinit/instance_id")
    except (ET.ParseError, OSError):
        return None


def should_skip_apply(
    state_path: Path,
    config_path: Path,
    instance_id: str,
    keys: list[str],
    cidrs: list[str],
) -> bool:
    """Skip only when this instance was already applied with at least these keys/CIDRs."""
    if not state_path.exists():
        return False
    try:
        previous = load_json(state_path)
    except (InvalidMetadata, json.JSONDecodeError, OSError):
        return False
    if previous.get("instance_id") != instance_id:
        return False
    if configured_instance_id(config_path) != instance_id:
        return False
    previous_keys = previous.get("ssh_key_count", 0)
    try:
        previous_keys = int(previous_keys)
    except (TypeError, ValueError):
        previous_keys = 0
    # Re-apply when user-data later exposes keys after a zero-key seal.
    if keys and previous_keys == 0:
        return False
    previous_cidrs = previous.get("management_cidrs", [])
    if not isinstance(previous_cidrs, list):
        previous_cidrs = []
    if cidrs and not previous_cidrs and keys:
        return False
    return True


def apply(metadata: dict, detected: list[dict], config_path: Path, state_path: Path) -> bool:
    instance_id = metadata.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise InvalidMetadata("instance_id is required")
    keys = valid_keys(metadata.get("ssh_authorized_keys"))
    raw_user_data = metadata.get("_freesense_raw_user_data")
    if (
        isinstance(raw_user_data, str)
        and SSH_AUTHORIZED_KEYS_MARK.search(raw_user_data)
        and not keys
    ):
        raise InvalidMetadata(
            "cloud-config declares ssh_authorized_keys but none were imported"
        )
    network = normalize_network(metadata.get("network"))
    extension = metadata.get("freesense", {})
    if extension is None:
        extension = {}
    if not isinstance(extension, dict):
        raise InvalidMetadata("freesense extension must be an object")
    cidrs = extension.get("management_cidrs", [])
    if not isinstance(cidrs, list):
        raise InvalidMetadata("management_cidrs must be an array")
    try:
        cidrs = [str(ipaddress.ip_network(value, strict=False)) for value in cidrs]
    except (TypeError, ValueError):
        raise InvalidMetadata("invalid management CIDR") from None
    if should_skip_apply(state_path, config_path, instance_id, keys, cidrs):
        return False
    assignments = resolve_interfaces(network, detected, extension)
    if len(assignments) == 1:
        role, item = assignments[0]
        item = {
            **item,
            "dhcp4": True,
            "addresses": [
                address for address in item.get("addresses", []) if address.version == 6
            ],
        }
        item.pop("gateway4", None)
        assignments = [("wan", item)]

    tree = ET.parse(config_path)
    root = tree.getroot()
    system = child(root, "system")
    if len(assignments) == 1:
        # FreeSense otherwise puts its anti-lockout rule on the sole WAN
        # interface, exposing the WebUI and SSH to every source.
        set_text(child(system, "webgui"), "noantilockout", "true")
    hostname = metadata.get("hostname")
    if hostname:
        if not isinstance(hostname, str) or len(hostname) > 253:
            raise InvalidMetadata("invalid hostname")
        labels = hostname.rstrip(".").split(".", 1)
        set_text(system, "hostname", labels[0])
        if len(labels) == 2:
            set_text(system, "domain", labels[1])
    timezone = metadata.get("timezone")
    if timezone:
        if not isinstance(timezone, str) or ".." in timezone or timezone.startswith("/"):
            raise InvalidMetadata("invalid timezone")
        set_text(system, "timezone", timezone)
    users = system.findall("user")
    admin = next((user for user in users if user.findtext("name") == "admin"), None)
    if admin is None:
        raise InvalidMetadata("config.xml has no admin account")
    old_hash = admin.find("bcrypt-hash")
    if old_hash is not None:
        admin.remove(old_hash)
    set_text(admin, "password", "*LOCKED*")
    if keys:
        set_text(admin, "authorizedkeys", base64.b64encode(("\n".join(keys) + "\n").encode()).decode())
        ssh = child(system, "ssh")
        set_text(ssh, "enable", "enabled")
        set_text(ssh, "sshdkeyonly", "enabled")

    interfaces = child(root, "interfaces")
    for existing in list(interfaces):
        interfaces.remove(existing)
    for role, item in assignments:
        interface_node = ET.SubElement(interfaces, role)
        configure_interface(interface_node, item)
        if item.get("gateway4"):
            set_text(interface_node, "gateway", f"{role.upper()}_CLOUD_GW")
        if item.get("gateway6"):
            set_text(interface_node, "gatewayv6", f"{role.upper()}_CLOUD_GWV6")

    gateways = child(root, "gateways")
    for gateway in list(gateways.findall("gateway_item")):
        if gateway.findtext("descr") == "FreeSense cloud gateway":
            gateways.remove(gateway)
    for role, item in assignments:
        for version, field in ((4, "gateway4"), (6, "gateway6")):
            if not item.get(field):
                continue
            gateway = ET.SubElement(gateways, "gateway_item")
            set_text(gateway, "interface", role)
            set_text(gateway, "gateway", item[field])
            set_text(gateway, "name", f"{role.upper()}_CLOUD_GW" + ("V6" if version == 6 else ""))
            set_text(gateway, "ipprotocol", "inet6" if version == 6 else "inet")
            set_text(gateway, "descr", "FreeSense cloud gateway")

    dns = []
    for _, item in assignments:
        nameservers = item.get("nameservers", {})
        addresses = nameservers.get("addresses", []) if isinstance(nameservers, dict) else item.get("dns", [])
        if isinstance(addresses, list):
            dns.extend(str(ipaddress.ip_address(value)) for value in addresses)
    for existing in list(system.findall("dnsserver")):
        system.remove(existing)
    for address in dict.fromkeys(dns):
        ET.SubElement(system, "dnsserver").text = address

    filter_node = child(root, "filter")
    for rule in list(filter_node.findall("rule")):
        if rule.findtext("descr") == "FreeSense cloud temporary SSH":
            filter_node.remove(rule)
    if len(assignments) == 1 and keys:
        sources = [(value, ipaddress.ip_network(value).version) for value in cidrs]
        if not sources:
            sources = [("any", 4), ("any", 6)]
        for source_value, ip_version in sources:
            rule = ET.SubElement(filter_node, "rule")
            set_text(rule, "type", "pass")
            set_text(rule, "interface", "wan")
            set_text(rule, "ipprotocol", "inet6" if ip_version == 6 else "inet")
            set_text(rule, "protocol", "tcp")
            set_text(rule, "descr", "FreeSense cloud temporary SSH")
            source = ET.SubElement(rule, "source")
            set_text(source, "any" if source_value == "any" else "address",
                     "" if source_value == "any" else source_value)
            destination = ET.SubElement(rule, "destination")
            set_text(destination, "network", "wanip6" if ip_version == 6 else "wanip")
            set_text(destination, "port", "22")

    cloud = child(root, "cloudinit")
    set_text(cloud, "instance_id", instance_id)
    set_text(cloud, "schema_version", "freesense.cloud-metadata/v1")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=config_path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        tree.write(temp, encoding="utf-8", xml_declaration=True)
        temp.flush()
        os.fsync(temp.fileno())
    shutil.copymode(config_path, temp_path)
    os.replace(temp_path, config_path)
    authorized_keys_path = (
        Path("/root/.ssh/authorized_keys")
        if config_path == DEFAULT_CONFIG
        else config_path.parent / "authorized_keys"
    )
    if keys:
        authorized_keys_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        key_temp = authorized_keys_path.with_suffix(".tmp")
        key_temp.write_text("\n".join(keys) + "\n", encoding="utf-8")
        key_temp.chmod(0o600)
        os.replace(key_temp, authorized_keys_path)
    else:
        authorized_keys_path.unlink(missing_ok=True)
    state_temp = state_path.with_suffix(".tmp")
    state_temp.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
                "ssh_key_count": len(keys),
                "management_cidrs": cidrs,
                "schema": 2,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(state_temp, state_path)
    return True


def detected_interfaces(path: Path | None) -> list[dict]:
    if path:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise InvalidMetadata("detected interfaces fixture must be an array")
        return value
    output = subprocess.run(["ifconfig", "-l"], check=True, text=True, capture_output=True).stdout
    ignored = ("lo", "pflog", "pfsync", "enc")
    result = []
    for name in output.split():
        if name.startswith(ignored):
            continue
        detail = subprocess.run(["ifconfig", name], check=True, text=True, capture_output=True).stdout
        match = re.search(r"\bether ([0-9a-f:]{17})\b", detail, re.I)
        if match:
            result.append({"name": name, "mac": match.group(1).lower()})
    if not result:
        raise InvalidMetadata("no usable network interfaces detected")
    return result


def run_cloud_init_modules() -> int:
    """Run first-boot modules, tolerating cloud-init's degraded exit code."""
    for command in (
        ("cloud-init", "init"),
        ("cloud-init", "modules", "--mode", "config"),
        ("cloud-init", "modules", "--mode", "final"),
    ):
        completed = subprocess.run(command, check=False)
        if completed.returncode == 2:
            print(
                "freesense-cloud-init: "
                f"{' '.join(command)} completed with recoverable errors (rc=2); "
                "continuing native provisioning",
                file=os.sys.stderr,
            )
            continue
        if completed.returncode != 0:
            print(
                "freesense-cloud-init: "
                f"{' '.join(command)} failed (rc={completed.returncode})",
                file=os.sys.stderr,
            )
            return completed.returncode
    return 0


def activate_cloud_runtime() -> None:
    """Apply late key/CIDR imports to the live filter and SSH service.

    Early boot may seal an instance before NoCloud user-data is readable.
    Final phase re-imports after full cloud-init; this makes the temporary
    WAN SSH rule and authorized keys take effect without another reboot.
    """
    account_script = (
        "require_once('config.inc');"
        "require_once('functions.inc');"
        "require_once('auth.inc');"
        "local_reset_accounts();"
    )
    for command in (
        ["/usr/local/bin/php", "-r", account_script],
        ["/etc/rc.filter_configure_sync"],
        ["/usr/local/bin/php-cgi", "-f", "/etc/sshd"],
    ):
        subprocess.run(command, check=False)


def provision(
    *,
    input_path: Path | None,
    interfaces: Path | None,
    config: Path,
    state: Path,
    initialize_local: bool,
) -> bool:
    """Query cloud-init (or a fixture) and apply native FreeSense config."""
    if input_path is None and initialize_local:
        initialize_cloud_init_local()
    raw = load_json(input_path) if input_path else query_cloud_init()
    return apply(
        normalize(raw),
        detected_interfaces(interfaces),
        config,
        state,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("early", "final"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--interfaces", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    if args.phase == "final":
        try:
            status = run_cloud_init_modules()
            if status != 0:
                return status
            # Full cloud-init has already populated userdata caches. Re-apply so
            # keys/CIDRs that were missing during early boot become live.
            changed = provision(
                input_path=args.input,
                interfaces=args.interfaces,
                config=args.config,
                state=args.state,
                initialize_local=False,
            )
            if changed:
                activate_cloud_runtime()
        except (
            InvalidMetadata,
            ET.ParseError,
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as error:
            print(f"freesense-cloud-init: {error}", file=os.sys.stderr)
            return 1
        finally:
            subprocess.run(["service", "qemu-guest-agent", "onestart"], check=False)
        return 0
    try:
        provision(
            input_path=args.input,
            interfaces=args.interfaces,
            config=args.config,
            state=args.state,
            initialize_local=args.input is None,
        )
    except (InvalidMetadata, ET.ParseError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"freesense-cloud-init: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
