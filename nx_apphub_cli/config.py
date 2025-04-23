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
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            print(f"Error: {config_path} is empty or invalid.")
            sys.exit(1)

        return data

    except yaml.YAMLError as e:
        print(f"YAML Parsing Error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
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
    
    sandbox = config.get("sandbox", {})
    if not isinstance(sandbox, dict):
        raise ValueError("sandbox must be a dictionary")

    sandbox_type = sandbox.get("type", "none")
    if sandbox_type not in ("bwrap", "firejail", "none"):
        raise ValueError("sandbox.type must be one of: bwrap, firejail, none")

    for key in bwrap_boolean_flags:
        if key in sandbox and not isinstance(sandbox[key], bool):
            raise ValueError(f"sandbox.{key} must be a boolean")

    for key in bwrap_list_flags:
        if key in sandbox and not isinstance(sandbox[key], list):
            raise ValueError(f"sandbox.{key} must be a list")

    for key in bwrap_key_value_flags:
        if key in sandbox and not isinstance(sandbox[key], (str, int)):
            raise ValueError(f"sandbox.{key} must be a string or integer")

    if sandbox_type == "firejail":
        if "aa_profile" in sandbox:
            if not isinstance(sandbox["aa_profile"], str):
                raise ValueError("sandbox.aa_profile must be a string")
            
            profile = sandbox["aa_profile"]
            if profile != "none":
                known_profiles = get_known_apparmor_profiles()
                if profile not in known_profiles:
                    print(f"⚠️ Warning: aa_profile '{profile}' does not match any profile in /etc/apparmor.d/")
                    print("\n   👉 To fix this, create or rename the profile file or set 'aa_profile: none'.\n")

    print("✅ YAML validation passed successfully.\n")
