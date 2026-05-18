#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import gzip
import lzma
import random
import time
from io import BytesIO
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from debian import debian_support
from rich.console import Console
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import DownloadError
from .console import print_error, print_warning

console = Console()

def set_console(new_console):
    """Set the global console for output (used by progress bars)."""
    global console
    console = new_console

# <---
# --->
# -- Base cache directory for downloads.

cache_dir = Path.home() / ".cache/nx-apphub-cli"


# -- Mirrors for supported distributions.

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
    "https://ports.ubuntu.com/ubuntu-ports",
]

devuan_mirrors = [
    "http://deb.devuan.org/merged",
]

kde_neon_mirrors = [
    "https://origin.archive.neon.kde.org/stable",
]

nitrux_mirrors = [
    "https://packagecloud.io/nitrux/mauikit/debian",
    "https://packagecloud.io/nitrux/area51/debian",
]

zbkit_mirrors = [
    "https://packagecloud.io/nitrux/zbkit/debian",
]


# -- Caching and Locks

cache_lock = Lock()
metadata_cache = {}


# -- Use retry strategy and session reuse for connection pooling.

retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=0.3,
)
adapter = HTTPAdapter(max_retries=retry_strategy)

session = requests.Session()
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


def get_mirrors_for_repo(repo, quiet=True):
    distro = str(repo.get("distro", "")).lower()

    if distro == "debian-snapshot":
        snapshot = repo.get("snapshot")
        if not snapshot:
            if not quiet:
                print_warning("Skipping debian-snapshot repo without 'snapshot' timestamp.", prefix="⚠️")
            return None
        return [f"https://snapshot.debian.org/archive/debian/{snapshot}".rstrip("/")]

    return get_mirrors_for_distro(distro)


def build_probe_tasks(repos, pkg_name, quiet):
    """
    Build probe tasks that randomly distribute mirrors to balance load,
    avoiding hitting the same mirror with multiple concurrent requests unnecessarily.
    """
    tasks = []
    for repo in repos:
        if "ppa" in repo:
            continue

        distro = str(repo.get("distro", "")).lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            if not quiet:
                print_error(f"Error: Missing required repo keys for {pkg_name}: {repo}")
            continue

        mirror_list = get_mirrors_for_repo(repo, quiet=quiet)
        if not mirror_list:
            if not quiet and distro != "debian-snapshot":
                print_warning(f"Skipping unknown distro: {distro}", prefix="⚠️")
            continue

        # -- Randomize the mirror list to spread load across mirrors.

        mirror_list = mirror_list[:]
        random.shuffle(mirror_list)

        # -- Only add one mirror per component at a time to reduce load.

        for component in components:
            for mirror in mirror_list:
                tasks.append((mirror, release, arch, pkg_name, component))

    return tasks


def get_latest_deb(pkg_name, repos, package_name, log_lock, stop_event=None, quiet=True):
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
        "systemd-sysv",
        "udev"
    }

    if pkg_name in excluded_packages:
        if not quiet:
            from .console import print_blank
            print_blank()
            print_blank()
            print_warning(f"        Skipping {pkg_name}: This package is a core system library and should not be bundled in the AppDir.", prefix="⚠️")
            print_blank()
        return None

    if stop_event and stop_event.is_set():
        raise DownloadError("Download cancelled.")

    package_dir = cache_dir / package_name
    deb_dir = package_dir / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)

    if not repos:
        raise DownloadError(f"No valid repositories provided for {pkg_name}.")

    probe_tasks = build_probe_tasks(repos, pkg_name, quiet)

    fetch_failures = []
    no_metadata = []
    candidates = []
    mirror_logs = []

    for repo in repos:
        if "ppa" in repo:
            candidate = fetch_from_ppa(pkg_name, repo, deb_dir, quiet)
            if candidate:
                candidates.append(candidate)

    def probe_mirror(task):
        if stop_event and stop_event.is_set():
            return (task, None, None, Exception("Download cancelled"))

        mirror, release, arch, _, component = task
        try:
            result, status_msg = fetch_package_metadata(mirror, release, arch, pkg_name, component, stop_event=stop_event)
            return (task, result, status_msg, None)
        except Exception as e:
            return (task, None, None, e)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(probe_mirror, task): task for task in probe_tasks}
        for future in as_completed(future_to_task):
            if stop_event and stop_event.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                raise DownloadError("Download cancelled during mirror probing.")

            mirror, _, _, pkg_name_task, component = future_to_task[future]
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
                        "path": deb_dir / f"{pkg_name_task}.deb",
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
                    if "Download cancelled" not in str(exception):
                        mirror_logs.append(f"⛔ Unhandled error for: {pkg_name_task} from: {mirror} [{component}]: {exception}")
            except Exception as e:
                if not quiet:
                    mirror_logs.append(f"⛔ Unexpected error for: {pkg_name}: {e}")

    if not quiet:
        if fetch_failures:
            console.print("\n" + "\n".join(f"        {msg}" for msg in fetch_failures))
        if no_metadata:
            console.print("\n" + "\n".join(f"        {msg}" for msg in no_metadata))
        if mirror_logs:
            console.print("\n" + "\n".join(f"        {msg}" for msg in mirror_logs))

    if not candidates:
        msg = f"Unable to find '{pkg_name}' after probing {len(probe_tasks)} mirror/component pairs. Aborting."
        if log_lock:
            with log_lock:
                console.print(f"❌ {msg}")
                console.print("")
        raise DownloadError(msg)

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
            console.print("")
            console.print(f"        📦 Package: {pkg_name}")
            console.print(f"        🔹 Version: {best['version_str']}")
            console.print(f"        🔹 Source:  {best['source']}\n")
            console.print(f"        📥 Downloading: {pkg_name} from: {best['url']}...\n")

    if stop_event and stop_event.is_set():
        raise DownloadError("Download cancelled.")

    download_errors = []

    for candidate in shuffled_candidates:
        if stop_event and stop_event.is_set(): break
        url = candidate["url"]
        path = candidate["path"]
        try:
            return download_file(url, path, quiet=quiet)
        except DownloadError as e:
            download_errors.append(f"{pkg_name}: {e} ← {url}")

    for candidate in shuffled_candidates:
        url = candidate["url"]
        path = candidate["path"]
        try:
            if not quiet:
                console.print(f"        🔁 Retrying download for: {pkg_name} from: {url}")
            return download_file(url, path, quiet=quiet)
        except DownloadError as e:
            download_errors.append(f"{pkg_name} (retry): {e} ← {url}")

    if not quiet and download_errors and log_lock:
        with log_lock:
            console.print("\n" + "\n".join(f"        ⚠️ {msg}" for msg in download_errors) + "\n")

    msg = f"All mirrors failed to download: {pkg_name}."

    if log_lock:
        with log_lock:
            console.print(f"❌ {msg}")
            console.print("")
    raise DownloadError(msg)


def fetch_package_metadata(mirror, release, arch, pkg_name, component="main", stop_event=None, retries=3):
    """Fetch the package filename and version from repository metadata, with retry and .xz fallback."""

    base_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/"
    urls_to_try = [base_url + "Packages.gz", base_url + "Packages.xz"]

    delay_range = (0.2, 0.6)
    cache_key = (mirror, release, arch, component)

    with cache_lock:
        if cache_key in metadata_cache:
            lines = metadata_cache[cache_key]
        else:
            lines = None

    if lines is None:
        for url in urls_to_try:
            if stop_event and stop_event.is_set():
                return None, "Download cancelled"

            for attempt in range(1, retries + 1):
                if stop_event and stop_event.is_set():
                    return None, "Download cancelled"

                try:
                    response = session.get(url, timeout=20, stream=True)

                    if response.status_code == 404:
                        break

                    response.raise_for_status()
                    content = response.content
                    if url.endswith(".gz"):
                        with gzip.open(BytesIO(content), "rt", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                    elif url.endswith(".xz"):
                        with lzma.open(BytesIO(content), "rt", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                    if lines:
                        with cache_lock:
                            metadata_cache[cache_key] = lines
                        break

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

                    mirror_host = urlparse(url).hostname
                    return None, f"⭢ 🚧 Unable to fetch metadata from: {mirror_host}: {reason} (after {retries} attempts)"

            if lines:
                break

    if not lines:
        return None, f"⛔ No metadata for: '{pkg_name}' from: '{mirror}' in [{component}]"

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

    return None, f"⛔ No metadata for: '{pkg_name}' from: '{mirror}' in [{component}]"


def fetch_from_ppa(pkg_name, repo, deb_dir, quiet=True):
    """Download packages from a PPA repository."""
    ppa = repo["ppa"].strip()
    if not ppa or "/" not in ppa:
        if not quiet:
            console.print(f"⛔ Invalid PPA format: {ppa}. Expected format: '<user>/<ppa-name>'.")
        return None

    distro = repo.get("distro", "ubuntu").lower()
    release = repo.get("release")
    arch = repo.get("arch")

    if not (distro and release and arch):
        if not quiet:
            console.print(f"❌ Error: Missing required repo keys for {pkg_name}: {repo}")
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
            console.print(f"⛔ Failed to fetch metadata for: {pkg_name} from: {base_url}: {e}")

    return None


def download_file(url, destination, quiet=True):
    """Download a file from the given URL to the given destination."""
    try:
        response = session.get(url, timeout=20, stream=True)
        response.raise_for_status()

        dl_chunk_size = 1024 * 1024

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=dl_chunk_size):
                if chunk:
                    f.write(chunk)

        if not quiet:
            console.print(f"        🎉 Successfully downloaded: {destination}\n")

        return destination

    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            raise DownloadError(f"🧾 HTTP {e.response.status_code}") from e
        elif isinstance(e, requests.exceptions.SSLError):
            raise DownloadError("🔒 SSL error") from e
        elif isinstance(e, requests.exceptions.Timeout):
            raise DownloadError("⌛ Timeout") from e
        elif isinstance(e, requests.exceptions.ConnectionError):
            if "NameResolutionError" in str(e):
                raise DownloadError("🌐 DNS resolution failed") from e
            raise DownloadError("🔌 Connection failed") from e
        else:
            raise DownloadError(f"⚠️ {e.__class__.__name__}") from e
