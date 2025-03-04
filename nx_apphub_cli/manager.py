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
from pathlib import Path
from .downloader import get_latest_deb
from .extractor import extract_deb
from .builder import prepare_appimage
from .config import load_yaml_config
from .utils import cleanup_cache


# -- Base directories.

repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
apps_dir = repo_base_dir / "apps"
git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"


# -- Ensure base directories exist.

repo_base_dir.mkdir(parents=True, exist_ok=True)
apps_dir.mkdir(parents=True, exist_ok=True)


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
    """Remove the installed AppBox and metadata safely."""
    print(f"Removing {app_name}...")

    app_file = repo_base_dir / f"{app_name}.AppBox"
    metadata_dir = apps_dir / app_name

    # -- Check if AppBox exists before removing.

    if app_file.exists():
        try:
            app_file.unlink()
            print(f"Removed {app_file}")
        except PermissionError:
            print(f"Error: Cannot remove {app_file}. Is it in use?")
            return
    else:
        print(f"AppBox for {app_name} not found.")

    # -- Ensure metadata directory is removed safely.

    if metadata_dir.exists():
        try:
            shutil.rmtree(metadata_dir)
            print(f"Metadata for {app_name} removed.")
        except PermissionError:
            print(f"Error: Cannot remove metadata for {app_name}.")
    else:
        print(f"Metadata for {app_name} not found.")

    # -- Clean up cache for this app only.

    cleanup_cache(app_name)

    print(f"{app_name} has been successfully removed.")


def update(app_name):
    """Update an AppBox using Zsync."""
    print(f"Updating {app_name}...")

    app_file = repo_base_dir / f"{app_name}.AppBox"
    if not app_file.exists():
        print(f"Error: {app_name} is not installed.")
        return

    # -- Load metadata and get update URL.

    app_yaml_path = apps_dir / app_name / "app.yml"
    if not app_yaml_path.exists():
        print(f"Error: No YAML metadata found for {app_name}. Cannot update.")
        return

    config = load_yaml_config(app_yaml_path)
    zsync_url = config["buildinfo"].get("update_url", "")

    if not zsync_url:
        print(f"Error: No update URL specified for {app_name}.")
        return

    # -- Run zsync update.
    try:
        subprocess.run(["zsync", "-i", str(app_file), zsync_url], check=True)
        print(f"{app_name} updated successfully!")
    except subprocess.CalledProcessError:
        print(f"Error updating {app_name}.")


def downgrade(app_name):
    """Downgrade an AppBox using a stored Zstd backup."""
    print(f"Downgrading {app_name}...")

    backup_file = repo_base_dir / f"{app_name}.zst"
    app_file = repo_base_dir / f"{app_name}.AppBox"
    temp_file = repo_base_dir / f"{app_name}.AppBox.tmp"

    if not backup_file.exists():
        print(f"No downgrade backup found for {app_name}.")
        return

    # -- Decompress the backup into a temporary file.
    try:
        subprocess.run(["zstd", "--decompress", str(backup_file), "-o", str(temp_file)], check=True)
        shutil.move(str(temp_file), str(app_file))
        print(f"{app_name} downgraded successfully!")
    except subprocess.CalledProcessError:
        print(f"Error downgrading {app_name}.")
        if temp_file.exists():
            temp_file.unlink()  # Cleanup failed temp file


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade"]
