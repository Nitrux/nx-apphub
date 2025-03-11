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
import platform
from datetime import datetime
from pathlib import Path
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


def install(app_name):
    """Fetch YAML metadata, build AppImage, and store metadata."""
    print(f"Installing {app_name}...")

    # -- Ensure the repository is valid.

    if repo_base_dir.exists() and not (repo_base_dir / ".git").exists():
        print(f"Warning: {repo_base_dir} exists but is not a valid Git repository. Removing...")
        shutil.rmtree(repo_base_dir)

    if not (repo_base_dir / ".git").exists():
        subprocess.run(["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["git", "-C", str(repo_base_dir), "pull"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # -- Load YAML and determine AppBox filename.

    app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"Error: No YAML found for {app_name} ({system_arch}) in repository.")
        return

    config = load_yaml_config(app_yaml_path)
    app_version = config["buildinfo"].get("version", "unknown")
    appbox_path = install_dir / f"{app_name}-{app_version}-{system_arch}.AppBox"

    # -- Check if version is missing from YAML.

    if not app_version or app_version == "unknown":
        print(f"Error: No valid version found for {app_name}. Aborting installation.")
        return

    # -- Check if already installed.

    if appbox_path.exists():
        print(f"Skipping installation: {app_name} {app_version} is already installed.")
        return

    # -- Ensure `distrorepo` is explicitly defined.

    distrorepo = config["buildinfo"].get("distrorepo")
    if not distrorepo:
        print(f"Error: No 'distrorepo' specified for {app_name}. Aborting installation.")
        return

    # -- Process dependencies.

    for dep in config["buildinfo"].get("deps", []):
        deb_path = get_latest_deb(dep, distrorepo, app_name)
        extract_deb(deb_path, app_name)

    # -- Build AppImage.

    prepare_appimage(config, install_mode=True)
    print(f"Installation of {app_name} completed!")

    # -- Verify new AppBox exists before final confirmation.

    built_appbox = install_dir / f"{app_name}-{app_version}-{system_arch}.AppBox"
    if not built_appbox.exists():
        print(f"Error: Failed to find the built {built_appbox} file. Aborting installation.")
        return

    print(f"Installation successful: {built_appbox}")


def remove(app_name):
    """Remove only the installed AppBox."""
    print(f"Removing {app_name}...")

    app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)
    if not app_file:
        print(f"AppBox for {app_name} not found.")
        return

    try:
        app_file.unlink()
        print(f"Removed {app_file}")
    except PermissionError:
        print(f"Error: Cannot remove {app_file}. Is it in use?")
        return

    cleanup_cache(app_name)
    print(f"{app_name} has been successfully removed.")


def search(app_names):
    """Search for specific applications in the local repository."""

    # -- Ensure the repository is cloned or updated before searching.

    if not (repo_base_dir / ".git").exists():
        shutil.rmtree(repo_base_dir, ignore_errors=True)
        subprocess.run(["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["git", "-C", str(repo_base_dir), "pull"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    found_apps = []
    missing_apps = []

    for app_name in app_names:
        app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
        if app_yaml_path.exists():
            config = load_yaml_config(app_yaml_path)
            app_version = config["buildinfo"].get("version", "unknown")
            found_apps.append(f"{app_name} - Version: {app_version}")
        else:
            missing_apps.append(app_name)

    if found_apps:
        print("\n".join(found_apps))
    if missing_apps:
        print(f"Error: No YAML found for {', '.join(missing_apps)}.")


def backup(app_name):
    """Create a backup of the installed AppBox."""
    app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)
    if not app_file:
        print(f"AppBox for {app_name} not found.")
        return
    
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_name = backup_dir / f"{app_name}_{datetime.now().strftime('%Y-%m-%d')}.tar"
    with tarfile.open(backup_name, "w") as tar:
        tar.add(app_file, arcname=app_file.name)
    
    print(f"Backup of {app_name} created at: {backup_name}")


def update(app_name):
    """Update an AppBox only if a newer version is available."""
    print(f"Checking for updates for {app_name}...")

    # -- Find installed AppBox.

    installed_app = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

    if not installed_app:
        print(f"Error: {app_name} is not installed. Cannot update.")
        return

    # -- Extract version from installed file.

    installed_parts = installed_app.stem.split("-")
    if len(installed_parts) < 2:
        print(f"Error: Could not determine installed version for {app_name}.")
        return

    installed_version = "-".join(installed_parts[1:-1])

    # -- Validate YAML existence.

    app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"Error: No YAML found for {app_name} ({system_arch}) in repository.")
        return

    # -- Load YAML and check latest version.

    config = load_yaml_config(app_yaml_path)
    latest_version = config["buildinfo"].get("version")

    if not latest_version or latest_version == "unknown":
        print(f"Error: No valid version information found for {app_name}. Aborting update.")
        return

    if installed_version == latest_version:
        print(f"{app_name} is already up to date (version {installed_version}).")
        return

    print(f"New version available: {latest_version} (Installed: {installed_version})")

    # -- Remove executable permission before backup.

    try:
        installed_app.chmod(0o644)
    except OSError as e:
        print(f"Warning: Failed to modify permissions of {installed_app}. Reason: {e}")

    # -- Create backup.

    backup_name = backup_dir / f"{app_name}-{installed_version}-{system_arch}.tar"
    with tarfile.open(backup_name, "w") as tar:
        tar.add(installed_app, arcname=installed_app.name)

    print(f"Backup created: {backup_name}")

    # -- Attempt installation of new version.

    install(app_name)

    # -- Check if new AppBox exists before removing the old one.

    new_appbox = install_dir / f"{app_name}-{latest_version}-{system_arch}.AppBox"
    if new_appbox.exists():
        installed_app.unlink()
        print(f"Updated {app_name} to version {latest_version}!")
    else:
        print(f"Update failed: Keeping existing {installed_app}")


def downgrade(app_name):
    """Restore a specific backup of an AppBox."""
    print(f"Downgrading {app_name}...")

    backups = sorted(backup_dir.glob(f"{app_name}-*-{system_arch}.tar"), reverse=True)
    if not backups:
        print(f"No backups found for {app_name}.")
        return

    print("\nAvailable backups:")
    for i, backup in enumerate(backups, 1):
        print(f"{i}. {backup.name}")

    while True:
        choice = input("\nEnter the number of the backup to restore (default = latest): ").strip()
        if choice == "":
            index = 0
            break
        if choice.isdigit() and 1 <= int(choice) <= len(backups):
            index = int(choice) - 1
            break
        print("Invalid selection. Please enter a valid number.")

    selected_backup = backups[index]

    try:
        with tarfile.open(selected_backup, "r") as tar:
            tar.extractall(path=install_dir)
        print(f"Successfully restored {app_name} from backup: {selected_backup}")
    except (tarfile.TarError, OSError) as e:
        print(f"Error: Could not restore {app_name} from backup. Reason: {e}")


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search", "backup"]
