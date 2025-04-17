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
import sys
from pathlib import Path

import requests

from .utils import cleanup_cache


# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Mirors for supported distributions.

debian_mirrors = [
    "https://deb.debian.org/debian",
    "https://ftp.debian.org/debian",
    "https://ftp.uk.debian.org/debian",
    "https://ftp.us.debian.org/debian",
    "https://ftp.de.debian.org/debian",
]

ubuntu_mirrors = [
    "https://archive.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
]

devuan_mirrors = [
    "https://deb.devuan.org/devuan",
    "https://devuan.ipacct.com/devuan",
    "https://mirror.vpgrp.io/devuan",
    "https://mirrors.dotsrc.org/devuan",
]

kde_neon_mirrors = [
    "https://archive.neon.kde.org/user",
]

nitrux_mirrors = [
    "https://packagecloud.io/nitrux/mauikit/debian",
    "https://packagecloud.io/nitrux/depot/debian",
]

debian_snapshots = [
    "https://snapshot.debian.org/archive/debian/20250101T083404Z",
]


def get_latest_deb(pkg_name, repos, package_name, quiet=True):
    """Download the latest .deb package for the given pkg_name from mirrors using Packages.gz metadata."""

    # -- Packages to exclude from downloading.

    excluded_packages = {
        "libc6", 
        "libglib2.0-0t64", 
        "libglib2.0-0", 
        "libgcc-s1", 
        "libstdc++6",
        "libglx0",
        "libegl1",
        "libgl1"
    }

    # -- Skip downloading if the package is in the exclusion list.

    if pkg_name in excluded_packages:
        print(f"\n\n        ⚠️ Skipping {pkg_name}: This package is a core system library and should not be bundled in the AppImage.\n")
        return None
    
    package_dir = cache_dir / package_name
    deb_dir = package_dir / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)

    if not repos:
        print(f"❌ Error: No valid repositories provided for {pkg_name}. Aborting.\n")
        sys.exit(1)

    for repo in repos:
        if "ppa" in repo:
            ppa = repo["ppa"].strip()
            if not ppa or "/" not in ppa:
                print(f"❌ Invalid PPA format: {ppa}. Expected format: '<user>/<ppa-name>'.")
                continue
            try:
                distro = repo["distro"].lower()
                release = repo["release"]
                arch = repo["arch"]
            except KeyError as e:
                print(f"❌ Error: Missing required key '{e.args[0]}' in repository entry: {repo}")
                continue

            ppa_url = f"https://ppa.launchpadcontent.net/{ppa}/{distro}"

            pkg_info = fetch_package_metadata(ppa_url, release, arch, pkg_name)
            if pkg_info:
                deb_url = f"{ppa_url}/{pkg_info}"
                if not quiet:
                    print(f"Downloading {pkg_name} from {deb_url}...")
                return download_file(deb_url, deb_dir / f"{pkg_name}.deb", quiet=quiet)

        else:
            distro = repo['distro'].lower()
            release = repo['release']
            arch = repo['arch']

            if distro not in ["debian", "ubuntu", "devuan", "kde-neon", "nitrux", "debian-snapshots"]:
                if not quiet:
                    print(f"Invalid distro: {distro}. Supported: Debian, Ubuntu, Devuan, KDE Neon.")
                continue

            # -- Select the correct mirror list.

            # -- NOTE: The options "nitrux" and "debian-snapshots" are purposefully undocumented because I'm only adding them to test
            # -- building the MauiKit AppImages using the packages in our repositories and the packages used to compile them, which is the whole reason I made this, lol.

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
            elif distro == "debian-snapshots":
                mirror_list = debian_snapshots
            else:
                continue

            for mirror in mirror_list:
                components = repo.get("components", ["main"])

                for component in components:
                    pkg_info = fetch_package_metadata(mirror, release, arch, pkg_name, component)
                    if pkg_info:
                        deb_url = f"{mirror}/{pkg_info}"
                        if not quiet:
                            print(f"Downloading {pkg_name} from {deb_url}...")
                        return download_file(deb_url, deb_dir / f"{pkg_name}.deb", quiet=quiet)

    sys.stdout.write("\n\n")
    sys.stdout.flush()
    cleanup_cache(package_name)
    raise RuntimeError(f"\n❌ Error: Package '{pkg_name}' could not be found in any repository.\n")


def fetch_package_metadata(mirror, release, arch, pkg_name, component="main"):
    """Fetch the latest package path from Packages.gz metadata."""
    packages_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/Packages.gz"

    try:
        response = requests.get(packages_url, timeout=20, stream=True)
        response.raise_for_status()

        with gzip.open(response.raw, "rt", encoding="utf-8", errors="ignore") as f:
            current_package = None
            filename = None

            for line in f:
                line = line.strip()

                if line.startswith("Package: "):
                    current_package = line.split("Package: ")[1]

                elif line.startswith("Filename: ") and current_package == pkg_name:
                    filename = line.split("Filename: ")[1]
                    return filename

    except requests.RequestException as e:
        print(f"\n❌ Error: Failed to fetch metadata from {packages_url}: {e}\n")

    return None


def download_file(url, dest_path, quiet=True):
    """Download a file from a URL and save it to the given destination path."""
    import requests

    if not quiet:
        print(f"Downloading {url} to {dest_path}")

    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"\n❌ Error: Failed to download {url}. HTTP {response.status_code}\n")
        return None

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)

    if not quiet:
        print(f"Successfully downloaded {dest_path}")

    return dest_path
