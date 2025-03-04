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

import subprocess
import os
from pathlib import Path
import shutil
import platform
import requests


# -- Base working directory for all packages.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"
appimagetool_path = local_bin / "appimagetool"

icon_themes = ["breeze-dark", "breeze", "Adwaita", "Luv", "hicolor"]

def find_system_icon(icon_name, preferred_theme=None):
    """Search for the system icon in user-specified or standard themes."""
    search_themes = [preferred_theme] + icon_themes if preferred_theme else icon_themes
    icon_exts = [".png", ".svg", ".xpm"]

    for theme in search_themes:
        theme_path = Path(f"/usr/share/icons/{theme}")
        if theme_path.exists():
            for ext in icon_exts:
                for icon_file in theme_path.rglob(f"{icon_name}{ext}"):
                    return icon_file
    return None


def get_architecture():
    """Return the system architecture for downloading the correct AppImageTool version."""
    arch_map = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    return arch_map.get(platform.machine(), "x86_64")


def ensure_appimagetool():
    """Ensure appimagetool is available by downloading it if missing."""
    if not appimagetool_path.exists():
        print("appimagetool not found! Downloading from GitHub...")
        local_bin.mkdir(parents=True, exist_ok=True)

        # -- Detect system architecture and download the correct executable.

        arch = get_architecture()
        tool_url = f"https://github.com/AppImage/appimagetool/releases/latest/download/appimagetool-{arch}.AppImage"

        try:
            response = requests.get(tool_url, stream=True)
            if response.status_code == 200:
                with open(appimagetool_path, "wb") as tool_file:
                    for chunk in response.iter_content(1024):
                        tool_file.write(chunk)
                appimagetool_path.chmod(0o755)
                print(f"appimagetool downloaded and saved to {appimagetool_path}")
            else:
                print(f"Failed to download appimagetool from {tool_url}!")
                exit(1)
        except Exception as e:
            print(f"Error downloading appimagetool: {e}")
            exit(1)


def cleanup_cache(package_name):
    """Remove the entire package cache directory after building the AppImage."""
    package_dir = app_base_dir / package_name
    if package_dir.exists():
        print(f"Cleaning up cache directory for {package_name}...")
        shutil.rmtree(package_dir, ignore_errors=True)
        print(f"Cache directory for {package_name} removed.")


def generate_apprun(app_dir, exec_path):
    """Generate the AppRun script dynamically inside the AppImage."""
    apprun_path = app_dir / "AppRun"
    apprun_script = f"""#!/usr/bin/env bash

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
#   Copyright <2025> <Nitrux Latinoamericana <hello@nxos.org>>                                                                                                                   #
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

set -eu

# -- Get the running directory of the AppImage.

realpath=$(readlink -f "$0")
running_dir=$(dirname "$realpath")


# -- Set environment variables for proper execution inside the AppImage.

export PATH="$running_dir/usr/bin:$running_dir/usr/sbin:$running_dir/usr/games:$running_dir/bin:$running_dir/sbin:$PATH"
export LD_LIBRARY_PATH="$running_dir/usr/lib:$running_dir/usr/lib/x86_64-linux-gnu:$running_dir/lib:$LD_LIBRARY_PATH"
export PYTHONPATH="$running_dir/usr/share/pyshared:$PYTHONPATH"
export PYTHONHOME="$running_dir/usr"
export PYTHONDONTWRITEBYTECODE=1
export XDG_DATA_DIRS="$running_dir/usr/share:$XDG_DATA_DIRS"
export GSETTINGS_SCHEMA_DIR="$running_dir/usr/share/glib-2.0/schemas:$GSETTINGS_SCHEMA_DIR"
export QT_PLUGIN_PATH="$running_dir/usr/lib/qt5/plugins:$QT_PLUGIN_PATH"


# -- Use defined executable or extract from .desktop file.

exec_cmd="{exec_path}"

if [[ -z "$exec_cmd" ]]; then
    desktop_file=$(find "$running_dir" -name '*.desktop' | head -n 1)
    if [[ -n "$desktop_file" ]]; then
        exec_cmd=$(grep -m1 '^Exec=' "$desktop_file" | cut -d'=' -f2 | awk '{{print $1}}')
        if [[ -z "$exec_cmd" ]]; then
            echo "Error: No Exec line found in $desktop_file, and no executable set in configuration!"
            exit 1
        fi
    else
        echo "Error: No .desktop file found and no executable defined!"
        exit 1
    fi
fi


# -- Run the application.

exec "$running_dir/$exec_cmd" "$@"
"""

    with open(apprun_path, "w") as f:
        f.write(apprun_script)

    apprun_path.chmod(0o755)
    print(f"Generated AppRun at {apprun_path}")


def prepare_appimage(config):
    """Prepare and build AppImage."""
    app_name = config['buildinfo']['name']

    # -- Define per-package directories dynamically.

    package_dir = app_base_dir / app_name
    app_dir = package_dir / "AppDir"
    bin_dir = app_dir / "usr/bin"
    deb_dir = package_dir / "debs"

    # -- Rename the AppImages built with nx-apphub-cli to AppBox to differentiate them from user-added AppImages.

    output_path = Path.cwd() / f"{app_name}.AppBox"

    binary_path = config['buildinfo']['binarypath']
    desktop_path = config['buildinfo'].get('desktoppath', None)
    icon_path = config['buildinfo'].get('iconpath', None)

    # -- Ensure AppDir exists.

    app_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    extracted_binary_path = app_dir / binary_path.lstrip("/")
    
    # -- Ensure binary exists before using new_binary_path.

    if extracted_binary_path.exists():
        new_binary_path = bin_dir / extracted_binary_path.name
        shutil.move(str(extracted_binary_path), str(new_binary_path))
        print(f"Moved {extracted_binary_path} → {new_binary_path}")
    else:
        print(f"Error: Binary {extracted_binary_path} not found! AppImage might fail.")
        return

    # -- Ensure appimagetool is available.

    ensure_appimagetool()

    # -- Generate a minimal .desktop file if none exists.

    desktop_file_path = app_dir / f"{app_name}.desktop"
    if not desktop_path or not (app_dir / desktop_path.lstrip("/")).exists():
        print(f"No .desktop file found for {app_name}. Generating a minimal one...")

        desktop_content = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec=/usr/bin/{new_binary_path.name}
Terminal=true
Categories=Utility;
Icon={app_name}
"""

        with open(desktop_file_path, "w") as f:
            f.write(desktop_content)

    # -- Ensure the .desktop file exists, otherwise, fail.

    if not desktop_file_path.exists():
        print(f"Error: .desktop file not found in {app_dir}. Aborting.")
        return 

    # -- Always fix the Exec path inside the .desktop file.

    with open(desktop_file_path, "r") as f:
        lines = f.readlines()
    with open(desktop_file_path, "w") as f:
        for line in lines:
            if line.startswith("Exec="):
                f.write(f"Exec=/usr/bin/{new_binary_path.name}\n")
            else:
                f.write(line)
    print(f"Fixed Exec path in {desktop_file_path}")

    # -- Copy system icon if needed.

    icon_dest = app_dir / f"{app_name}.png"
    if not icon_path or not (app_dir / icon_path.lstrip("/")).exists():
        print(f"No icon found for {app_name}. Searching for system icon: utilities-terminal")

        system_icon = find_system_icon("utilities-terminal")
        if system_icon:
            shutil.copy(system_icon, icon_dest)
            print(f"Copied system icon to {icon_dest}")
        else:
            print("Warning: No system icon found! AppImage might fail to build.")

    # -- Ensure there's an AppRun inside the AppImage.

    generate_apprun(app_dir, f"./usr/bin/{new_binary_path.name}")

    # -- Fix the .desktop file to use the correct Exec path.

    if desktop_file_path.exists():
        with open(desktop_file_path, "r") as f:
            lines = f.readlines()
        with open(desktop_file_path, "w") as f:
            for line in lines:
                if line.startswith("Exec="):
                    f.write(f"Exec=/usr/bin/{new_binary_path.name}\n")
                else:
                    f.write(line)
        print(f"Fixed Exec path in {desktop_file_path}")

    # -- Build AppImage.

    print(f"Building AppImage: {output_path}")
    try:
        subprocess.run([str(appimagetool_path), str(app_dir), str(output_path)], check=True)
        print("AppImage built successfully!")

        # -- Rename to .AppBox after creation.

        final_path = output_path.with_suffix(".AppBox")
        shutil.move(output_path, final_path)
        print(f"Renamed output to {final_path}")

        # -- Cleanup after successful build.

        cleanup_cache(app_name)

    except subprocess.CalledProcessError as e:
        print(f"Error: AppImage build failed! {e}")
        exit(1)
