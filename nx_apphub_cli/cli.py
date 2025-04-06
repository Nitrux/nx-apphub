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

import argparse
import sys
import types
import subprocess
import yaml

from shutil import get_terminal_size
from tqdm import tqdm
from pathlib import Path

from nx_apphub_cli.builder import prepare_appimage, setup_appimage_directories
from nx_apphub_cli.config import load_yaml_config, validate_yaml_config
from nx_apphub_cli.downloader import get_latest_deb
from nx_apphub_cli.extractor import extract_deb
from nx_apphub_cli.manager import install, remove, search, show, update, downgrade
from nx_apphub_cli.utils import cleanup_cache, infer_lint_metadata_from_yaml, get_architecture
from nx_apphub_cli.appdir_lint import run_linter
from nx_apphub_cli.generator import generate_yaml, generate_description_md


def main():
    parser = argparse.ArgumentParser(
        prog="nx-apphub-cli",
        description="NX AppHub CLI — Lightweight command-line tool for managing and building applications in Nitrux"
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

    subparser_show = subparsers.add_parser("show", help="Show installed applications")

    # -- Building command (requires YAML file).

    subparser_build = subparsers.add_parser("build", help="Build an AppImage from a local YAML file")
    subparser_build.add_argument("config", metavar="CONFIG", type=str, help="Path to YAML configuration file")
    subparser_build.add_argument("--appdir-lint", metavar="APPDIR", type=str, help="Run appdir-lint after build on the specified extracted AppDir")

    subparser_generate = subparsers.add_parser("generate", help="Generate YAML template from package metadata")
    subparser_generate.add_argument("--package", required=True, help="Package name")
    subparser_generate.add_argument("--distro", required=True, help="Distribution name (e.g., ubuntu)")
    subparser_generate.add_argument("--release", required=True, help="Release codename (e.g., oracular)")
    subparser_generate.add_argument("--arch", default="amd64", help="Architecture (default: amd64)")
    subparser_generate.add_argument("--components", nargs="*", default=["main"], help="APT components (default: main)")
    subparser_generate.add_argument("--output", default="app.yml", help="Output YAML file")
    subparser_generate.add_argument("--description-output", help="Output application metadata file")


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
    elif args.command == "show":
        show()
    elif args.command == "build":
        print(f"\n[ 🛠  Building local AppImage... ]\n")

        config = load_yaml_config(args.config)

        # -- Validate the YAML before doing anything else.

        validate_yaml_config(config)

        package_name = config["buildinfo"]["name"]

        setup_appimage_directories(package_name, config["buildinfo"]["binarypath"])

        for repo_group in config.get("buildinfo", {}).get("distrorepo", {}).values():
            for repo in repo_group:
                for key in ["distro", "release", "arch"]:
                    if key not in repo:
                        print(f"❌ Error: Missing required key '{key}' in repo: {repo}")
                        sys.exit(1)

        distrepo = config["buildinfo"].get("distrorepo", {})
        base_repos = distrepo.get("base", [])
        ppa_repos = {ppa["id"]: ppa for ppa in distrepo.get("ppas", [])}

        dependencies = config["buildinfo"].get("deps", [])

        if dependencies:
            print(f"📥 Downloading {len(dependencies)} dependencies:\n")

            terminal_width = get_terminal_size((80, 20)).columns
            with tqdm(
                dependencies,
                desc="    ⏬ Fetching PKGs",
                unit="pkg",
                ncols=terminal_width,
                dynamic_ncols=False,
                bar_format="{l_bar}{bar}| {remaining:>8} • {rate_fmt:<14}"
            ) as progress:
                for dep in progress:
                    if isinstance(dep, dict):
                        pkg_name = dep["name"]
                        repo_id = dep.get("repo")
                        if repo_id:
                            repo_list = [ppa_repos.get(repo_id)]
                            if repo_list[0] is None:
                                progress.disable = True
                                print(f"❌ Error: Unknown repo ID '{repo_id}' for package '{pkg_name}'.")
                                cleanup_cache(package_name)
                                return
                        else:
                            repo_list = base_repos
                    else:
                        pkg_name = dep
                        repo_list = base_repos

                    try:
                        deb_path = get_latest_deb(pkg_name, repo_list, package_name)
                        if deb_path is not None:
                            extract_deb(deb_path, package_name)
                    except RuntimeError as e:
                        progress.disable = True
                        print(e)
                        progress.close()
                        cleanup_cache(package_name)
                        return
        else:
            print("📦 No dependencies listed.")

        print()
        prepare_appimage(config)

        print("\n✅ AppImage creation complete!\n")

        if args.appdir_lint:
            print(f"🧪 Running appdir-lint on: {args.appdir_lint}\n")

            app_name = config["buildinfo"]["name"]
            app_version = config["buildinfo"].get("version", "latest")
            arch = get_architecture()
            appimage_path = Path.cwd() / f"{app_name}-{app_version}-{arch}.AppImage"

            lint_target = Path(args.appdir_lint).expanduser()

            if not lint_target.exists():
                print(f"📦 Extracting AppImage to squashfs-root/...")
                subprocess.run(
                    [str(appimage_path), "--appimage-extract"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                lint_target = Path("squashfs-root")

            lint_meta = infer_lint_metadata_from_yaml(args.config)

            lint_args = types.SimpleNamespace(
                appdir=str(lint_target),
                distro=args.lint_distro or lint_meta.get("distro"),
                release=args.lint_release or lint_meta.get("release"),
                components=args.lint_components or lint_meta.get("components")
            )

            try:
                run_linter(lint_args)
            except Exception as e:
                print(f"❌ appdir-lint failed: {e}")
    elif args.command == "generate":
        yaml_data, fields = generate_yaml(
            args.package,
            args.distro,
            args.release,
            args.arch,
            args.components
        )
        if yaml_data:
            with open(args.output, "w") as f:
                yaml.dump(yaml_data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
            print(f"\n✅ YAML template written to: {args.output}\n")

            if args.description_output and fields:
                md = generate_description_md(fields)
                with open(args.description_output, "w") as desc:
                    desc.write(md)
                print(f"📝 Description Markdown written to: {args.description_output}\n")
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
