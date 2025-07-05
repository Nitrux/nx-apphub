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
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path
from threading import Lock

import requests
from debian import debian_support
from tqdm import tqdm

from .utils import cleanup_cache


# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Mirors for supported distributions.

debian_mirrors = [
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
    "https://origin.archive.neon.kde.org/stable/",
]

nitrux_mirrors = [
    "https://packagecloud.io/nitrux/mauikit/debian",
]

zbkit_mirrors = [
    "https://packagecloud.io/nitrux/zbkit/debian",
]


def get_mirrors_for_distro(distro):
    return {
        "debian": debian_mirrors,
        "ubuntu": ubuntu_mirrors,
        "ubuntu-ports": ubuntu_ports_mirrors,
        "devuan": devuan_mirrors,
        "kde-neon": kde_neon_mirrors,
        "nitrux": nitrux_mirrors,
        "zbkit": zbkit_mirrors
    }.get(distro, None)


def build_probe_tasks(repos, pkg_name, quiet):
    """
    Build probe tasks that randomly distribute mirrors to balance load,
    avoiding hitting the same mirror with multiple concurrent requests unnecessarily.
    """
    tasks = []
    for repo in repos:
        if "ppa" in repo:
            continue

        distro = repo.get("distro", "").lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            if not quiet:
                print(f"❌ Error: Missing required repo keys for {pkg_name}: {repo}")
            continue

        mirror_list = get_mirrors_for_distro(distro)
        if not mirror_list:
            if not quiet:
                print(f"⚠️ Skipping unknown distro: {distro}")
            continue

        # -- Randomize the mirror list to spread load across mirrors.

        mirror_list = mirror_list[:]  # copy to avoid side effects
        random.shuffle(mirror_list)

        # -- Only add one mirror per component at a time to reduce load.

        for component in components:
            for mirror in mirror_list:
                tasks.append((mirror, release, arch, pkg_name, component))
                break  # Only take one mirror for this component

    return tasks


def get_latest_deb(pkg_name, repos, package_name, log_lock, quiet=True):
    """Download the latest .deb package for the given pkg_name by probing all mirrors concurrently."""

    excluded_packages = {
        "dbus-user-session",
        "libc6",
        "libdrm2",
        "libegl-mesa0",
        "libegl1",
        "libgbm1",
        "libgcc-s1",
        "libgl1",
        "libgl1-mesa-dri",
        "libgl1-mesa-glx",
        "libglapi-mesa",
        "libgles2",
        "libglib2.0-0",
        "libglib2.0-0t64",
        "libglib2.0-bin",
        "libglx-mesa0",
        "libglx0",
        "libopengl0",
        "libstdc++6",
        "libsystemd0",
        "libsystemd-shared",
        "libwayland-client0",
        "libwayland-cursor0",
        "libwayland-egl1",
        "libwayland-server0",
        "mesa-libgallium",
        "mesa-vulkan-drivers",
        "sudo",
        "systemd",
        "systemd-sysv"
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

    probe_tasks = build_probe_tasks(repos, pkg_name, quiet)

    # Handle PPAs first
    for repo in repos:
        if "ppa" in repo:
            result = fetch_from_ppa(pkg_name, repo, package_name, deb_dir, quiet)
            if result:
                return result

    fetch_failures = []
    no_metadata = []
    candidates = []
    mirror_logs = []

    for mirror, release, arch, pkg_name, component in probe_tasks:
        time.sleep(random.uniform(0.05, 0.2))
        try:
            result, status_msg = fetch_package_metadata(mirror, release, arch, pkg_name, component)
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
            elif status_msg and not quiet:
                
                if "Unable to fetch metadata" in status_msg:
                    fetch_failures.append(status_msg)
                elif "No metadata" in status_msg:
                    no_metadata.append(status_msg)
                else:
                    mirror_logs.append(status_msg)

        except Exception as e:
            if not quiet:
                mirror_logs.append(f"⛔ Unhandled error for {pkg_name} from {mirror} [{component}]: {e}")

    if not quiet:
        from tqdm import tqdm
        if fetch_failures:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in fetch_failures))
        if no_metadata:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in no_metadata))
        if mirror_logs:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in mirror_logs))

    if not candidates:
        cleanup_cache(package_name)
        raise RuntimeError(f"❌ Error: Package '{pkg_name}' could not be found in any repository after probing {len(probe_tasks)} mirror/component pairs.")

    candidates.sort(key=lambda c: c["version"], reverse=True)
    best = candidates[0]

    if not quiet:
        with log_lock:
            tqdm.write("")
            tqdm.write(f"        📦 Package: {pkg_name}")
            tqdm.write(f"        🔹 Version: {best['version_str']}")
            tqdm.write(f"        🔹 Source:  {best['source']}\n")
            tqdm.write(f"        📥 Downloading: {pkg_name} from: {best['url']}...\n")

    download_errors = []

    for candidate in candidates:
        try:
            return download_file(candidate["url"], candidate["path"], quiet=quiet)
        except RuntimeError as e:
            download_errors.append(f"{pkg_name}: {e} ← {candidate['url']}")

    if not quiet and download_errors:
        from tqdm import tqdm
        tqdm.write(
            "\n" +
            "\n".join(f"        ⚠️ {msg}" for msg in download_errors) +
            "\n"
        )

    raise RuntimeError(f"⛔ All mirrors failed to download: {pkg_name}.")


def fetch_package_metadata(mirror, release, arch, pkg_name, component="main", retries=3):
    """Fetch the package filename and version from Packages.gz metadata, with retry on failure."""
    packages_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/Packages.gz"
    delay_range = (0.2, 0.6)

    for attempt in range(1, retries + 1):
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
                            return (filename, version), None

            except (OSError, EOFError, gzip.BadGzipFile) as gz_err:
                return None, f"❌ Error: Failed to decompress metadata from {packages_url}: {gz_err}"

            return None, f"⛔ No metadata for: {pkg_name} from: {mirror} [{component}]"

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(random.uniform(*delay_range))
                continue

            if isinstance(e, requests.exceptions.Timeout):
                reason = "⌛ Timeout"
            elif isinstance(e, requests.exceptions.ConnectionError):
                reason = "🔌 Connection error"
            elif isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                reason = f"HTTP {e.response.status_code}"
            else:
                reason = e.__class__.__name__

            mirror_host = urllib.parse.urlparse(packages_url).hostname
            return None, f"⭢ 🚧 Unable to fetch metadata from: {mirror_host}: {reason} (after {retries} attempts)"

    return None, f"⭢ 🚧 Unexpected error for {pkg_name} from {mirror} [{component}]"


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

        dl_chunk_size = 1024 * 1024

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=dl_chunk_size):
                if chunk:
                    f.write(chunk)

        if not quiet:
            tqdm.write(f"        🎉 Successfully downloaded: {destination}\n")

        return destination

    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            raise RuntimeError(f"🧾 HTTP {e.response.status_code}")
        elif isinstance(e, requests.exceptions.SSLError):
            raise RuntimeError("🔒 SSL error")
        elif isinstance(e, requests.exceptions.Timeout):
            raise RuntimeError("⌛ Timeout")
        elif isinstance(e, requests.exceptions.ConnectionError):
            if "NameResolutionError" in str(e):
                raise RuntimeError("🌐 DNS resolution failed")
            raise RuntimeError("🔌 Connection failed")
        else:
            raise RuntimeError(f"⚠️ {e.__class__.__name__}")


def print_grouped_logs(logs):
    """Group and print logs with visual separation by error type."""
    fetch_errors = [msg for msg in logs if "Failed to fetch metadata" in msg]
    decompress_errors = [msg for msg in logs if "Failed to decompress metadata" in msg]
    no_metadata = [msg for msg in logs if "No metadata" in msg]
    unhandled = [msg for msg in logs if msg not in fetch_errors + decompress_errors + no_metadata]

    if fetch_errors:
        print("\n" + "\n".join(f" {line}" for line in fetch_errors))

    if decompress_errors:
        print("\n" + "\n".join(f" {line}" for line in decompress_errors))

    if no_metadata:
        print("\n" + "\n".join(f" {line}" for line in no_metadata))

    if unhandled:
        print("\n" + "\n".join(f" {line}" for line in unhandled))
