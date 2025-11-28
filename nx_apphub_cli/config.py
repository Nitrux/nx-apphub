#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os

from pathlib import Path

import yaml

from .exceptions import ConfigError
from .sandbox import get_known_apparmor_profiles, bwrap_boolean_flags, bwrap_list_flags, bwrap_key_value_flags

# <---
# --->
# -- Base cache directory.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


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

        return data

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
    
    # -- Validate apprunconf section.

    apprunconf = config.get("apprunconf", {})

    extra = apprunconf.get("extra_rpaths")
    if extra is None:
        apprunconf["extra_rpaths"] = []
    elif isinstance(extra, str):
        apprunconf["extra_rpaths"] = [extra]
    elif isinstance(extra, list):
        if not all(isinstance(x, str) for x in extra):
            raise ConfigError("'apprunconf.extra_rpaths' list must contain only strings.")
    else:
        raise ConfigError("'apprunconf.extra_rpaths' must be a string or a list of strings.")

    prebuild = apprunconf.get("prebuild_commands")
    if prebuild is None:
        apprunconf["prebuild_commands"] = []
    elif isinstance(prebuild, list):
        if not all(isinstance(x, str) for x in prebuild):
            raise ConfigError("'apprunconf.prebuild_commands' list must contain only strings.")
    else:
        raise ConfigError("'apprunconf.prebuild_commands' must be a list of strings.")

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

    if integration_type == "wm" and sandbox_type != "none":
        raise ConfigError(
            "Window manager integration must not use a sandbox. "
            "Set 'sandbox.type' to 'none' when using integration.type: wm."
        )

    # -- Validate distrorepo architecture consistency and allowed values.

    distrorepo = config["buildinfo"].get("distrorepo", {})
    if isinstance(distrorepo, list):
        arches = set()
        for entry in distrorepo:
            arch = entry.get("arch")
            distro = entry.get("distro")

            if not arch:
                raise ConfigError("Missing 'arch' key in distrorepo entry.")

            if not distro:
                raise ConfigError("Missing 'distro' key in distrorepo entry.")

            if distro == "ubuntu" and arch != "amd64":
                raise ConfigError("'distrorepo.arch' for 'ubuntu' must be: amd64.")

            if distro == "ubuntu-ports" and arch not in ("arm64", "riscv64"):
                raise ConfigError("'distrorepo.arch' for 'ubuntu-ports' must be: arm64 or riscv64.")

            arches.add(arch)

        if len(arches) > 1:
            raise ConfigError("'distrorepo.arch' must not have mixed architectures.")

    def validate_firejail(sandbox):
        required = {"name"}
        optional = {"aa_profile"}

        for key in required:
            if key not in sandbox:
                raise ConfigError(f"Missing required 'sandbox.{key}' key for Firejail.")

        if "aa_profile" in sandbox:
            if not isinstance(sandbox["aa_profile"], str):
                raise ConfigError("'sandbox.aa_profile' must be a string.")

            profile = sandbox["aa_profile"]
            if profile != "none":
                known_profiles = get_known_apparmor_profiles()
                if profile not in known_profiles:
                    print(f"🚨 Warning: aa_profile '{profile}' does not match any profile in /etc/apparmor.d/")
                    print("\n   👉 To fix this, create or rename the profile file or set 'aa_profile: none'.\n")

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

                if key == "bwrap_env":
                    for item in sandbox[key]:
                        if not isinstance(item, dict) or len(item) != 1:
                            raise ConfigError("Each item in 'sandbox.bwrap_env' must be a dictionary with a single key-value pair.")
                        for k, v in item.items():
                            if not isinstance(k, str) or not isinstance(v, str):
                                raise ConfigError("'sandbox.bwrap_env' entries must have string key-value pairs.")

                elif key == "bwrap_unset-env":
                    if not all(isinstance(v, str) for v in sandbox[key]):
                        raise ConfigError("'sandbox.bwrap_unset-env' entries must be strings.")

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

    print("✅ YAML validation passed successfully.\n")
