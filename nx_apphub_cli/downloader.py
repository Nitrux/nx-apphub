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

import requests
from pathlib import Path
import re
import sys


# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"

def get_latest_deb(pkg_name, repos, package_name):
    """Download the latest .deb package for the given pkg_name from a list of repos."""

    package_dir = cache_dir / package_name
    deb_dir = package_dir / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        distro = repo['distro'].lower()
        release = repo['release']
        arch = repo['arch']

        if distro not in ["debian", "ubuntu"]:
            print(f"Invalid distro: {distro}. Supported: Debian, Ubuntu.")
            continue

        # -- Construct repo URL for the package.

        if distro == "ubuntu":
            repo_url = f"https://packages.ubuntu.com/{release}/{arch}/{pkg_name}/download"
        else:
            repo_url = f"https://packages.debian.org/{release}/{arch}/{pkg_name}/download"

        print(f"Checking repository: {repo_url}")

        try:
            response = requests.get(repo_url, timeout=10)
            response.raise_for_status()

            deb_url = extract_deb_url(response.text)
            if not deb_url:
                print(f"Warning: No .deb URL found for {pkg_name} in {repo_url}")
                continue

            # Download .deb package
            deb_path = deb_dir / f"{pkg_name}.deb"
            download_file(deb_url, deb_path)
            return deb_path

        except requests.RequestException as e:
            print(f"Error accessing {repo_url}: {e}")
            continue

    print(f"Failed to find package: {pkg_name} in any repository.")
    sys.exit(1)


def extract_deb_url(html):
    """Extracts the .deb download URL from the HTML page."""
    match = re.search(r'"(https?://[^"]+\.deb)"', html)
    return match.group(1) if match else None


def download_file(url, dest):
    """Downloads a file from the given URL and saves it to dest."""
    print(f"Downloading {url} to {dest}")

    try:
        response = requests.get(url, stream=True, timeout=20)
        response.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"Successfully downloaded {dest}")

    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        sys.exit(1)
