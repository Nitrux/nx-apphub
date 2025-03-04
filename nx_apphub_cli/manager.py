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
from .builder import prepare_appimage
from .config import load_yaml_config


# -- Base directories.

repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"


# -- Ensure base directories exist.

repo_base_dir.mkdir(parents=True, exist_ok=True)


def install(app_name):
    """Fetch YAML metadata, build AppImage, and store metadata."""
    print(f"Installing {app_name}...")

    # -- Clone or update repo to get the latest metadata.

    repo_dir = repo_base_dir / "apps"
    if repo_dir.exists():
        subprocess.run(["git", "-C", str(repo_dir), "pull"], check=True)
    else:
        subprocess.run(["git", "clone", git_repo_url, str(repo_dir)], check=True)

    # -- Locate the YAML file.

    app_yaml = repo_dir / app_name / "app.yml"
    if not app_yaml.exists():
        print(f"Error: No YAML found for {app_name} in repository.")
        return

    # -- Load YAML and build the AppImage.

    config = load_yaml_config(app_yaml)
    prepare_appimage(config)
    print(f"Installation of {app_name} completed!")


def remove(app_name):
    """Remove the installed AppBox and metadata."""
    print(f"Removing {app_name}...")

    app_file = repo_base_dir / f"{app_name}.AppBox"
    if app_file.exists():
        app_file.unlink()
        print(f"Removed {app_file}")
    else:
        print(f"AppBox for {app_name} not found.")

    metadata_dir = repo_base_dir / "apps" / app_name
    if metadata_dir.exists():
        shutil.rmtree(metadata_dir, ignore_errors=True)
        print(f"Removed metadata for {app_name}")

    print(f"{app_name} has been successfully removed.")


def update(app_name):
    """Update an AppBox using Zsync."""
    print(f"Updating {app_name}...")

    app_file = repo_base_dir / f"{app_name}.AppBox"
    zsync_url = f"https://example.com/{app_name}.zsync"  # Placeholder URL

    if not app_file.exists():
        print(f"Error: {app_name} is not installed.")
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

    if not backup_file.exists():
        print(f"No downgrade backup found for {app_name}.")
        return

    # -- Decompress the backup.

    try:
        subprocess.run(["zstd", "--decompress", str(backup_file), "-o", str(app_file)], check=True)
        print(f"{app_name} downgraded successfully!")
    except subprocess.CalledProcessError:
        print(f"Error downgrading {app_name}.")


# -- Export functions
__all__ = ["install", "remove", "update", "downgrade"]
