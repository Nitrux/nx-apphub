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
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from pathlib import Path
from threading import Lock

import requests
from debian import debian_support
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

from .utils import cleanup_cache
# <---
# --->
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


# -- Debounce per host.

last_access_time = {}
access_lock = Lock()
MIN_DELAY_PER_HOST = 0.3


# -- Use retry strategy and session reuse for connection pooling.

retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=0.3,
)
adapter = HTTPAdapter(max_retries=retry_strategy)

session = requests.Session()

metadata_cache = {}
session.mount("http://", adapter)
session.mount("https://", adapter)


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

        mirror_list = mirror_list[:]
        random.shuffle(mirror_list)

        # -- Only add one mirror per component at a time to reduce load.

        for component in components:
            for mirror in mirror_list:
                tasks.append((mirror, release, arch, pkg_name, component))
                break

    return tasks


def get_latest_deb(pkg_name, repos, package_name, log_lock, quiet=True):
    """Download the latest .deb package for the given pkg_name by probing all mirrors concurrently using threads."""

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
        raise RuntimeError(f"❌ Error: No valid repositories provided for {pkg_name}.")

    probe_tasks = build_probe_tasks(repos, pkg_name, quiet)

    fetch_failures = []
    no_metadata = []
    candidates = []
    mirror_logs = []

    for repo in repos:
        if "ppa" in repo:
            candidate = fetch_from_ppa(pkg_name, repo, package_name, deb_dir, quiet)
            if candidate:
                candidates.append(candidate)

    def probe_mirror(task):
        mirror, release, arch, pkg_name, component = task
        try:
            result, status_msg = fetch_package_metadata(mirror, release, arch, pkg_name, component)
            return (task, result, status_msg, None)
        except Exception as e:
            return (task, None, None, e)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(probe_mirror, task): task for task in probe_tasks}
        for future in as_completed(future_to_task):
            mirror, release, arch, pkg_name, component = future_to_task[future]
            try:
                _, result, status_msg, exception = future.result()
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
                elif exception and not quiet:
                    mirror_logs.append(f"⛔ Unhandled error for: {pkg_name} from: {mirror} [{component}]: {exception}")
            except Exception as e:
                if not quiet:
                    mirror_logs.append(f"⛔ Unexpected error for: {pkg_name}: {e}")

    if not quiet:
        if fetch_failures:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in fetch_failures))
        if no_metadata:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in no_metadata))
        if mirror_logs:
            tqdm.write("\n" + "\n".join(f"        {msg}" for msg in mirror_logs))

    if not candidates:
        raise RuntimeError(f"Unable to find '{pkg_name}' in any repository after probing {len(probe_tasks)} mirror/component pairs.")

    version_groups = defaultdict(list)
    for c in candidates:
        version_groups[c["version"]].append(c)

    sorted_versions = sorted(version_groups.keys(), reverse=True)

    shuffled_candidates = []
    for version in sorted_versions:
        mirrors = version_groups[version]
        random.shuffle(mirrors)
        shuffled_candidates.extend(mirrors)

    best = shuffled_candidates[0]

    if not quiet:
        with log_lock:
            tqdm.write("")
            tqdm.write(f"        📦 Package: {pkg_name}")
            tqdm.write(f"        🔹 Version: {best['version_str']}")
            tqdm.write(f"        🔹 Source:  {best['source']}\n")
            tqdm.write(f"        📥 Downloading: {pkg_name} from: {best['url']}...\n")

    download_errors = []

    for candidate in shuffled_candidates:
        url = candidate["url"]
        path = candidate["path"]
        try:
            return download_file(url, path, quiet=quiet)
        except RuntimeError as e:
            download_errors.append(f"{pkg_name}: {e} ← {url}")

    for candidate in shuffled_candidates:
        url = candidate["url"]
        path = candidate["path"]
        try:
            if not quiet:
                tqdm.write(f"        🔁 Retrying download for: {pkg_name} from: {url}")
            return download_file(url, path, quiet=quiet)
        except RuntimeError as e:
            download_errors.append(f"{pkg_name} (retry): {e} ← {url}")

    if not quiet and download_errors and log_lock:
        with log_lock:
            tqdm.write("\n" + "\n".join(f"        ⚠️ {msg}" for msg in download_errors) + "\n")

    raise RuntimeError(f"⛔ All mirrors failed to download: {pkg_name}.")


def fetch_package_metadata(mirror, release, arch, pkg_name, component="main", retries=3):
    """Fetch the package filename and version from Packages.gz metadata, with retry on failure."""
    packages_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/Packages.gz"
    delay_range = (0.2, 0.6)
    cache_key = (mirror, release, arch, component)

    for attempt in range(1, retries + 1):
        try:
            if cache_key in metadata_cache:
                lines = metadata_cache[cache_key]
            else:
                response = session.get(packages_url, timeout=20, stream=True)
                response.raise_for_status()

                try:
                    with gzip.open(response.raw, "rt", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        metadata_cache[cache_key] = lines
                except (OSError, EOFError, gzip.BadGzipFile) as gz_err:
                    return None, f"❌ Error: Failed to decompress metadata from {packages_url}: {gz_err}"

            current_package = None
            filename = None
            version = None

            for line in lines:
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

            mirror_host = urlparse(packages_url).hostname
            return None, f"⭢ 🚧 Unable to fetch metadata from: {mirror_host}: {reason} (after {retries} attempts)"

    return None, f"⭢ 🚧 Unexpected error for {pkg_name} from {mirror} [{component}]"


def fetch_from_ppa(pkg_name, repo, package_name, deb_dir, quiet=True):

    ppa = repo["ppa"].strip()
    if not ppa or "/" not in ppa:
        if not quiet:
            tqdm.write(f"⛔ Invalid PPA format: {ppa}. Expected format: '<user>/<ppa-name>'.")
        return None

    distro = repo.get("distro", "ubuntu").lower()
    release = repo.get("release")
    arch = repo.get("arch")

    if not (distro and release and arch):
        if not quiet:
            tqdm.write(f"❌ Error: Missing required repo keys for {pkg_name}: {repo}")
        return None

    base_url = f"https://ppa.launchpadcontent.net/{ppa}/{distro}".rstrip('/')

    try:
        result, _ = fetch_package_metadata(base_url, release, arch, pkg_name)
        if result:
            filename, version_str = result
            version = debian_support.Version(version_str)
            full_url = urljoin(base_url + "/", filename)
            deb_path = deb_dir / f"{pkg_name}.deb"

            return {
                "version": version,
                "version_str": version_str,
                "url": full_url,
                "path": deb_path,
                "source": f"{base_url} [ppa]"
            }

    except Exception as e:
        if not quiet:
            tqdm.write(f"⛔ Failed to fetch metadata for: {pkg_name} from: {base_url}: {e}")

    return None


def download_file(url, destination, quiet=True):
    try:
        response = session.get(url, timeout=20, stream=True)
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
