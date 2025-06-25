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
import platform
import shutil
from pathlib import Path
import re

import requests


# -- Define base directories.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"
appimagetool_path = local_bin / "appimagetool"
go_appimagetool_path = local_bin / "go-appimagetool"
uruntime_path = local_bin / "uruntime"


# -- Utility functions.

def ensure_executable(path):
    """Ensure a file is executable."""
    os.chmod(path, 0o755)


def get_architecture():
    """Return the system architecture for downloading the correct AppImageTool version."""
    arch_map = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    return arch_map.get(platform.machine(), "x86_64")


def cleanup_cache(package_name=None):
    """Remove the cache directory for a specific package or skip full cache cleanup."""

    cache_dir = Path.home() / ".cache/nx-apphub-cli"

    if package_name:
        target_dir = cache_dir / package_name

        if target_dir.exists():
            print(f"\n🧹 Cleaning up build cache for: {package_name}...\n")
            shutil.rmtree(target_dir, ignore_errors=True)
        else:
            print(f"\n🚨 Warning: No build cache found for: {package_name}. Skipping cleanup.\n")
    else:
        print("\nℹ️ Skipping full cache cleanup. Only removing package-specific cache.")


def get_appimagetool(quiet=True):
    """Ensure appimagetool is available by downloading it if missing."""
    if not appimagetool_path.exists():
        if not quiet:
            print("appimagetool not found! Downloading from GitHub...")
        local_bin.mkdir(parents=True, exist_ok=True)

        # -- Detect system architecture and download the correct executable.

        arch = get_architecture()
        tool_url = f"https://github.com/AppImage/appimagetool/releases/latest/download/appimagetool-{arch}.AppImage"

        try:
            response = requests.get(tool_url, stream=True, timeout=20)
            response.raise_for_status()

            with open(appimagetool_path, "wb") as tool_file:
                for chunk in response.iter_content(1024):
                    tool_file.write(chunk)

            appimagetool_path.chmod(0o755)
            if not quiet:
                print(f"✅  appimagetool downloaded and saved to {appimagetool_path}")

        except requests.RequestException as e:
            print(f"❌ Error downloading appimagetool: {e}")
            print()
            exit(1)
        
    return appimagetool_path


def get_go_appimagetool(quiet=True):
    """Ensure go-appimagetool is available by downloading it if missing."""
    if not go_appimagetool_path.exists():
        if not quiet:
            print("go-appimagetool not found! Downloading from GitHub...")
        local_bin.mkdir(parents=True, exist_ok=True)

        arch = get_architecture()

        latest_url = "https://github.com/probonopd/go-appimage/releases/expanded_assets/continuous"
        try:
            response = requests.get(latest_url, timeout=20)
            response.raise_for_status()

            pattern = rf'href="([^"]*appimagetool-.*-{arch}\.AppImage)"'
            match = re.search(pattern, response.text)

            if match:
                download_url = f"https://github.com{match.group(1)}"
                response = requests.get(download_url, stream=True, timeout=20)
                response.raise_for_status()

                with open(go_appimagetool_path, "wb") as tool_file:
                    for chunk in response.iter_content(1024):
                        tool_file.write(chunk)

                go_appimagetool_path.chmod(0o755)
                if not quiet:
                    print(f"✅  go-appimagetool downloaded and saved to {go_appimagetool_path}")

            else:
                print(f"❌ Error: Could not find a matching go-appimagetool build for architecture: {arch}")
                print()
                exit(1)

        except requests.RequestException as e:
            print(f"❌ Error downloading Go-based appimagetool: {e}")
            print()
            exit(1)

    return go_appimagetool_path


def get_uruntime(quiet=True):
    """Ensure uruntime is available by downloading it if missing."""

    if not uruntime_path.exists():
        if not quiet:
            print("❌ Error: uruntime not found! Downloading from GitHub...")

        local_bin.mkdir(parents=True, exist_ok=True)

        arch = get_architecture()
        uruntime_filename = f"uruntime-appimage-dwarfs-{arch}"

        tool_url = f"https://github.com/VHSgunzo/uruntime/releases/latest/download/{uruntime_filename}"

        try:
            response = requests.get(tool_url, stream=True, timeout=20)
            response.raise_for_status()

            with open(uruntime_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            uruntime_path.chmod(0o755)
            if not quiet:
                print(f"✅  uruntime downloaded and saved to {uruntime_path}")

        except requests.RequestException as e:
            print(f"❌ Error downloading uruntime: {e}")
            print()
            sys.exit(1)

    return uruntime_path


def infer_lint_metadata_from_yaml(yaml_path):
    from pathlib import Path
    import yaml

    path = Path(yaml_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    result = {
        "distro": None,
        "release": None,
        "components": [],
    }

    distros = config.get("buildinfo", {}).get("distrorepo")

    if isinstance(distros, list):
        if distros:
            result["distro"] = distros[0].get("distro")
            result["release"] = distros[0].get("release")
            result["components"] = distros[0].get("components", ["main"])
    elif isinstance(distros, dict):
        base = distros.get("base", [])
        if base:
            result["distro"] = base[0].get("distro")
            result["release"] = base[0].get("release")
            result["components"] = base[0].get("components", ["main"])

    return result
