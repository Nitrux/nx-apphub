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
import subprocess
import argparse
from pathlib import Path
import gzip
import urllib.request

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
    return path.is_dir() and any((path / d).exists() for d in ("usr", "AppRun", "usr/bin"))


def find_missing_libs(appdir):
    """Scan the AppDir for executables or shared objects with missing libraries."""
    missing = {}
    for root, dirs, files in os.walk(appdir):
        for file in files:
            full_path = Path(root) / file
            if os.access(full_path, os.X_OK) or '.so' in full_path.name:
                try:
                    result = subprocess.check_output(['ldd', str(full_path)], stderr=subprocess.DEVNULL, text=True)
                except subprocess.CalledProcessError:
                    continue
                for line in result.splitlines():
                    if '=> not found' in line:
                        lib = line.split('=>')[0].strip()
                        missing.setdefault(lib, []).append(str(full_path))
    return missing


def get_index_url(distro, release, component):
    if distro == "ubuntu":
        return f"http://archive.ubuntu.com/ubuntu/dists/{release}/{component}/binary-amd64/Contents-amd64.gz"
    elif distro == "debian":
        return f"http://deb.debian.org/debian/dists/{release}/{component}/binary-amd64/Contents-amd64.gz"
    elif distro == "devuan":
        return f"http://pkgmaster.devuan.org/devuan/dists/{release}/{component}/binary-amd64/Contents-amd64.gz"
    else:
        raise ValueError(f"Unsupported distro: {distro}")


index_cache = {}

def search_package_for_library(libname, distro="ubuntu", release="oracular", component="main"):
    cache_key = f"{distro}:{release}:{component}"
    
    # -- Reuse cached index if available.

    if cache_key not in index_cache:
        url = get_index_url(distro, release, component)
        try:
            with urllib.request.urlopen(url) as response:
                with gzip.open(response, 'rt') as f:
                    index_cache[cache_key] = list(f)
        except Exception as e:
            print(f"⚠️  Failed to query index ({url}): {e}")
            return None

    # -- Search for the library in the cached index.

    for line in index_cache[cache_key]:
        if f"/{libname}" in line:
            return line.strip().split()[-1]

    return None


def format_yaml_deps(packages):
    return "\n".join([f"  - {pkg}" for pkg in sorted(packages)])


def main():
    parser = argparse.ArgumentParser(description="Check missing shared libraries in an AppDir and suggest package names.")
    parser.add_argument("appdir", type=str, help="Path to the AppDir or squashfs-root directory")
    parser.add_argument("--distro", type=str, default="ubuntu", choices=["ubuntu", "debian", "devuan"], help="Base distro")
    parser.add_argument("--release", type=str, default="oracular", help="Distro release")
    parser.add_argument(
        "--components",
        type=str,
        nargs="+",
        default=["main", "universe"],
        help="APT components to search (default: main universe)"
    )
    args = parser.parse_args()

    appdir_path = detect_appdir(args.appdir)
    if not is_valid_appdir(appdir_path):
        print(f"❌ Invalid or incomplete AppDir: {appdir_path}")
        return

    print(f"🔍 Scanning AppDir: {appdir_path}\n")
    missing = find_missing_libs(appdir_path)

    if not missing:
        print("✅ No missing shared libraries found.")
        return

    print("❌ Missing shared libraries:\n")
    for lib, sources in sorted(missing.items()):
        print(f"{lib}")
        for src in sorted(set(sources)):
            print(f"  ↪ {src}")
        print()
    
    found_packages = {}

    print("🔎 Attempting to map to package names...\n")
    for lib in sorted(missing):
        for component in args.components:
            pkg = search_package_for_library(lib, args.distro, args.release, component)
            if pkg:
                deb_pkg = Path(pkg).parts[0]
                found_packages[lib] = deb_pkg
                print(f"📦 {lib} → {deb_pkg}")
                break
        else:
            print(f"❌ {lib} → Package not found")

    if found_packages:
        print("\n📋 Suggested deps:\n")
        print("deps:")
        print(format_yaml_deps(set(found_packages.values())))
    else:
        print("\n⚠️ No packages were matched from the indexes.")

    print("\n📌 Add the suggested packages to your YAML file.")

if __name__ == "__main__":
    main()
