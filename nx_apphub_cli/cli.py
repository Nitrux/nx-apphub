#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import argparse
import re
import subprocess
import sys
import types
from datetime import datetime
from io import StringIO
from pathlib import Path

import yaml

from .exceptions import NxAppHubError, ConfigError, BuildError
from .appdir_lint import run_linter
from .builder import prepare_appimage, setup_appimage_directories
from .config import load_yaml_config, validate_yaml_config
from .generator import generate_yaml, generate_description_md
from .manager import install, remove, search, show, update, downgrade
from .utils import get_architecture, concurrent_downloads
from .console import (
    print_header, print_success, print_error, print_warning,
    print_info, print_blank
)

# <---
# --->
def main():
    """Entry point for the nx-apphub-cli command-line interface."""
    try:
        parser = argparse.ArgumentParser(
        prog="nx-apphub-cli",
        description="NX AppHub CLI — Lightweight command-line tool for managing and building applications in Nitrux."
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

        subparsers.add_parser("show", help="Show installed applications")

        # -- Building command (requires YAML file).

        subparser_build = subparsers.add_parser("build", help="Build an custom bundle from a local YAML file")
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
        subparser_generate.add_argument("--integration-type", choices=["cli", "gui", "wm"], default="gui", help="Integration type: cli, gui, or wm (default: gui)")

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
            print_header("🛠  Building local bundle...")

            yaml_file = Path(args.config)
            yaml_dir = yaml_file.parent

            config = load_yaml_config(args.config)
            validate_yaml_config(config)

            package_name = config["buildinfo"]["name"]

            setup_appimage_directories(package_name, config["buildinfo"]["binarypath"])

            distrorepo = config.get("buildinfo", {}).get("distrorepo", {})

            if isinstance(distrorepo, list):
                repo_groups = [distrorepo]
            elif isinstance(distrorepo, dict):
                repo_groups = distrorepo.values()
            else:
                repo_groups = []

            for repo_group in repo_groups:
                for repo in repo_group:
                    for key in ["distro", "release", "arch"]:
                        if key not in repo:
                            raise ConfigError(f"Missing required key '{key}' in repo: {repo}")

            distrorepo = config["buildinfo"].get("distrorepo", {})

            if isinstance(distrorepo, list):
                base_repos = distrorepo
                ppa_repos = {}
            elif isinstance(distrorepo, dict):
                base_repos = distrorepo.get("base", [])
                ppa_repos = {ppa["id"]: ppa for ppa in distrorepo.get("ppas", [])}
            else:
                base_repos = []
                ppa_repos = {}

            dependencies = config["buildinfo"].get("deps", [])

            concurrent_downloads(dependencies, base_repos, ppa_repos, package_name)

            print_blank()
            prepare_appimage(config, yaml_dir=yaml_dir)

            print_success("Bundle creation complete!")
            print_blank()

            if args.appdir_lint:
                app_name = config["buildinfo"]["name"]
                app_version = config["buildinfo"].get("version", "latest")
                arch = get_architecture()
                appimage_path = Path.cwd() / f"{app_name}-{app_version}-{arch}.AppImage"

                lint_target = Path(args.appdir_lint).expanduser()

                if not lint_target.exists():
                    if not appimage_path.exists():
                        raise BuildError(f"Bundle not found: {appimage_path}")

                    print_info("Extracting to squashfs-root/...", prefix="📦")

                    try:
                        subprocess.run(
                            [str(appimage_path), "--appimage-extract"],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except PermissionError:
                        print_blank()
                        print_warning(f"Warning: Bundle '{appimage_path.name}' is not executable. Attempting to fix permissions...")
                        try:
                            appimage_path.chmod(0o755)
                            subprocess.run(
                                [str(appimage_path), "--appimage-extract"],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                            print_success("Successfully fixed and extracted Bundle.")
                            print_blank()
                        except Exception as e:
                            raise BuildError(f"Failed to extract after fixing permissions: {e}")
                    except subprocess.CalledProcessError as e:
                        raise BuildError(f"Failed to extract: {e}")

                    lint_target = Path("squashfs-root")

                lint_args = types.SimpleNamespace(
                    appdir=str(lint_target),
                    yaml=args.config
                )

                try:
                    run_linter(lint_args)
                except Exception as e:
                    print_error(f"appdir-lint failed: {e}")

        elif args.command == "generate":
            integration_key = args.integration_type

            yaml_data, fields = generate_yaml(
                args.package,
                args.distro,
                args.release,
                args.arch,
                args.components,
                integration_key=integration_key
            )
            if yaml_data:
                current_year = datetime.now().year
                header_lines = [
                    "# YAML build file",
                    f"# nx-apphub-cli {current_year} (c) Nitrux Latinoamericana S.C.",
                    ""
                ]

                with open(args.output, "w", encoding="utf-8") as f:
                    f.write("\n".join(header_lines) + "\n")

                    yaml_buffer = StringIO()
                    yaml.dump(
                        yaml_data,
                        yaml_buffer,
                        sort_keys=False,
                        allow_unicode=True,
                        default_flow_style=False,
                        indent=2,
                        width=100,
                    )
                    yaml_str = yaml_buffer.getvalue()

                    yaml_str = yaml_str.replace("\napprunconf:", "\n\napprunconf:")
                    yaml_str = yaml_str.replace("\nsandbox:", "\n\nsandbox:")
                    yaml_str = yaml_str.replace("\nintegration:", "\n\nintegration:")

                    yaml_str = re.sub(
                        r'(deps:\n)((?:  - .*\n)+)',
                        lambda m: m.group(1) + re.sub(r'^  ', '    ', m.group(2), flags=re.MULTILINE),
                        yaml_str
                    )

                    yaml_str = re.sub(
                        r'(base:\n)((?:  - .*\n)+)',
                        lambda m: m.group(1) + re.sub(r'^  ', '    ', m.group(2), flags=re.MULTILINE),
                        yaml_str
                    )
                    
                    yaml_str = re.sub(
                        r'^ {2}(- distro:)',
                        r'    \1',
                        yaml_str,
                        flags=re.MULTILINE
                    )

                    yaml_str = re.sub(
                        r'(components:\n)((?:    - .*\n)+)',
                        lambda m: m.group(1) + re.sub(r'^    ', '        ', m.group(2), flags=re.MULTILINE),
                        yaml_str
                    )

                    yaml_str = re.sub(
                        r'^( {4})(release|arch|components):',
                        r'      \2:',
                        yaml_str,
                        flags=re.MULTILINE
                    )

                    f.write(yaml_str)

                print_success(f"YAML template written to: {args.output}")

                if args.description_output and fields:
                    md = generate_description_md(fields)
                    with open(args.description_output, "w", encoding="utf-8") as desc:
                        desc.write(md)
                    print_success(f"Description template written to: {args.description_output}")
                print_blank()
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print_error("Interrupted by SIGINT. Exiting cleanly.", prefix="🛑")
        print_blank()
        sys.exit(130)
    except NxAppHubError as e:
        print_blank()
        print_error(f"Error: {e}")
        print_blank()
        sys.exit(1)

if __name__ == "__main__":
    main()
