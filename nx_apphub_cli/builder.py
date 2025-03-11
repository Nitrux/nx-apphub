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
from nx_apphub_cli.utils import ensure_appimagetool, cleanup_cache


# -- Base working directory for all packages.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"
appimagetool_path = local_bin / "appimagetool"


# -- Get an icon from the default icon themes. Search in /usr/share/icons and use /usr/share/pixmaps as fallback.

icon_themes = ["breeze-dark", "breeze", "Adwaita", "Luv", "hicolor"]

def find_system_icon(icon_name, preferred_theme=None):
    """Search for the system icon in the specified or standard themes, preferring exact matches."""
    search_themes = [preferred_theme] + icon_themes if preferred_theme else icon_themes
    icon_exts = [".png", ".svg", ".xpm"]

    for ext in icon_exts:
        for theme in search_themes:
            theme_path = Path(f"/usr/share/icons/{theme}")
            if theme_path.exists():
                exact_match = theme_path / f"{icon_name}{ext}"
                if exact_match.exists():
                    return exact_match
                for icon_file in theme_path.rglob(f"{icon_name}{ext}"):
                    return icon_file

    pixmaps_path = Path("/usr/share/pixmaps")
    for ext in icon_exts:
        exact_match = pixmaps_path / f"{icon_name}{ext}"
        if exact_match.exists():
            return exact_match
        for icon_file in pixmaps_path.glob(f"{icon_name}{ext}"):
            return icon_file

    return None


# -- Create the AppRun for the AppImage.

def generate_apprun(app_dir, exec_path):
    """Generate the AppRun script dynamically inside the AppImage."""
    apprun_path = app_dir / "AppRun"
    apprun_script = f"""#!/usr/bin/env bash

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
#   Copyright <2025> <Nitrux Latinoamericana <hello@nxos.org>>                                                                                                              #
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


# -- Exit on errors.

set -eu


# -- Get the running directory of the AppImage.

realpath=$(readlink -f "$0")
running_dir=$(dirname "$realpath")


# -- Set environment variables for proper execution inside the AppImage.

export PATH="$running_dir/usr/bin:$running_dir/usr/sbin:$running_dir/usr/games:$running_dir/bin:$running_dir/sbin:$PATH"
export LD_LIBRARY_PATH="${{LD_LIBRARY_PATH:-}}:$running_dir/usr/lib:$running_dir/usr/lib/x86_64-linux-gnu:$running_dir/lib"
export XDG_DATA_DIRS="${{XDG_DATA_DIRS:-}}:$running_dir/usr/share"
export GSETTINGS_SCHEMA_DIR="${{GSETTINGS_SCHEMA_DIR:-}}:$running_dir/usr/share/glib-2.0/schemas"
export QT_PLUGIN_PATH="${{QT_PLUGIN_PATH:-}}:$running_dir/usr/lib/qt5/plugins"


# -- Run the application.
exec "$running_dir/{exec_path}" "$@"
"""

    with open(apprun_path, "w") as f:
        f.write(apprun_script)

    apprun_path.chmod(0o755)
    print(f"Generated AppRun at {apprun_path}")


def setup_appimage_directories(app_name, binary_path):
    """Ensure required directories exist for AppImage building."""
    package_dir = app_base_dir / app_name
    app_dir = package_dir / "AppDir"
    bin_dir = app_dir / "usr/bin"

    app_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    extracted_binary_path = app_dir / binary_path.lstrip("/")
    return extracted_binary_path, app_dir


def fix_desktop_entry(app_name, app_dir, binary_path):
    """Ensure the AppImage contains a valid .desktop file."""
    desktop_file_path = app_dir / f"{app_name}.desktop"
    if not desktop_file_path.exists():
        print(f"No .desktop file found for {app_name}. Generating a minimal one...")
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec=/usr/bin/{binary_path.name}
Terminal=true
Categories=Utility;
Icon={app_name}
"""
        with open(desktop_file_path, "w") as f:
            f.write(desktop_content)

    # -- Read existing .desktop file before modifying it.

    with open(desktop_file_path, "r") as f:
        lines = f.readlines()

    # -- Update Exec line if needed.

    updated_lines = []
    for line in lines:
        if line.startswith("Exec=") and f"/usr/bin/{binary_path.name}" not in line:
            updated_lines.append(f"Exec=/usr/bin/{binary_path.name}\n")
        else:
            updated_lines.append(line)

    with open(desktop_file_path, "w") as f:
        f.writelines(updated_lines)
    print(f"Fixed Exec path in {desktop_file_path}")


def copy_system_icon(app_name, app_dir, icon_path):
    """Copy the system icon if none exists in the AppDir."""
    icon_dest = app_dir / f"{app_name}.png"

    if icon_path:
        icon_path = Path(icon_path)
        if icon_path.exists():
            shutil.copy(icon_path, icon_dest)
            print(f"Copied provided icon to {icon_dest}")
            return

    print(f"No provided icon for {app_name}. Searching for a fallback system icon...")
    system_icon = find_system_icon(app_name) or find_system_icon("utilities-terminal")
    if system_icon:
        shutil.copy(system_icon, icon_dest)
        print(f"Copied system icon to {icon_dest}")
    else:
        print("Warning: No system icon found! AppImage might fail to build.")


def build_appimage(app_name, app_dir, output_file):
    """Run appimagetool to build the AppImage."""
    print(f"Building AppImage: {output_file}")
    try:
        subprocess.run([str(appimagetool_path), str(app_dir), str(output_file)], check=True)
        print(f"AppImage built successfully: {output_file}")

        # -- Clean cache after successful build.

        cleanup_cache(app_name)

    except subprocess.CalledProcessError as e:
        print(f"Error: AppImage build failed! {e}")
        exit(1)


def prepare_appimage(config, install_mode=False, quiet=False):
    """Prepare and build an AppImage with the version in the filename."""
    
    app_name = config["buildinfo"]["name"]
    version = config["buildinfo"].get("version", "unknown")
    binary_path = config["buildinfo"].get("binarypath")

    if not binary_path:
        print(f"Error: No binary path specified for {app_name}. Aborting.")
        return

    extracted_binary_path, app_dir = setup_appimage_directories(app_name, binary_path)

    if not extracted_binary_path.exists():
        print(f"Error: Binary {extracted_binary_path} not found! AppImage might fail.")
        return

    ensure_appimagetool()

    # -- Move binary to correct location BEFORE generating AppRun.

    bin_dir = app_dir / "usr/bin"
    new_binary_path = bin_dir / extracted_binary_path.name

    if extracted_binary_path != new_binary_path:
        shutil.move(str(extracted_binary_path), str(new_binary_path))
        if not quiet:
            print(f"Moved {extracted_binary_path} → {new_binary_path}")

    # -- Generate metadata & AppRun.

    generate_apprun(app_dir, f"./usr/bin/{new_binary_path.name}")
    fix_desktop_entry(app_name, app_dir, new_binary_path)
    copy_system_icon(app_name, app_dir, config["buildinfo"].get("iconpath", None))

    # -- Determine the final AppImage location.

    output_dir = Path.home() / ".local/bin/nx-apphub" if install_mode else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Use versioned filename for tracking updates.

    file_ext = "AppBox" if install_mode else "AppImage"
    output_file = output_dir / f"{app_name}-{version}-{platform.machine().lower()}.{file_ext}"

    # -- Build final AppImage.

    build_appimage(app_name, app_dir, output_file)

    if not quiet:
        print(f"AppImage created: {output_file}")
