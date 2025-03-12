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
    print(f"\n[ ⚡ Installing: {app_name}... ]\n")

    # -- Ensure the repository is valid.
    if repo_base_dir.exists() and not (repo_base_dir / ".git").exists():
        print(f"⚠️ Warning: {repo_base_dir} is not a valid Git repository. Removing...")
        shutil.rmtree(repo_base_dir)

    if not (repo_base_dir / ".git").exists():
        subprocess.run(
            ["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        subprocess.run(
            ["git", "-C", str(repo_base_dir), "pull"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    # -- Load YAML and determine AppBox filename.

    app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"❌ Error: No YAML found for {app_name} ({system_arch}) in repository.")
        return

    config = load_yaml_config(app_yaml_path)
    app_version = config["buildinfo"].get("version", "unknown")

    # -- Ensure version is valid.

    if not app_version or app_version == "unknown":
        print(f"❌ Error: No valid version found for {app_name}. Aborting installation.")
        return

    # -- Check if **any version** of the AppImage is already installed.

    installed_appbox = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)
    
    if installed_appbox:
        installed_version = installed_appbox.stem.split("-")[1]
        print(f"ℹ️  {app_name} is already installed (version {installed_version}). Skipping installation.\n")
        return

    # -- Ensure `distrorepo` is explicitly defined.

    distrorepo = config["buildinfo"].get("distrorepo")
    if not distrorepo:
        print(f"❌ Error: No 'distrorepo' specified for {app_name}. Aborting installation.")
        return

    # -- Process dependencies.

    print("📥 Downloading dependencies...")
    for dep in config["buildinfo"].get("deps", []):
        deb_path = get_latest_deb(dep, distrorepo, app_name)
        extract_deb(deb_path, app_name)

    # -- Build AppImage.

    print("\n🛠 Building AppImage...\n")
    prepare_appimage(config, install_mode=True)

    # -- Verify new AppBox exists before final confirmation.

    built_appbox = install_dir / f"{app_name}-{app_version}-{system_arch}.AppBox"
    if not built_appbox.exists():
        print(f"❌ Error: Failed to find the built {built_appbox} file. Aborting installation.")
        return

    print(f"\n✅ Installation successful!\n\n    📦 Available at: {built_appbox}\n")


def remove(app_name):
    """Remove only the installed AppBox."""
    
    print(f"\n[ 🗑 Removing: {app_name}... ]\n")

    # -- Find the installed AppBox matching the app name and system architecture.

    app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

    if not app_file:
        print(f"⚠️ Warning: No installed AppBox found for {app_name}. Skipping removal.")
        return

    try:
        app_file.unlink()
        print(f"📦 Removed: {app_file}\n")
    except PermissionError:
        print(f"❌ Error: Cannot remove {app_file}. Is it in use?")
        return


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
        if app_yaml_path.exists():
            config = load_yaml_config(app_yaml_path)
            app_version = config["buildinfo"].get("version", "unknown")
            found_apps.append(f"    ✅ {app_name} - Version: {app_version}")
        else:
            missing_apps.append(f"    ❌ {app_name}")

    if found_apps:
        print("\n🟢 Found Applications:\n")
        print("\n".join(found_apps), "\n")
    
    if missing_apps:
        print("\n🔴 Not Found:\n")
        print("\n".join(missing_apps), "\n")


def update(app_name):
    """Update an AppBox only if a newer version is available."""
    print(f"\n[ 📤 Updating {app_name}... ]\n")

    # -- Ensure the repository is up to date.

    if not (repo_base_dir / ".git").exists():
        print("📥 Cloning application repository...")
        shutil.rmtree(repo_base_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        print("🔄 Fetching latest repository changes...")
        subprocess.run(
            ["git", "-C", str(repo_base_dir), "pull"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    # -- Find installed AppBox.

    installed_app = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

    if not installed_app:
        print(f"❌ Error: {app_name} is not installed. Cannot update.\n")
        return

    # -- Extract version from installed file.

    installed_parts = installed_app.stem.split("-")
    if len(installed_parts) < 2:
        print(f"❌ Error: Could not determine installed version for {app_name}.\n")
        return

    installed_version = "-".join(installed_parts[1:-1])

    # -- Validate YAML existence.

    app_yaml_path = repo_dir / system_arch / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"❌ Error: No YAML found for {app_name} ({system_arch}) in repository.\n")
        return

    # -- Load YAML and check latest version.

    config = load_yaml_config(app_yaml_path)
    latest_version = config["buildinfo"].get("version", "unknown")

    if not latest_version or latest_version == "unknown":
        print(f"❌ Error: No valid version information found for {app_name}. Aborting update.\n")
        return

    if installed_version == latest_version:
        print(f"\n✅ {app_name} is already up to date (version {installed_version}).\n")
        return

    print(f"\n    🔄 New version available: {latest_version} (Installed: {installed_version})\n")

    # -- Remove executable permission before backup.

    try:
        installed_app.chmod(0o644)
    except OSError as e:
        print(f"⚠️ Warning: Failed to modify permissions of {installed_app}. Reason: {e}")

    # -- Create backup.

    backup_name = backup_dir / f"{app_name}-{installed_version}-{system_arch}.tar"
    with tarfile.open(backup_name, "w") as tar:
        tar.add(installed_app, arcname=installed_app.name)

    print(f"📦 Backup created: {backup_name}")

    # -- Attempt installation of new version.

    install(app_name)

    # -- Check if new AppBox exists before removing the old one.

    new_appbox = install_dir / f"{app_name}-{latest_version}-{system_arch}.AppBox"
    if new_appbox.exists():
        installed_app.unlink()
        print(f"✅ {app_name} successfully updated to version {latest_version}!\n")
    else:
        print(f"❌ Update failed: Keeping existing {installed_app}\n")


def downgrade(app_name):
    """Restore a specific backup of an AppBox."""
    print(f"\n[ ⏳ Downgrading {app_name}... ]\n")

    # -- Find available backups.

    backups = sorted(backup_dir.glob(f"{app_name}-*-{system_arch}.tar"), reverse=True)

    if not backups:
        print(f"❌ No backups found for {app_name}.\n")
        return

    # -- Display available backups.

    print("📦 Available backups:\n")
    for i, backup in enumerate(backups, 1):
        print(f"    {i}. {backup.name}")

    # -- Select a backup.

    while True:
        choice = input("\n🔢 Enter the number of the backup to restore (default = latest): ").strip()
        if choice == "":
            index = 0
            break
        if choice.isdigit() and 1 <= int(choice) <= len(backups):
            index = int(choice) - 1
            break
        print("⚠️ Invalid selection. Please enter a valid number.")

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
            return

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


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search"]
