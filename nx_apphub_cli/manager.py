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
import shutil
import subprocess
import yaml
import tarfile
import tempfile
import platform
import sys
from datetime import datetime
from pathlib import Path
from shutil import get_terminal_size
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from .downloader import get_latest_deb
from .extractor import extract_deb
from .builder import prepare_appimage
from .config import load_yaml_config
from .utils import cleanup_cache


# -- Ensure directories exist.

system_arch = platform.machine().lower()
repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
repo_dir = repo_base_dir / "apps"
backup_dir = repo_base_dir / "backups"
install_dir = Path.home() / ".local/bin/nx-apphub"
git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"


# -- Create all necessary directories.

for directory in [repo_base_dir, repo_dir, backup_dir, install_dir]:
    directory.mkdir(parents=True, exist_ok=True)


def install(app_names):
    """Fetch YAML metadata, build AppImage, and store metadata for multiple applications."""

    if not isinstance(app_names, list):
        app_names = [app_names]

    print(f"\n[ ⚡ Installing: {', '.join(app_names)} ]")
    print()

    # -- Ensure the repository is valid.

    if repo_base_dir.exists() and not (repo_base_dir / ".git").exists():
        print(f"⚠️ Warning: {repo_base_dir} is not a valid Git repository. Removing...")
        print()
        shutil.rmtree(repo_base_dir)

    # -- If repo is valid and non-empty, update it.

    if (repo_base_dir / ".git").exists() and any(repo_dir.glob("*")):
        try:
            subprocess.run(
                ["git", "-C", str(repo_base_dir), "pull"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print("🔄 Applications repository updated.\n")
        except subprocess.CalledProcessError:
            print("⚠️ Warning: Failed to update repository. Continuing with existing version.\n")

    if not any(repo_dir.glob("*")):
        print("🔄 Applications repository is missing or empty. Cloning fresh copy...\n")
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print("❌ Error: Failed to clone app repository.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: Unexpected failure during clone: {e}")
            sys.exit(1)

    for app_name in app_names:

        # -- Load YAML and determine AppBox filename.

        app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
        if not app_yaml_path.exists():
            print(f"    ❌ Error: No YAML found for {app_name} ({system_arch}) in repository.")
            print()
            continue

        config = load_yaml_config(app_yaml_path)
        app_version = config["buildinfo"].get("version", "unknown")

        # -- Ensure version is valid.

        if not app_version or app_version == "unknown":
            print(f"    ❌ Error: No valid version found for {app_name}. Skipping installation.")
            continue

        # -- Check if **any version** of the AppImage is already installed.

        installed_appbox = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if installed_appbox:
            installed_version = installed_appbox.stem.split("-")[1]
            print(f"    ℹ️  {app_name} is already installed (version {installed_version}). Skipping installation.\n")
            continue

        # -- Ensure `distrorepo` is explicitly defined.

        distrorepo = config["buildinfo"].get("distrorepo")
        if not distrorepo:
            print(f"    ❌ Error: No 'distrorepo' specified for {app_name}. Skipping installation.")
            continue

        # -- Process dependencies.

        repos_config = config["buildinfo"].get("distrorepo", {})

        #  -- Support both list and dict formats.

        if isinstance(repos_config, list):
            base_repos = repos_config
            ppa_repos = {}
        else:
            base_repos = repos_config.get("base", [])
            ppa_repos = {ppa["id"]: ppa for ppa in repos_config.get("ppas", [])}

        dependencies = config["buildinfo"].get("deps", [])

        if dependencies:
            print(f"📥 Downloading {len(dependencies)} dependencies:\n")

            # -- Prepare download tasks.

            download_tasks = []

            for dep in dependencies:
                if isinstance(dep, dict):
                    pkg_name = dep["name"]
                    repo_id = dep.get("repo")
                    if repo_id:
                        repo_list = [ppa_repos.get(repo_id)]
                        if repo_list[0] is None:
                            print(f"❌ Error: Unknown repo ID '{repo_id}' for package '{pkg_name}'.")
                            cleanup_cache(app_name)
                            return
                    else:
                        repo_list = base_repos
                else:
                    pkg_name = dep
                    repo_list = base_repos

                download_tasks.append((pkg_name, repo_list))

            # -- Prefetch metadata for all mirrors before starting parallel downloads.

            from nx_apphub_cli.downloader import fetch_package_metadata

            prefetch_targets = set()

            for pkg_name, repo_list in download_tasks:
                for repo in repo_list:
                    distro = repo.get("distro", "").lower()
                    release = repo.get("release")
                    arch = repo.get("arch")
                    components = repo.get("components", ["main"])
                    if not (distro and release and arch):
                        continue
                    if distro == "debian":
                        mirror_list = debian_mirrors
                    elif distro == "ubuntu":
                        mirror_list = ubuntu_mirrors
                    elif distro == "ubuntu-ports":
                        mirror_list = ubuntu_ports_mirrors
                    elif distro == "devuan":
                        mirror_list = devuan_mirrors
                    elif distro == "kde-neon":
                        mirror_list = kde_neon_mirrors
                    elif distro == "nitrux":
                        mirror_list = nitrux_mirrors
                    else:
                        continue
                    for mirror in mirror_list:
                        for component in components:
                            prefetch_targets.add((mirror, release, arch, component, pkg_name))

            for mirror, release, arch, component, pkg in prefetch_targets:
                fetch_package_metadata(mirror, release, arch, pkg, component)

            # -- Start progress bar manually.

            terminal_width = get_terminal_size((80, 20)).columns
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with tqdm(
                total=len(download_tasks),
                desc="    ⏬ Fetching PKGs",
                unit="pkg",
                ncols=terminal_width,
                dynamic_ncols=False,
                bar_format="{l_bar}{bar}| {remaining:>8} • {rate_fmt:<14}"
            ) as progress:

                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(get_latest_deb, pkg_name, repo_list, app_name): pkg_name
                        for pkg_name, repo_list in download_tasks
                    }

                    first = True

                    for future in as_completed(futures):
                        pkg_name = futures[future]

                        if first:
                            sys.stdout.write("\n\n")
                            sys.stdout.flush()
                            first = False

                        try:
                            deb_path = future.result()
                            if deb_path:
                                extract_deb(deb_path, app_name)
                        except Exception as e:
                            print(f"\n❌ Error downloading {pkg_name}: {e}")
                            cleanup_cache(app_name)
                            progress.close()
                            return
                        progress.update(1)

        else:
            print("📦 No dependencies listed.")

        # -- Build AppImage.

        print("\n🛠  Building AppImage...\n")
        prepare_appimage(config, install_mode=True)

        # -- Verify new AppBox exists before final confirmation.

        built_appbox = install_dir / f"{app_name}-{app_version}-{system_arch}.AppBox"
        if not built_appbox.exists():
            print(f"❌ Error: Failed to find the built {built_appbox} file. Skipping installation.")
            cleanup_cache(app_name)
            return

        print(f"\n✅ Installation successful!\n\n    📦 Available at: {built_appbox}\n")

    print("🎉 All requested applications have been processed!\n")


def remove(app_names):
    """Remove one or more installed AppBoxes."""

    if isinstance(app_names, str):
        app_names = [app_names]

    print(f"\n[ 🗑  Removing: {', '.join(app_names)} ]\n")

    removed_apps = []
    missing_apps = []
    firejail_profiles_deleted = []

    for app_name in app_names:
        app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not app_file:
            missing_apps.append(f"    ❌ {app_name} (Not Installed)")
            continue

        try:
            app_file.unlink()
            removed_apps.append(f"    ✅ {app_name} (Removed)")

            firejail_profile = Path.home() / ".local/share/nx-apphub-cli/firejail.d" / f"{app_name}-profile.profile"
            if firejail_profile.exists():
                firejail_profile.unlink()
                firejail_profiles_deleted.append(firejail_profile.name)

        except PermissionError:
            missing_apps.append(f"    ❌ {app_name} (Permission Denied)")
            continue

    if removed_apps:
        print("🟢 Successfully Removed:\n\n" + "\n".join(removed_apps))

    if firejail_profiles_deleted:
        print(f"\n🔒 Firejail profile(s) deleted: {', '.join(sorted(firejail_profiles_deleted))}")

    if missing_apps:
        print("\n🔴 Skipped:\n\n" + "\n".join(missing_apps))

    print("\n🎉 All requested applications have been processed!\n")


def search(app_names):
    """Search for specific applications in the local repository."""

    print(f"\n[ 🔍 Searching for: {', '.join(app_names)} ]\n")

    # -- Ensure the repository is cloned or updated before searching.

    if not (repo_base_dir / ".git").exists():
        print("📥 Cloning application repository...")
        shutil.rmtree(repo_base_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        print("🔄 Updating repository...")
        subprocess.run(
            ["git", "-C", str(repo_base_dir), "pull"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    
    found_apps = []
    missing_apps = []

    for app_name in app_names:
        app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
        matched_paths = [
            p for p in (repo_dir / system_arch).glob("*")
            if app_name in p.name
        ]

        for p in matched_paths:
            app_yaml = p / "app.yml"
            if app_yaml.exists():
                config = load_yaml_config(app_yaml)
                version = config["buildinfo"].get("version", "unknown")
                found_apps.append(f"    ✅ {p.name} - Version: {version} - Arch: {system_arch}")
            else:
                missing_apps.append(f"    ❌ {p.name} (Missing YAML)")

    if found_apps:
        print("\n🟢 Found Applications:\n")
        print("\n".join(found_apps), "\n")
    
    if missing_apps:
        print("\n🔴 Not Found:\n")
        print("\n".join(missing_apps), "\n")


def update(app_names):
    """Update one or more AppBoxes only if a newer version is available."""

    # -- Ensure app_names is a list.

    if isinstance(app_names, str):
        app_names = [app_names]

    print(f"\n[ 📤 Updating: {', '.join(app_names)} ]\n")

    # -- Ensure the repository is up to date.

    if not (repo_base_dir / ".git").exists():
        print("📥 Cloning application repository...")
        shutil.rmtree(repo_base_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        print("    🔄 Fetching latest repository changes...")
        subprocess.run(
            ["git", "-C", str(repo_base_dir), "pull"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    for app_name in app_names:
        print(f"\n[ 🔄 Checking updates for: {app_name} ]\n")

        # -- Find installed AppBox.

        installed_app = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not installed_app:
            print(f"    ❌ Error: {app_name} is not installed. Cannot update.\n")
            continue

        # -- Extract version from installed file.

        installed_parts = installed_app.stem.split("-")
        if len(installed_parts) < 2:
            print(f"    ❌ Error: Could not determine installed version for {app_name}.\n")
            continue

        installed_version = "-".join(installed_parts[1:-1])

        # -- Validate YAML existence.

        app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
        if not app_yaml_path.exists():
            print(f"    ❌ Error: No YAML found for {app_name} ({system_arch}) in repository.\n")
            print()
            continue

        # -- Load YAML and check latest version.

        config = load_yaml_config(app_yaml_path)
        latest_version = config["buildinfo"].get("version", "unknown")

        if not latest_version or latest_version == "unknown":
            print(f"    ❌ Error: No valid version information found for {app_name}. Aborting update.\n")
            continue

        if installed_version == latest_version:
            print(f"    ✅ {app_name} is already up to date (version {installed_version}).\n")
            continue

        print(f"    🔄 New version available: {latest_version} (Installed: {installed_version})\n")

        # -- Remove executable permission before backup.

        try:
            installed_app.chmod(0o644)
        except OSError as e:
            print(f"⚠️ Warning: Failed to modify permissions of {installed_app}. Reason: {e}")

        # -- Create backup safely.

        backup_name = backup_dir / f"{app_name}-{installed_version}-{system_arch}.tar"
        try:
            with tarfile.open(backup_name, "w") as tar:
                tar.add(installed_app, arcname=installed_app.name)
            print(f"📦 Backup created: {backup_name}")
        except Exception as e:
            print(f"❌ Error creating backup for {app_name}: {e}")
            continue

        # -- Delete the old AppImage to force install to proceed with creating a new one.

        try:
            installed_app.unlink()
        except OSError as e:
            print(f"❌ Error deleting {installed_app}: {e}")
            continue

        # -- Attempt installation of new version.

        install([app_name])

        # -- Check if new AppBox exists.

        new_appbox = install_dir / f"{app_name}-{latest_version}-{system_arch}.AppBox"
        if new_appbox.exists():
            print(f"✅ {app_name} successfully updated to version {latest_version}!\n")
        else:
            print(f"❌ Update failed: No new AppImage found. Restoring backup...")

            # -- Restore backup if update fails.

            try:
                with tarfile.open(backup_name, "r") as tar:
                    tar.extractall(path=install_dir)
                restored_appbox = install_dir / f"{app_name}-{installed_version}-{system_arch}.AppBox"
                if restored_appbox.exists():
                    restored_appbox.chmod(0o755)
                    print(f"♻️ Restored {app_name} to version {installed_version}\n")
                else:
                    print(f"❌ Failed to restore {app_name}.")
            except Exception as e:
                print(f"❌ Critical error: Could not restore backup for {app_name}. Reason: {e}")


def downgrade(app_names):
    """Restore specific backups of multiple AppBoxes."""

    # -- Ensure app_names is a list.

    if isinstance(app_names, str):
        app_names = [app_names]

    print(f"\n[ ⏳ Downgrading: {', '.join(app_names)} ]\n")

    for app_name in app_names:
        print(f"\n🔽 Processing downgrade for: {app_name}...\n")

        # -- Find available backups.

        backups = sorted(backup_dir.glob(f"{app_name}-*-{system_arch}.tar"), reverse=True)

        if not backups:
            print(f"    ❌ No backups found for {app_name}.\n")
            continue

        # -- Display available backups.

        print("📦 Available backups:\n")
        for i, backup in enumerate(backups, 1):
            print(f"    {i}. {backup.name}")

        # -- Select a backup.

        while True:
            choice = input(f"\n🔢 Enter the number of the backup to restore for {app_name} (default = latest): ").strip()
            if choice == "":
                index = 0
                break
            if choice.isdigit() and 1 <= int(choice) <= len(backups):
                index = int(choice) - 1
                break
            print("\n    ⚠️ Invalid selection. Please enter a valid number.")

        selected_backup = backups[index]

        print(f"\n🔄 Restoring backup: {selected_backup.name}...\n")

        try:
            # -- Extract the backup.

            with tarfile.open(selected_backup, "r") as tar:
                extracted_files = tar.getnames()
                tar.extractall(path=install_dir)

            # -- Locate the restored AppBox based on extracted filenames.

            restored_appbox = None
            for file in extracted_files:
                restored_path = install_dir / file
                if restored_path.suffix == ".AppBox" and restored_path.exists():
                    restored_appbox = restored_path
                    break

            if not restored_appbox:
                print(f"❌ Error: Restoration failed! No valid AppBox found in {install_dir}.\n")
                continue

            # -- Restore executable permissions.

            restored_appbox.chmod(0o755)
            print(f"✅ Successfully restored {app_name} to {restored_appbox.name}\n")

            # -- Find and remove the newer version.

            for newer_version in install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"):
                if newer_version != restored_appbox:
                    try:
                        newer_version.unlink()
                    except OSError as e:
                        print(f"⚠️ Warning: Failed to remove newer version {newer_version}. Reason: {e}")

        except (tarfile.TarError, OSError) as e:
            print(f"❌ Error: Could not restore {app_name} from backup. Reason: {e}")

    print("🎉 All requested applications have been processed!\n")


def format_size(size_bytes):
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PiB"


def show():
    """Show installed AppBoxes."""
    print("\n[ 📦 Installed AppBoxes ]\n")

    installed_apps = list(install_dir.glob(f"*-{system_arch}.AppBox"))

    if not installed_apps:
        print("❌ No applications installed.\n")
        return

    installed_apps.sort(key=lambda app: app.stat().st_size, reverse=True)

    total_size = 0

    for app in installed_apps:
        size = app.stat().st_size
        total_size += size
        print(f"    ✅ {app.name} ({format_size(size)})")

    print(f"\n📁 Total: {len(installed_apps)} installed in {install_dir}\n")
    print(f"📦 Size: {format_size(total_size)}\n")


def get_search_results(app_names):
    """Return structured search results for use in GUI."""
    results = []

    for app_name in app_names:
        app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
        if app_yaml_path.exists():
            config = load_yaml_config(app_yaml_path)
            results.append({
                "name": app_name,
                "version": config["buildinfo"].get("version", "unknown"),
                "arch": system_arch
            })

    return results


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search", "show"]
