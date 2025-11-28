#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os
import platform
import re
import shutil
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Event

import requests
from tqdm import tqdm

from .exceptions import ConfigError, DownloadError


# -- Define base directories.

cache_dir = Path.home() / ".cache/nx-apphub-cli"
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
            raise DownloadError(f"Error downloading appimagetool: {e}") from e

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
                raise DownloadError(f"Could not find a matching go-appimagetool build for architecture: {arch}")

        except requests.RequestException as e:
            raise DownloadError(f"Error downloading Go-based appimagetool: {e}") from e

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
            raise DownloadError(f"Error downloading uruntime: {e}") from e

    return uruntime_path


def concurrent_downloads(dependencies, base_repos, ppa_repos, cache_name):
    from .downloader import get_latest_deb
    from .extractor import extract_deb

    if not dependencies:
        print("📦 No dependencies listed.")
        return

    print(f"📥 Downloading {len(dependencies)} dependencies:\n")

    download_tasks = []
    for dep in dependencies:
        if isinstance(dep, dict):
            pkg_name = dep["name"]
            repo_id = dep.get("repo")
            if repo_id:
                repo_list = [ppa_repos.get(repo_id)]
                if repo_list[0] is None:
                    raise ConfigError(f"Unknown repo ID: '{repo_id}' for package: '{pkg_name}'.")
            else:
                repo_list = base_repos
        else:
            pkg_name = dep
            repo_list = base_repos

        download_tasks.append((pkg_name, repo_list))

    terminal_width = shutil.get_terminal_size((80, 20)).columns

    try:
        with tqdm(
            total=len(download_tasks),
            desc="    ⏬ Fetching PKGs",
            unit="pkg",
            ncols=terminal_width,
            dynamic_ncols=False,
            bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} • {rate_fmt:<14}",
            leave=True
        ) as progress:
            with ThreadPoolExecutor(max_workers=3) as executor:
                log_lock = Lock()
                stop_event = Event()

                future_to_pkg = {
                    executor.submit(get_latest_deb, pkg_name, repo_list, cache_name, log_lock, stop_event=stop_event): pkg_name
                    for pkg_name, repo_list in download_tasks
                }

                has_failed = False
                first_exception = None

                for future in as_completed(future_to_pkg):
                    try:
                        deb_path = future.result()

                        if has_failed:
                            continue

                        if deb_path:
                            extract_deb(deb_path, cache_name)

                        progress.update(1)

                    except Exception as e:
                        if not has_failed:
                            has_failed = True
                            first_exception = e
                            stop_event.set()
                            executor.shutdown(wait=False, cancel_futures=True)

                            os.kill(os.getpid(), signal.SIGINT)

                if has_failed:
                    progress.close()
                    cleanup_cache(cache_name)
                    raise DownloadError(f"AppImage build failed! {first_exception}") from first_exception

    except KeyboardInterrupt:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except NameError:
            pass

        cleanup_cache(cache_name)
        raise
