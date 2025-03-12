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
import shutil
import requests
from pathlib import Path


# -- Define base directories.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"
appimagetool_path = local_bin / "appimagetool"


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
            print(f"🧹 Cleaning up build cache for: {package_name}...")
            shutil.rmtree(target_dir, ignore_errors=True)
        else:
            print(f"⚠️ Warning: No build cache found for: {package_name}. Skipping cleanup.")
    else:
        print("ℹ️ Skipping full cache cleanup. Only removing package-specific cache.")


def ensure_appimagetool(quiet=True):
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
                print(f"appimagetool downloaded and saved to {appimagetool_path}")

        except requests.RequestException as e:
            print(f"Error downloading appimagetool: {e}")
            exit(1)
