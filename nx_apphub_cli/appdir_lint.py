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


def suggest_providing_packages(missing_libs, repos):
    suggestions = {}
    seen_contents = set()

    if isinstance(repos, dict):
        base_repos = repos.get("base", [])
        ppa_repos = repos.get("ppas", [])
        repos = base_repos + ppa_repos

    lib_patterns = {lib: re.compile(rf"/{re.escape(lib)}(\s|$)") for lib in missing_libs}

    known_mirrors = {
        "debian": [
            "https://ftp.debian.org/debian",
            "https://uk.mirrors.clouvider.net/debian",
            "https://atl.mirrors.clouvider.net/debian",
        ],
        "ubuntu": [
            "https://archive.ubuntu.com/ubuntu",
            "https://security.ubuntu.com/ubuntu",
            "https://mirrors.edge.kernel.org/ubuntu/ubuntu",
        ],
        "ubuntu-ports": [
            "https://ports.ubuntu.com/ubuntu-ports",
        ],
        "devuan": [
            "http://deb.devuan.org/merged",
        ],
        "kde-neon": [
            "https://origin.archive.neon.kde.org/stable",
        ],
        # nitrux is intentionally excluded — it has no Contents files
    }

    for repo in repos:
        distro = repo.get("distro", "").lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            continue

        if distro not in known_mirrors:
            continue

        for mirror in known_mirrors[distro]:
            for component in components:
                contents_url = f"{mirror}/dists/{release}/{component}/Contents-{arch}.gz"

                if contents_url in seen_contents:
                    continue
                seen_contents.add(contents_url)

                try:
                    response = requests.get(contents_url, timeout=15)
                    response.raise_for_status()
                    with gzip.open(BytesIO(response.content), 'rt', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            parts = line.strip().rsplit(None, 1)
                            if len(parts) != 2:
                                continue
                            path, pkg = parts
                            for lib, pattern in lib_patterns.items():
                                if pattern.search(path):
                                    suggestions.setdefault(lib, set()).add(pkg)
                except Exception:
                    continue

    return suggestions


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
        print(f"\n❌ Invalid or incomplete AppDir: {appdir_path}\n")
        return

    print(f"🔍 Scanning AppDir: {appdir_path}\n")
    missing = find_missing_libs(appdir_path)

    if not missing:
        print("✅ No missing shared libraries found.\n")
        return

    print("❌ Missing shared libraries:\n")
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
