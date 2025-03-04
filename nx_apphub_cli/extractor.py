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

import subprocess
import shutil
from pathlib import Path


# -- Extract .deb files into the correct package directory.

def extract_deb(deb_path, package_name):
    """Extracts a .deb package into its designated AppDir."""
    
    # -- Define per-package directories dynamically.

    package_dir = Path.home() / ".cache/nx-apphub-cli" / package_name
    app_dir = package_dir / "AppDir"
    deb_dir = package_dir / "debs"

    # -- Ensure AppDir exists.

    app_dir.mkdir(parents=True, exist_ok=True)
    
    # -- Extract the .deb package.

    temp_dir = deb_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {deb_path} to {app_dir}...")

    try:
        # -- Extract .deb using `ar` and `tar`.

        subprocess.run(["ar", "x", deb_path], cwd=temp_dir, check=True)

        # -- Determine if data archive is `data.tar.xz` or `data.tar.gz`.

        if (temp_dir / "data.tar.xz").exists():
            data_archive = "data.tar.xz"
        elif (temp_dir / "data.tar.gz").exists():
            data_archive = "data.tar.gz"
        else:
            print(f"Error: No valid data archive found in {deb_path}.")
            return

        subprocess.run(["tar", "xf", data_archive, "-C", str(app_dir)], cwd=temp_dir, check=True)

        print(f"Successfully extracted {deb_path} to {app_dir}")

        # -- Ensure that libraries are correctly moved.

        lib_dir = app_dir / "usr/lib/"
        lib_dir.mkdir(parents=True, exist_ok=True)

        for extracted_file in (app_dir / "lib").glob("*.so*"):
            shutil.move(str(extracted_file), str(lib_dir))

        print(f"Moved libraries to {lib_dir}")

    except subprocess.CalledProcessError as e:
        print(f"Extraction failed: {e}")
        return
    
    finally:
        # -- Cleanup temporary extraction directory.

        shutil.rmtree(temp_dir)
