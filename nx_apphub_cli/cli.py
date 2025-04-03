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
from nx_apphub_cli.config import load_yaml_config, validate_yaml_config
from nx_apphub_cli.downloader import get_latest_deb
from nx_apphub_cli.extractor import extract_deb
from nx_apphub_cli.builder import prepare_appimage, setup_appimage_directories
from nx_apphub_cli.manager import install, remove, update, downgrade, search


def main():
    parser = argparse.ArgumentParser(
        prog="nx-apphub-cli",
        description="NX AppHub CLI — Install, update, remove, and build AppImages"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        title="Commands",
        metavar=""
    )

    # -- Management commands.

    subparser_install = subparsers.add_parser("install", help="Install one or more applications")
    subparser_install.add_argument("app_names", nargs="+", type=str, help="Name(s) of application(s) to install")

    subparser_remove = subparsers.add_parser("remove", help="Remove one or more installed applications")
    subparser_remove.add_argument("app_names", nargs="+", type=str, help="Name(s) of application(s) to remove")

    subparser_update = subparsers.add_parser("update", help="Update one or more installed applications")
    subparser_update.add_argument("app_names", nargs="+", type=str, help="Name(s) of application(s) to update")

    subparser_downgrade = subparsers.add_parser("downgrade", help="Downgrade one or more installed applications")
    subparser_downgrade.add_argument("app_names", nargs="+", type=str, help="Name(s) of application(s) to downgrade")

    subparser_search = subparsers.add_parser("search", help="Search for specific applications")
    subparser_search.add_argument("app_names", nargs="+", type=str, help="Name(s) of application(s) to search for")

    # -- Building command (requires YAML file).

    subparser_build = subparsers.add_parser("build", help="Build an AppImage from a YAML file")
    subparser_build.add_argument("config", metavar="CONFIG", type=str, help="Path to YAML configuration file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "install":
        install(args.app_names)
    elif args.command == "remove":
        remove(args.app_names)
    elif args.command == "update":
        update(args.app_names)
    elif args.command == "downgrade":
        downgrade(args.app_names)
    elif args.command == "search":
        search(args.app_names)
    elif args.command == "build":
        print(f"\n[ 🛠 Building local AppImage... ]\n")

        config = load_yaml_config(args.config)

        # -- Validate the YAML before doing anything else.

        validate_yaml_config(config)

        package_name = config["buildinfo"]["name"]

        setup_appimage_directories(package_name, config["buildinfo"]["binarypath"])

        dependencies = config["buildinfo"].get("deps", [])
        repos = config["buildinfo"].get("distrorepo", [])

        for dep in dependencies:
            deb_path = get_latest_deb(dep, repos, package_name)
            extract_deb(deb_path, package_name)

        prepare_appimage(config)
        print("\n✅ AppImage creation complete!\n")
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
