#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os
import re

from pathlib import Path

import yaml

from .exceptions import ConfigError
from .sandbox import get_known_apparmor_profiles, bwrap_boolean_flags, bwrap_list_flags, bwrap_key_value_flags
from .console import print_warning, print_blank, print_success

# <---
# --->
# -- Base cache directory.

cache_dir = Path.home() / ".cache/nx-apphub-cli"
debian_snapshot_pattern = re.compile(r"^\d{8}T\d{6}Z$")


def _promote_legacy_key(section, old_key, new_key):
    """Promote legacy underscore-style keys to hyphen-style keys."""
    if not isinstance(section, dict):
        return

    if old_key in section and new_key in section:
        raise ConfigError(
            f"YAML contains both '{old_key}' and '{new_key}'. "
            f"Use only '{new_key}'."
        )

    if old_key in section and new_key not in section:
        section[new_key] = section.pop(old_key)


def normalize_yaml_key_aliases(config):
    """Normalize legacy YAML key names to canonical hyphen-style keys."""
    if not isinstance(config, dict):
        return config

    buildinfo = config.get("buildinfo")
    if isinstance(buildinfo, dict):
        _promote_legacy_key(buildinfo, "os_target", "os-target")

    apprunconf = config.get("apprunconf")
    if isinstance(apprunconf, dict):
        _promote_legacy_key(apprunconf, "extra_rpaths", "extra-rpaths")
        _promote_legacy_key(apprunconf, "prebuild_commands", "prebuild-commands")

    sandbox = config.get("sandbox")
    if isinstance(sandbox, dict):
        _promote_legacy_key(sandbox, "aa_profile", "aa-profile")
        _promote_legacy_key(sandbox, "bwrap_env", "bwrap-env")
        _promote_legacy_key(sandbox, "bwrap_unset-env", "bwrap-unset-env")

    return config


# -- Load YAML configuration.

def load_yaml_config(config_path):
    """Load and parse a YAML configuration file and return its contents as a dict."""

    if not os.path.isfile(config_path):
        raise ConfigError(
            f"'{config_path}' is not a valid YAML file. "
            "Are you sure you passed the full path to a YAML file, not a directory?"
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ConfigError(f"'{config_path}' is empty or invalid.")

        return normalize_yaml_key_aliases(data)

    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parsing error in '{config_path}': {e}") from e
    except Exception as e:
        raise ConfigError(f"Unexpected error while loading '{config_path}': {e}") from e


def get_apprunconf_value(config, key, default=None, expected_type=None):
    """Fetch values from the 'apprunconf' section of the YAML configuration with type validation."""
    value = config.get("apprunconf", {}).get(key, default)

    if expected_type and not isinstance(value, expected_type):
        raise ConfigError(
            f"Invalid type for 'apprunconf.{key}'. "
            f"Expected {expected_type.__name__}, got {type(value).__name__}. "
            "Please correct the YAML configuration before proceeding."
        )

    return value.strip() if isinstance(value, str) else value


def validate_yaml_config(config):
    """Validate the structure and types of the YAML configuration."""

    if not isinstance(config, dict):
        raise ConfigError("Top-level YAML structure must be a mapping (dictionary).")

    required_sections = {
        "buildinfo": {
            "name": str,
            "version": str,
            "binarypath": str
        },
        "apprunconf": {
            "exec": str,
            "setpath": str,
            "setlibpath": str,
            "envvars": dict,
        }
    }

    # -- Validate required sections and keys.

    for section, keys in required_sections.items():
        if section not in config:
            raise ConfigError(f"Missing required section '{section}' in YAML.")

        for key, expected_type in keys.items():
            value = config[section].get(key)
            if value is None:
                raise ConfigError(f"Missing required key '{key}' in section '{section}' of YAML.")
            if not isinstance(value, expected_type):
                raise ConfigError(
                    f"Invalid type for '{section}.{key}'. "
                    f"Expected {expected_type.__name__}, got {type(value).__name__}."
                )

    os_target = config["buildinfo"].get("os-target")
    if os_target is not None:
        if not isinstance(os_target, str) or not os_target.strip():
            raise ConfigError("'buildinfo.os-target' must be a non-empty string when defined.")
    
    # -- Validate apprunconf section.

    apprunconf = config.get("apprunconf", {})

    extra = apprunconf.get("extra-rpaths")
    if extra is None:
        apprunconf["extra-rpaths"] = []
    elif isinstance(extra, str):
        apprunconf["extra-rpaths"] = [extra]
    elif isinstance(extra, list):
        if not all(isinstance(x, str) for x in extra):
            raise ConfigError("'apprunconf.extra-rpaths' list must contain only strings.")
    else:
        raise ConfigError("'apprunconf.extra-rpaths' must be a string or a list of strings.")

    prebuild = apprunconf.get("prebuild-commands")
    if prebuild is None:
        apprunconf["prebuild-commands"] = []
    elif isinstance(prebuild, list):
        if not all(isinstance(x, str) for x in prebuild):
            raise ConfigError("'apprunconf.prebuild-commands' list must contain only strings.")
    else:
        raise ConfigError("'apprunconf.prebuild-commands' must be a list of strings.")

    config["apprunconf"] = apprunconf

    # -- Validate sandbox section.

    sandbox = config.get("sandbox", {})
    if not isinstance(sandbox, dict):
        raise ConfigError("'sandbox' must be a dictionary.")

    sandbox_type = sandbox.get("type", "none")
    if sandbox_type not in ("bwrap", "firejail", "none"):
        raise ConfigError("'sandbox.type' must be one of: bwrap, firejail, none.")

    # -- Validate integration section early (needed for Firejail).

    integration = config.get("integration", {})
    if not isinstance(integration, dict):
        raise ConfigError("'integration' must be a dictionary.")

    integration_type = integration.get("type")
    if integration_type not in ("cli", "gui", "wm"):
        raise ConfigError("'integration.type' must be one of: cli, gui, wm.")

    integration_launcher = integration.get("launcher", "")
    if integration_launcher is None:
        integration_launcher = ""
    if not isinstance(integration_launcher, str):
        raise ConfigError("'integration.launcher' must be a string.")
    integration_launcher = integration_launcher.strip()
    if integration_launcher and "/" in integration_launcher:
        raise ConfigError("'integration.launcher' must be a desktop file name, not a path.")
    if integration_launcher and not integration_launcher.endswith(".desktop"):
        raise ConfigError("'integration.launcher' must end with '.desktop'.")
    integration["launcher"] = integration_launcher
    config["integration"] = integration

    if integration_type == "wm" and sandbox_type != "none":
        raise ConfigError(
            "Window manager integration must not use a sandbox. "
            "Set 'sandbox.type' to 'none' when using integration.type: wm."
        )

    # -- Validate distrorepo architecture consistency and allowed values.

    distrorepo = config["buildinfo"].get("distrorepo", {})
    if isinstance(distrorepo, list):
        repos_to_validate = distrorepo
    elif isinstance(distrorepo, dict):
        repos_to_validate = distrorepo.get("base", [])
    else:
        repos_to_validate = []

    arches = set()
    for entry in repos_to_validate:
        if not isinstance(entry, dict):
            raise ConfigError("Each distrorepo entry must be a dictionary.")

        arch = entry.get("arch")
        distro = entry.get("distro")
        snapshot = entry.get("snapshot")

        if not arch:
            raise ConfigError("Missing 'arch' key in distrorepo entry.")

        if not distro:
            raise ConfigError("Missing 'distro' key in distrorepo entry.")

        if not isinstance(distro, str):
            raise ConfigError("'distrorepo.distro' must be a string.")

        distro = distro.lower()

        if distro == "ubuntu" and arch != "amd64":
            raise ConfigError("'distrorepo.arch' for 'ubuntu' must be: amd64.")

        if distro == "ubuntu-ports" and arch not in ("arm64", "riscv64"):
            raise ConfigError("'distrorepo.arch' for 'ubuntu-ports' must be: arm64 or riscv64.")

        if distro == "debian-snapshot":
            if not snapshot:
                raise ConfigError("'distrorepo.snapshot' is required when 'distrorepo.distro' is: debian-snapshot.")
            if not isinstance(snapshot, str):
                raise ConfigError("'distrorepo.snapshot' must be a string.")
            if not debian_snapshot_pattern.match(snapshot):
                raise ConfigError("'distrorepo.snapshot' must use format: YYYYMMDDThhmmssZ (e.g. 20260725T202958Z).")
        elif snapshot is not None:
            raise ConfigError("'distrorepo.snapshot' is only valid when 'distrorepo.distro' is: debian-snapshot.")

        arches.add(arch)

    if len(arches) > 1:
        raise ConfigError("'distrorepo.arch' must not have mixed architectures.")

    def validate_firejail(sandbox):
        required = {"name"}
        optional = {"aa-profile"}

        for key in required:
            if key not in sandbox:
                raise ConfigError(f"Missing required 'sandbox.{key}' key for Firejail.")

        if "aa-profile" in sandbox:
            if not isinstance(sandbox["aa-profile"], str):
                raise ConfigError("'sandbox.aa-profile' must be a string.")

            profile = sandbox["aa-profile"]
            if profile != "none":
                known_profiles = get_known_apparmor_profiles()
                if profile not in known_profiles:
                    print_warning(f"Warning: aa-profile '{profile}' does not match any profile in /etc/apparmor.d/")
                    print_blank()
                    print_warning("   👉 To fix this, create or rename the profile file or set 'aa-profile: none'.", prefix="")
                    print_blank()

        for key in sandbox.keys():
            if key not in ({"type"} | required | optional):
                raise ConfigError(f"Unknown key 'sandbox.{key}' for Firejail.")

    def validate_bwrap(sandbox):
        allowed_keys = {"type"} | bwrap_boolean_flags.keys() | bwrap_list_flags.keys() | bwrap_key_value_flags.keys()

        for key in sandbox.keys():
            if key not in allowed_keys:
                raise ConfigError(f"Unknown key 'sandbox.{key}' in Bwrap config.")

        for key in bwrap_boolean_flags:
            if key in sandbox and not isinstance(sandbox[key], bool):
                raise ConfigError(f"'sandbox.{key}' must be a boolean.")

        for key in bwrap_list_flags:
            if key in sandbox:
                if not isinstance(sandbox[key], list):
                    raise ConfigError(f"'sandbox.{key}' must be a list.")

                if key == "bwrap-env":
                    for item in sandbox[key]:
                        if not isinstance(item, dict) or len(item) != 1:
                            raise ConfigError("Each item in 'sandbox.bwrap-env' must be a dictionary with a single key-value pair.")
                        for k, v in item.items():
                            if not isinstance(k, str) or not isinstance(v, str):
                                raise ConfigError("'sandbox.bwrap-env' entries must have string key-value pairs.")

                elif key == "bwrap-unset-env":
                    if not all(isinstance(v, str) for v in sandbox[key]):
                        raise ConfigError("'sandbox.bwrap-unset-env' entries must be strings.")

        for key in bwrap_key_value_flags:
            if key in sandbox and not isinstance(sandbox[key], (str, int)):
                raise ConfigError(f"'sandbox.{key}' must be a string or integer.")

    # -- Firejail validation (disallow GUI apps).

    if sandbox_type == "firejail":
        validate_firejail(sandbox)
        if integration_type in ("gui", "wm"):
            raise ConfigError(
                "Firejail sandboxing is only supported for CLI apps. "
                "Use Bubblewrap (bwrap) for GUI applications instead."
            )
    elif sandbox_type == "bwrap":
        validate_bwrap(sandbox)

    # -- Validate runtime.

    allowed_runtimes = {"classic", "go", "uruntime"}
    runtime = config["buildinfo"].get("runtime", "classic")

    if not isinstance(runtime, str) or runtime not in allowed_runtimes:
        raise ConfigError(f"'buildinfo.runtime' must be one of: {', '.join(sorted(allowed_runtimes))}.")

    print_success("YAML validation passed successfully.")
    print_blank()
