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

def run_linter(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Check missing shared libraries in an AppDir.")
        parser.add_argument("appdir", type=str, help="Path to the AppDir or squashfs-root directory")
        args = parser.parse_args()

    appdir_path = detect_appdir(args.appdir)
    if not is_valid_appdir(appdir_path):
        print(f"❌ Invalid or incomplete AppDir: {appdir_path}")
        return

    print(f"\n🔍 Scanning AppDir: {appdir_path}\n")
    missing = find_missing_libs(appdir_path)

    if not missing:
        print("✅ No missing shared libraries found.")
        return

    print("❌ Missing shared libraries:\n")
    for lib, sources in sorted(missing.items()):
        print(f"{lib} — required by:")
        for src in sorted(set(sources)):
            print(f"  ↪ {src}")
        print()
