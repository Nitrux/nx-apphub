#!/usr/bin/env python3

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
#   Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>                                                                                                                   #
#                                                                                                                                                                           #
#   Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:                          #
#                                                                                                                                                                           #
#    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.                                        #
#                                                                                                                                                                           #
#    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer                                      #
#       in the documentation and/or other materials provided with the distribution.                                                                                         #
#                                                                                                                                                                           #
#    3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software                    #
#       without specific prior written permission.                                                                                                                          #
#                                                                                                                                                                           #
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,                      #
#    THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS                  #
#    BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE                 #
#    GOODS OR SERVICES; LOSS OF USE, DATA,   OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,                      #
#    STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.   #
#############################################################################################################################################################################

import os
import sys

from pathlib import Path

import yaml

from .sandbox import get_known_apparmor_profiles, bwrap_boolean_flags, bwrap_list_flags, bwrap_key_value_flags


# -- Base cache directory.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Load YAML configuration.

def load_yaml_config(config_path):
    if not os.path.isfile(config_path):
        print(f"❌ Error: '{config_path}' is not a valid YAML file. Are you sure you passed the full path to a YAML file, not a directory?\n")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            print(f"❌ Error: {config_path} is empty or invalid.\n")
            sys.exit(1)

        return data

    except yaml.YAMLError as e:
        print(f"❌ YAML Parsing Error in '{config_path}': {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error while loading '{config_path}': {e}\n")
        sys.exit(1)


def get_apprunconf_value(config, key, default=None, expected_type=None):
    """Fetch values from the 'apprunconf' section of the YAML configuration with type validation."""
    value = config.get("apprunconf", {}).get(key, default)

    if expected_type and not isinstance(value, expected_type):
        print(f"❌ Error: Invalid type for 'apprunconf.{key}'. Expected {expected_type.__name__}, got {type(value).__name__}.\n")
        print("🛑 Please correct the YAML configuration before proceeding.\n")
        sys.exit(1)

    return value.strip() if isinstance(value, str) else value


def validate_yaml_config(config):
    """Validate the structure and types of the YAML configuration."""

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
            print(f"❌ Error: Missing required section '{section}' in YAML.\n")
            sys.exit(1)

        for key, expected_type in keys.items():
            value = config[section].get(key)
            if value is None:
                print(f"❌ Error: Missing required key '{key}' in section '{section}' of YAML.\n")
                sys.exit(1)
            if not isinstance(value, expected_type):
                print(f"❌ Error: Invalid type for '{section}.{key}'. Expected {expected_type.__name__}, got {type(value).__name__}.\n")
                sys.exit(1)

    # -- Validate sandbox section.

    sandbox = config.get("sandbox", {})
    if not isinstance(sandbox, dict):
        print("❌ Error: 'sandbox' must be a dictionary.\n")
        sys.exit(1)

    sandbox_type = sandbox.get("type", "none")
    if sandbox_type not in ("bwrap", "firejail", "none"):
        print("❌ Error: 'sandbox.type' must be one of: bwrap, firejail, none.\n")
        sys.exit(1)

    # -- Validate integration section early (needed for Firejail).

    integration = config.get("integration", {})
    if not isinstance(integration, dict):
        print("❌ Error: 'integration' must be a dictionary.\n")
        sys.exit(1)

    valid_keys = {"gui_app", "cli_app"}
    actual_keys = set(integration.keys())

    if not actual_keys:
        print("❌ Error: 'integration' must contain one key: either 'gui_app' or 'cli_app'.\n")
        sys.exit(1)

    if len(actual_keys) > 1 or not actual_keys.issubset(valid_keys):
        print("❌ Error: 'integration' must only contain one of: 'gui_app' or 'cli_app'.\n")
        sys.exit(1)

    only_key = next(iter(actual_keys))
    if not isinstance(integration[only_key], bool):
        print(f"❌ Error: 'integration.{only_key}' must be a boolean.\n")
        sys.exit(1)

    def validate_firejail(sandbox):
        required = {"name"}
        optional = {"aa_profile"}

        for key in required:
            if key not in sandbox:
                print(f"❌ Error: Missing required 'sandbox.{key}' key for Firejail.\n")
                sys.exit(1)

        if "aa_profile" in sandbox:
            if not isinstance(sandbox["aa_profile"], str):
                print("❌ Error: 'sandbox.aa_profile' must be a string.\n")
                sys.exit(1)

            profile = sandbox["aa_profile"]
            if profile != "none":
                known_profiles = get_known_apparmor_profiles()
                if profile not in known_profiles:
                    print(f"⚠️ Warning: aa_profile '{profile}' does not match any profile in /etc/apparmor.d/")
                    print("\n   👉 To fix this, create or rename the profile file or set 'aa_profile: none'.\n")

        for key in sandbox.keys():
            if key not in ({"type"} | required | optional):
                print(f"❌ Error: Unknown key 'sandbox.{key}' for Firejail.\n")
                sys.exit(1)

    def validate_bwrap(sandbox):
        allowed_keys = {"type"} | bwrap_boolean_flags.keys() | bwrap_list_flags.keys() | bwrap_key_value_flags.keys()

        for key in sandbox.keys():
            if key not in allowed_keys:
                print(f"❌ Error: Unknown key 'sandbox.{key}' in Bwrap config.\n")
                sys.exit(1)

        for key in bwrap_boolean_flags:
            if key in sandbox and not isinstance(sandbox[key], bool):
                print(f"❌ Error: 'sandbox.{key}' must be a boolean.\n")
                sys.exit(1)

        for key in bwrap_list_flags:
            if key in sandbox:
                if not isinstance(sandbox[key], list):
                    print(f"❌ Error: 'sandbox.{key}' must be a list.\n")
                    sys.exit(1)

                if key == "bwrap_env":
                    for item in sandbox[key]:
                        if not isinstance(item, dict) or len(item) != 1:
                            print("❌ Error: Each item in 'sandbox.bwrap_env' must be a dictionary with a single key-value pair.\n")
                            sys.exit(1)
                        for k, v in item.items():
                            if not isinstance(k, str) or not isinstance(v, str):
                                print("❌ Error: 'sandbox.bwrap_env' entries must have string key-value pairs.\n")
                                sys.exit(1)

                elif key == "bwrap_unset-env":
                    if not all(isinstance(v, str) for v in sandbox[key]):
                        print("❌ Error: 'sandbox.bwrap_unset-env' entries must be strings.\n")
                        sys.exit(1)

        for key in bwrap_key_value_flags:
            if key in sandbox and not isinstance(sandbox[key], (str, int)):
                print(f"❌ Error: 'sandbox.{key}' must be a string or integer.\n")
                sys.exit(1)

    # -- Firejail validation (disallow GUI apps).

    if sandbox_type == "firejail":
        validate_firejail(sandbox)
        if integration.get("gui_app"):
            print("❌ Error: Firejail sandboxing is only supported for CLI apps.\n")
            print("👉 Use Bubblewrap (bwrap) for GUI applications instead.\n")
            sys.exit(1)
    elif sandbox_type == "bwrap":
        validate_bwrap(sandbox)

    # -- Validate runtime.

    allowed_runtimes = {"classic", "go", "uruntime"}
    runtime = config["buildinfo"].get("runtime", "classic")

    if not isinstance(runtime, str) or runtime not in allowed_runtimes:
        print(f"❌ Error: 'buildinfo.runtime' must be one of: {', '.join(sorted(allowed_runtimes))}.\n")
        sys.exit(1)

    print("✅ YAML validation passed successfully.\n")
