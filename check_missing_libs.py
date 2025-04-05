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
from pathlib import Path

def find_missing_libs(appdir):
    appdir = Path(appdir).resolve()
    missing = {}

    for root, dirs, files in os.walk(appdir):
        for file in files:
            full_path = Path(root) / file

            #  -- Check if file is executable or a .so* library.

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

def main():
    appdir = os.environ.get("APPDIR", os.path.expanduser("~/.cache/nx-apphub-cli/inkscape/AppDir"))
    print(f"🔍 Scanning AppDir: {appdir}\n")

    missing = find_missing_libs(appdir)

    if not missing:
        print("✅ No missing shared libraries found.")
        return

    print("❌ Missing shared libraries:\n")
    for lib, paths in sorted(missing.items()):
        print(f"{lib}")
        for path in sorted(set(paths)):
            print(f"  ↪ {path}")
        print()

    print("📦 Add these to your YAML 'deps:' if applicable.\n")

if __name__ == "__main__":
    main()
