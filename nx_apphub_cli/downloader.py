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
from debian import debian_support
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .utils import cleanup_cache


# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Mirors for supported distributions.

debian_mirrors = [
    "https://deb.debian.org/debian",
    "https://ftp.debian.org/debian",
    "https://uk.mirrors.clouvider.net/debian",
    "https://atl.mirrors.clouvider.net/debian",
    "https://ftp.tu-clausthal.de/debian",
]

ubuntu_mirrors = [
    "https://archive.ubuntu.com/ubuntu",
    "https://security.ubuntu.com/ubuntu",
    "https://mirrors.kernel.org/ubuntu",
]

ubuntu_ports_mirrors = [
    "https://ports.ubuntu.com/ubuntu-ports/",
]

devuan_mirrors = [
    "http://deb.devuan.org/merged",
]

kde_neon_mirrors = [
    "https://archive.neon.kde.org/stable",
]

nitrux_mirrors = [
    "https://packagecloud.io/nitrux/mauikit/debian",
    "https://packagecloud.io/nitrux/depot/debian",
]


def get_latest_deb(pkg_name, repos, package_name, quiet=True):
    """Download the latest .deb package for the given pkg_name by probing all mirrors concurrently."""

    excluded_packages = {
        "libc6", "libglib2.0-0t64", "libglib2.0-0", "libgcc-s1", "libstdc++6",
        "libglx0", "libegl1", "libgl1", "libgbm1", "libgl1-mesa-dri",
        "libgles2", "libdrm2"
    }

    if pkg_name in excluded_packages:
        if not quiet:
            print(f"\n\n        ⚠️ Skipping {pkg_name}: This package is a core system library and should not be bundled in the AppImage.\n")
        return None

    package_dir = cache_dir / package_name
    deb_dir = package_dir / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)

    if not repos:
        print(f"❌ Error: No valid repositories provided for {pkg_name}. Aborting.\n")
        sys.exit(1)

    probe_tasks = []

    for repo in repos:
        if "ppa" in repo:
            result = fetch_from_ppa(pkg_name, repo, package_name, deb_dir, quiet)
            if result:
                return result
            continue

        distro = repo.get("distro", "").lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            if not quiet:
                print(f"❌ Error: Missing required repo keys for {pkg_name}: {repo}")
            continue

        if distro == "debian":
            mirror_list = debian_mirrors
        elif distro == "ubuntu":
            mirror_list = ubuntu_mirrors
        elif distro == "ubuntu-ports":
            mirror_list = ubuntu_ports_mirrors
        elif distro == "devuan":
            mirror_list = devuan_mirrors
        elif distro == "kde-neon":
            mirror_list = kde_neon_mirrors
        elif distro == "nitrux":
            mirror_list = nitrux_mirrors
        else:
            if not quiet:
                print(f"⚠️ Skipping unknown distro: {distro}")
            continue

        for mirror in mirror_list:
            for component in components:
                probe_tasks.append((mirror, release, arch, pkg_name, component))

    candidates = []

    if not quiet:
        print()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_package_metadata, mirror, release, arch, pkg_name, component): (mirror, component)
            for (mirror, release, arch, pkg_name, component) in probe_tasks
        }

        mirror_logs = []

        for future in as_completed(futures):
            mirror, component = futures[future]
            try:
                result = future.result()
                if result:
                    filename, version_str = result
                    version = debian_support.Version(version_str)
                    deb_url = f"{mirror}/{filename}"
                    candidates.append({
                        "version": version,
                        "version_str": version_str,
                        "url": deb_url,
                        "path": deb_dir / f"{pkg_name}.deb",
                        "source": f"{mirror} [{component}]"
                    })
                elif not quiet:
                    mirror_logs.append(f"        ⛔ No metadata for {pkg_name} from {mirror} [{component}]")
            except Exception as e:
                if not quiet:
                    mirror_logs.append(f"        ⚠️ Failed to fetch {pkg_name} from {mirror} [{component}]: {e}")

    if not quiet and mirror_logs:
        print("\n" + "\n".join(mirror_logs))

    if not candidates:
        print()
        cleanup_cache(package_name)
        raise RuntimeError(f"\n❌ Error: Package '{pkg_name}' could not be found in any repository.\n")

    candidates.sort(key=lambda c: c["version"], reverse=True)
    best = candidates[0]

    if not quiet:
        print()
        print(f"        📦 Package: {pkg_name}")
        print(f"        🔹 Version: {best['version_str']}")
        print(f"        🔹 Source:  {best['source']}\n")
        print(f"        📥 Downloading: {pkg_name} from: {best['url']}...\n")

    return download_file(best["url"], best["path"], quiet=quiet)


def fetch_package_metadata(mirror, release, arch, pkg_name, component="main"):
    """Fetch the package filename and version from Packages.gz metadata."""
    packages_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/Packages.gz"

    try:
        response = requests.get(packages_url, timeout=20, stream=True)
        response.raise_for_status()

        try:
            with gzip.open(response.raw, "rt", encoding="utf-8", errors="ignore") as f:
                current_package = None
                filename = None
                version = None

                for line in f:
                    line = line.strip()

                    if line.startswith("Package: "):
                        current_package = line.split("Package: ")[1]
                        filename = None
                        version = None

                    elif line.startswith("Version: ") and current_package == pkg_name:
                        version = line.split("Version: ")[1]

                    elif line.startswith("Filename: ") and current_package == pkg_name:
                        filename = line.split("Filename: ")[1]

                    if current_package == pkg_name and filename and version:
                        return filename, version

        except (OSError, EOFError, gzip.BadGzipFile) as gz_err:
            print(f"\n❌ Error: Failed to decompress metadata from {packages_url}: {gz_err}\n")
            return None

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: Failed to fetch metadata from: {packages_url}: {e}\n")

    return None


def fetch_from_ppa(pkg_name, repo, package_name, deb_dir, quiet=True):
    ppa = repo["ppa"].strip()
    if not ppa or "/" not in ppa:
        print(f"❌ Invalid PPA format: {ppa}. Expected format: '<user>/<ppa-name>'.")
        return None

    distro = repo.get("distro", "ubuntu").lower()
    release = repo.get("release")
    arch = repo.get("arch")

    if not (distro and release and arch):
        print(f"❌ Error: Missing required repo keys for {pkg_name}: {repo}")
        return None

    ppa_url = f"https://ppa.launchpadcontent.net/{ppa}/{distro}"
    try:
        pkg_info = fetch_package_metadata(ppa_url, release, arch, pkg_name)
        if pkg_info:
            deb_url = f"{ppa_url}/{pkg_info}"
            if not quiet:
                print(f"📦 Downloading {pkg_name} from {deb_url}...")
            return download_file(deb_url, deb_dir / f"{pkg_name}.deb", quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"⚠️ Failed to fetch: {pkg_name} from: {ppa_url}: {e}")

    return None


def download_file(url, destination, quiet=True):
    try:
        response = requests.get(url, stream=True, timeout=20)
        response.raise_for_status()

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        if not quiet:
            print(f"        🎉 Successfully downloaded: {destination}\n")

        return destination

    except requests.RequestException as e:
        if not quiet:
            print(f"        ❌ Download failed: {e}")
        return None
