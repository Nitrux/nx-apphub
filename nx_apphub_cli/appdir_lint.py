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
import sys
import subprocess
import gzip
from io import BytesIO
from pathlib import Path
import requests
import yaml
import re
from elftools.elf.elffile import ELFFile
# <---
# --->
def detect_appdir(path):
    """Normalize path and auto-detect if it's a squashfs-root."""
    path = Path(path).expanduser().resolve()
    if path.name == "squashfs-root":
        return path
    if (path / "squashfs-root").is_dir():
        return path / "squashfs-root"
    return path


def is_valid_appdir(path):
    """Check if the path is a plausible AppDir or squashfs-root."""
    return path.is_dir() and path.name == "squashfs-root" and (path / "AppRun").is_file()


def is_elf(path):
    """Return True if the file is an ELF binary."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:
        return False


def library_exists_in_appdir(libname, appdir):
    for root, dirs, files in os.walk(appdir):
        for file in files:
            if file == libname or file.startswith(libname + "."):
                return True
    return False


def find_missing_libs(appdir):
    """Scan the AppDir for executables or shared objects with missing libraries."""
    missing = {}
    for root, dirs, files in os.walk(appdir):
        for file in files:
            full_path = Path(root) / file
            if not is_elf(full_path):
                continue
            try:
                result = subprocess.check_output(['ldd', str(full_path)], stderr=subprocess.DEVNULL, text=True)
            except subprocess.CalledProcessError:
                continue
            for line in result.splitlines():
                if '=> not found' in line:
                    lib = line.split('=>')[0].strip()
                    if library_exists_in_appdir(lib, appdir):
                        continue
                    missing.setdefault(lib, []).append(str(full_path))
    return missing


def is_valid_appdir(appdir_path):
    """Validate that the AppDir has a minimal structure."""
    if not appdir_path.is_dir():
        return False

    app_run = appdir_path / "AppRun"
    usr_dir = appdir_path / "usr"

    # -- Minimal expectations: AppRun and usr/ must exist.

    if not app_run.is_file():
        return False

    if not usr_dir.is_dir():
        return False

    return True


def suggest_providing_packages(missing_libs, repos, quiet=True):
    suggestions = {}
    seen_urls = set()

    lib_patterns = {
        lib: re.compile(rf"{re.escape(lib)}(\s|$)") for lib in missing_libs
    }

    if isinstance(repos, dict):
        repos = repos.get('base', []) + repos.get('ppas', [])

    for repo in repos:
        distro = repo.get("distro", "").lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            if not quiet:
                print(f"⚠️  Skipping invalid repo definition: {repo}")
            continue

        if distro == "debian":
            mirrors = ["https://ftp.debian.org/debian"]
            subpath = "dists"
        elif distro == "ubuntu":
            mirrors = ["https://archive.ubuntu.com/ubuntu"]
            subpath = "dists"
        elif distro == "ubuntu-ports":
            mirrors = ["https://ports.ubuntu.com/ubuntu-ports"]
            subpath = "dists"
        elif distro == "devuan":
            mirrors = ["http://deb.devuan.org/merged"]
            subpath = "dists"
        elif distro == "kde-neon":
            mirrors = ["https://origin.archive.neon.kde.org/stable"]
            subpath = "dists"
        elif distro == "nitrux":
            if not quiet:
                print("⏩ Skipping Nitrux repository (no Contents file provided).")
            continue
        else:
            if not quiet:
                print(f"⏩ Unknown distro '{distro}', skipping.")
            continue

        for mirror in mirrors:
            for component in components:
                if distro in ("debian", "devuan"):
                    url = f"{mirror}/{subpath}/{release}/{component}/Contents-{arch}.gz"
                else:
                    url = f"{mirror}/{subpath}/{release}/Contents-{arch}.gz"

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                if not quiet:
                    print(f"📥 Downloading: {url}")

                try:
                    response = requests.get(url, timeout=20)
                    response.raise_for_status()

                    if not quiet:
                        print(f"📑 Parsing: {url}\n")

                    with gzip.open(BytesIO(response.content), 'rt', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.rsplit(None, 1)
                            if len(parts) != 2:
                                continue
                            path, pkg = parts
                            for lib, pattern in lib_patterns.items():
                                if pattern.search(path):
                                    if not quiet:
                                        print(f"✅ Matched {lib} → {pkg} in {url}")
                                    suggestions.setdefault(lib, set()).add(pkg)
                    if not quiet:
                        print()
                except Exception as e:
                    if not quiet:
                        print(f"⚠️  Failed to process {url}: {e}")
                    continue

    return {lib: sorted(set(pkgs)) for lib, pkgs in suggestions.items()}


def run_linter(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Check missing shared libraries in an AppDir.")
        parser.add_argument("appdir", type=str, help="Path to the AppDir or squashfs-root directory")
        args = parser.parse_args()

    appdir_path = detect_appdir(args.appdir)

    # --- Handle uruntime symlink (squashfs-root -> AppDir).

    if appdir_path.is_symlink():
        resolved = appdir_path.resolve()
        print(f"ℹ️ squashfs-root is a symlink — resolved to: {resolved}")
        appdir_path = resolved

    if not is_valid_appdir(appdir_path):
        print(f"\n⛔ Invalid or incomplete AppDir: {appdir_path}\n")
        return

    print()
    print(f"🔍 Scanning AppDir: {appdir_path}\n")
    missing = find_missing_libs(appdir_path)

    if not missing:
        print("✅ No missing shared libraries found.\n")
        return

    print("🚨 Missing shared libraries:\n")
    for lib, sources in sorted(missing.items()):
        print(f"{lib} — required by:")
        for src in sorted(set(sources)):
            print(f"  ↪ {src}")
        print()

    # -- Load YAML config to retrieve repositories.

    yaml_path = args.yaml if hasattr(args, "yaml") else None
    if not yaml_path or not os.path.isfile(yaml_path):
        print("⚠️  No YAML config provided. Skipping package suggestions.\n")
        return

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    repos = config.get("buildinfo", {}).get("distrorepo", [])
    if isinstance(repos, dict):
        repos = repos.get("base", [])

    print("💡 Suggesting Debian packages that may provide the missing libraries...\n")
    suggestions = suggest_providing_packages(missing.keys(), repos)
    for lib in missing:
        pkgs = suggestions.get(lib)
        if pkgs:
            print(f"   ➤ {lib}: suggested packages → {', '.join(sorted(pkgs))}")
        else:
            print(f"   ➤ {lib}: no suggestion found")
    print()
