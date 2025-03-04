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

import sys
import argparse
from nx_apphub_cli.config import load_yaml_config, setup_directories
from nx_apphub_cli.downloader import get_latest_deb
from nx_apphub_cli.extractor import extract_deb
from nx_apphub_cli.appimage import prepare_appimage

def main():
    parser = argparse.ArgumentParser(description="NX AppHub CLI - Convert .deb packages to AppImages")
    parser.add_argument("config", metavar="CONFIG", type=str, help="Path to YAML configuration file")
    args = parser.parse_args()

    # -- Load configuration file.

    config = load_yaml_config(args.config)

    # -- Get package name.

    package_name = config["buildinfo"]["name"]

    # -- Ensure necessary directories exist.

    setup_directories(package_name)

    # -- Get dependencies list (default to empty list if missing).

    dependencies = config["buildinfo"].get("deps", [])

    # -- Get list of repositories (default to empty list if missing).

    repos = config["buildinfo"].get("distrorepo", [])

    for dep in dependencies:
        deb_path = get_latest_deb(dep, repos, package_name)
        extract_deb(deb_path, package_name)

    # -- Build the AppImage.

    prepare_appimage(config)
    print("AppImage creation complete!")

if __name__ == "__main__":
    main()
