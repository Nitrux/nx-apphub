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

import requests
import gzip
import re
from pathlib import Path

cache_dir = Path.home() / ".cache/nx-apphub-cli"

debian_mirrors = [
    "http://ftp.debian.org/debian",
    "http://ftp.uk.debian.org/debian",
    "http://ftp.us.debian.org/debian",
    "http://ftp.de.debian.org/debian",
]

ubuntu_mirrors = [
    "http://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu",
]

def get_latest_deb(pkg_name, repos, package_name):
    """Download the latest .deb package for the given pkg_name from mirrors using Packages.gz metadata."""
    
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

        mirror_list = debian_mirrors if distro == "debian" else ubuntu_mirrors

        for mirror in mirror_list:
            pkg_info = fetch_package_metadata(mirror, release, arch, pkg_name)
            if pkg_info:
                deb_url = f"{mirror}/{pkg_info}"
                return download_file(deb_url, deb_dir / f"{pkg_name}.deb")

    print(f"Failed to find package: {pkg_name} in any repository.")
    sys.exit(1)


def fetch_package_metadata(mirror, release, arch, pkg_name):
    """Fetches the latest package path from Packages.gz metadata."""
    packages_url = f"{mirror}/dists/{release}/main/binary-{arch}/Packages.gz"

    try:
        response = requests.get(packages_url, timeout=10, stream=True)
        response.raise_for_status()

        with gzip.open(response.raw, "rt") as f:
            packages_data = f.read()

        # -- Extract the package filename from metadata.

        pkg_regex = rf"^Package: {pkg_name}\n(?:.*\n)*?^Filename: (\S+)"
        match = re.search(pkg_regex, packages_data, re.MULTILINE)

        if match:
            return match.group(1)

    except requests.RequestException as e:
        print(f"Error fetching metadata from {packages_url}: {e}")

    return None


def download_file(url, dest):
    """Downloads a file from the given URL and saves it to dest."""
    print(f"Downloading {url} to {dest}")

    try:
        response = requests.get(url, stream=True, timeout=20)
        response.raise_for_status()

        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"Successfully downloaded {dest}")
        return dest

    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        sys.exit(1)
