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

def extract_deb(deb_path, package_name, quiet=False):
    """Extracts a .deb package into its designated AppDir."""
    
    package_dir = Path.home() / ".cache/nx-apphub-cli" / package_name
    app_dir = package_dir / "AppDir"
    deb_dir = package_dir / "debs"

    app_dir.mkdir(parents=True, exist_ok=True)
    
    temp_dir = deb_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"Extracting {deb_path}...")

    try:
        # -- Extract control, data, and metadata from the .deb package.

        subprocess.run(["ar", "x", deb_path], cwd=temp_dir, check=True)

        # -- Detect the correct data archive file.

        archive_files = list(temp_dir.glob("data.tar.*"))
        if not archive_files:
            print(f"Error: No valid data archive found in {deb_path}.")
            return

        data_archive = archive_files[0]

        # -- Extract the correct archive type.
    
        if data_archive.suffix == ".xz":
            subprocess.run(["tar", "xf", str(data_archive), "-C", str(app_dir)], check=True)
        elif data_archive.suffix == ".gz":
            subprocess.run(["tar", "xzf", str(data_archive), "-C", str(app_dir)], check=True)
        elif data_archive.suffix == ".zst":
            decompressed_archive = temp_dir / "data.tar"
            subprocess.run(["unzstd", "-d", str(data_archive), "-o", str(decompressed_archive)], check=True)
            subprocess.run(["tar", "xf", str(decompressed_archive), "-C", str(app_dir)], check=True)
        else:
            print(f"Error: Unsupported archive format in {deb_path}.")
            return

        if not quiet:
            print(f"Extracted {deb_path} successfully.")

        # -- Ensure that libraries are correctly moved without overwriting existing ones.

        lib_dir = app_dir / "usr/lib/"
        lib_dir.mkdir(parents=True, exist_ok=True)

        for extracted_file in (app_dir / "lib").glob("*.so*"):
            target_file = lib_dir / extracted_file.name
            if not target_file.exists():
                shutil.move(str(extracted_file), str(target_file))
                if not quiet:
                    print(f"Moved {extracted_file} → {target_file}")

    except subprocess.CalledProcessError as e:
        print(f"Error: Extraction failed for {deb_path}. {e}")
        return
    
    finally:
        shutil.rmtree(temp_dir)
