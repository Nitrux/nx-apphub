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
from datetime import datetime
from pathlib import Path
from .downloader import get_latest_deb
from .extractor import extract_deb
from .builder import prepare_appimage
from .config import load_yaml_config
from .utils import cleanup_cache


# -- Base directories.

repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
apps_dir = repo_base_dir / "apps"
backup_dir = repo_base_dir / "backups"
git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"


# -- Ensure base directories exist.

repo_base_dir.mkdir(parents=True, exist_ok=True)
apps_dir.mkdir(parents=True, exist_ok=True)
backup_dir.mkdir(parents=True, exist_ok=True)


def install(app_name):
    """Fetch YAML metadata, build AppImage, and store metadata."""
    print(f"Installing {app_name}...")

    repo_dir = repo_base_dir / "apps"

    # -- If repo exists but isn't valid, remove & re-clone.

    if repo_base_dir.exists() and not (repo_base_dir / ".git").exists():
        print(f"Warning: {repo_base_dir} exists but is not a valid Git repository. Removing...")
        shutil.rmtree(repo_base_dir)
    
    # -- Clone repository if missing.

    if not (repo_base_dir / ".git").exists():
        print("Cloning repository...")
        subprocess.run(["git", "clone", "--depth=1", git_repo_url, str(repo_base_dir)], check=True)
    else:
        print("Updating repository...")
        subprocess.run(["git", "-C", str(repo_base_dir), "pull"], check=True)

    if not apps_dir.exists():
        apps_dir.mkdir(parents=True, exist_ok=True)

    # -- Validate YAML existence.

    app_yaml_path = repo_dir / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"Error: No YAML found for {app_name} in repository.")
        return

    # -- Load YAML and process dependencies.

    config = load_yaml_config(app_yaml_path)

    for dep in config["buildinfo"].get("deps", []):
        deb_path = get_latest_deb(dep, config["buildinfo"]["distrorepo"], app_name)
        extract_deb(deb_path, app_name)

    # -- Build the AppImage.

    prepare_appimage(config)
    print(f"Installation of {app_name} completed!")


def remove(app_name):
    """Remove only the installed AppBox."""
    print(f"Removing {app_name}...")

    app_file = repo_base_dir / f"{app_name}.AppBox"
    
    if app_file.exists():
        try:
            app_file.unlink()
            print(f"Removed {app_file}")
        except PermissionError:
            print(f"Error: Cannot remove {app_file}. Is it in use?")
            return
    else:
        print(f"AppBox for {app_name} not found.")

    cleanup_cache(app_name)
    print(f"{app_name} has been successfully removed.")


def search():
    """Search for available applications in the local repository."""
    print("Searching for available applications...")
    
    for app_dir in apps_dir.iterdir():
        app_yaml_path = app_dir / "app.yml"
        if app_yaml_path.exists():
            config = load_yaml_config(app_yaml_path)
            app_name = config["buildinfo"]["name"]
            app_version = config["buildinfo"].get("version", "unknown")
            print(f"{app_name} - Version: {app_version}")


def backup(app_name):
    """Create a backup of the installed AppBox."""
    app_file = repo_base_dir / f"{app_name}.AppBox"
    if not app_file.exists():
        print(f"Error: {app_name} is not installed.")
        return
    
    backup_name = backup_dir / f"{app_name}_{datetime.now().strftime('%Y-%m-%d')}.tar"
    with tarfile.open(backup_name, "w") as tar:
        tar.add(app_file, arcname=app_file.name)
    
    print(f"Backup of {app_name} created: {backup_name}")


def update(app_name):
    """Update an AppBox by creating a backup and rebuilding."""
    print(f"Updating {app_name}...")
    backup(app_name)
    remove(app_name)
    install(app_name)
    print(f"{app_name} updated successfully!")


def downgrade(app_name):
    """Restore the most recent backup."""
    print(f"Downgrading {app_name}...")
    
    backups = sorted(backup_dir.glob(f"{app_name}_*.tar"), reverse=True)
    if not backups:
        print(f"No backups found for {app_name}.")
        return
    
    latest_backup = backups[0]
    with tarfile.open(latest_backup, "r") as tar:
        tar.extractall(path=repo_base_dir)
    
    print(f"Restored {app_name} from backup: {latest_backup}")


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search", "backup"]
