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

import gzip
import re
import requests
import sys
from pathlib import Path


# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Mirors for supported distributions.

debian_mirrors = [
    "http://deb.debian.org/debian",
    "http://ftp.debian.org/debian",
    "http://ftp.uk.debian.org/debian",
    "http://ftp.us.debian.org/debian",
    "http://ftp.de.debian.org/debian",
]

ubuntu_mirrors = [
    "http://archive.ubuntu.com/ubuntu",
    "http://security.ubuntu.com/ubuntu",
]

devuan_mirrors = [
    "http://deb.devuan.org/devuan",
    "http://devuan.ipacct.com/devuan",
    "http://mirror.vpgrp.io/devuan",
    "http://mirrors.dotsrc.org/devuan",
]

kde_neon_mirrors = [
    "https://archive.neon.kde.org/user",
]

nitrux_mirrors = [
    "https://packagecloud.io/nitrux/mauikit/debian",
]

def get_latest_deb(pkg_name, repos, package_name, quiet=True):
    """Download the latest .deb package for the given pkg_name from mirrors using Packages.gz metadata."""
    
    package_dir = cache_dir / package_name
    deb_dir = package_dir / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)

    if not repos:
        print(f"❌ Error: No valid repositories provided for {pkg_name}. Aborting.")
        sys.exit(1)

    for repo in repos:
        distro = repo['distro'].lower()
        release = repo['release']
        arch = repo['arch']

        if distro not in ["debian", "ubuntu", "devuan", "kde-neon", "nitrux"]:
            if not quiet:
                print(f"Invalid distro: {distro}. Supported: Debian, Ubuntu, Devuan, KDE Neon, Nitrux.")
            continue

        # -- Select the correct mirror list.

        if distro == "debian":
            mirror_list = debian_mirrors
        elif distro == "ubuntu":
            mirror_list = ubuntu_mirrors
        elif distro == "devuan":
            mirror_list = devuan_mirrors
        elif distro == "kde-neon":
            mirror_list = kde_neon_mirrors
        elif distro == "nitrux":
            mirror_list = nitrux_mirrors
        else:
            continue

        for mirror in mirror_list:
            pkg_info = fetch_package_metadata(mirror, release, arch, pkg_name)
            if pkg_info:
                deb_url = f"{mirror}/{pkg_info}"
                
                if not quiet:
                    print(f"Downloading {pkg_name} from {deb_url}...")

                return download_file(deb_url, deb_dir / f"{pkg_name}.deb", quiet=quiet)

    print(f"❌ Error: Failed to find package '{pkg_name}' in any repository.")
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
        print(f"❌ Error: Failed to fetch metadata from {packages_url}: {e}")

    return None


def download_file(url, dest_path, quiet=True):
    """Download a file from a URL and save it to the given destination path."""
    import requests

    if not quiet:
        print(f"Downloading {url} to {dest_path}")

    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"❌ Error: Failed to download {url}. HTTP {response.status_code}")
        return None

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)

    if not quiet:
        print(f"Successfully downloaded {dest_path}")

    return dest_path
