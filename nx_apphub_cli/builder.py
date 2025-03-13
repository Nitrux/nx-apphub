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
from nx_apphub_cli.utils import get_appimagetool, cleanup_cache, get_architecture
from nx_apphub_cli.config import get_apprunconf_value
from datetime import datetime


# -- Base working directory for all packages.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"
appimagetool_path = local_bin / "appimagetool"

def setup_appimage_directories(app_name, binary_path):
    """Ensure required directories exist for AppImage building."""
    package_dir = app_base_dir / app_name
    app_dir = package_dir / "AppDir"
    bin_dir = app_dir / "usr/bin"

    app_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    extracted_binary_path = app_dir / binary_path.lstrip("/")
    return extracted_binary_path, app_dir


# -- Get an icon from the default icon themes. Search in /usr/share/icons and use /usr/share/pixmaps as a fallback.

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


def copy_system_icon(app_name, app_dir, icon_path):
    """Copy the system icon if none exists in the AppDir."""
    icon_dest = app_dir / f"{app_name}.png"

    if icon_path:
        icon_path = Path(icon_path)
        if icon_path.exists():
            shutil.copy(icon_path, icon_dest)
            print(f"Copied provided icon to {icon_dest}")
            return

    # print(f"No provided icon for {app_name}. Searching for a fallback system icon...")
    system_icon = find_system_icon(app_name) or find_system_icon("utilities-terminal")
    if system_icon:
        shutil.copy(system_icon, icon_dest)
        # print(f"Copied system icon to {icon_dest}")
    else:
        raise FileNotFoundError(f"❌ Error: No system icon found for {app_name}.")


def fix_desktop_entry(app_name, app_dir, binary_path):
    """Ensure the AppImage contains a valid .desktop file."""
    desktop_file_path = app_dir / f"{app_name}.desktop"
    if not desktop_file_path.exists():
        # print(f"No .desktop file found for {app_name}. Generating a minimal one...")
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

    # -- Read the existing .desktop file before modifying it.

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
    # print(f"Fixed Exec path in {desktop_file_path}")


def generate_apprun(app_dir, config):
    """Generate the AppRun script dynamically inside the AppImage."""
    apprun_path = app_dir / "AppRun"

    # -- Fetch settings from YAML. Exit if missing.

    exec_cmd = get_apprunconf_value(config, "exec", expected_type=str)
    setpath = get_apprunconf_value(config, "setpath", default="/usr/bin", expected_type=str)
    setlibpath = get_apprunconf_value(config, "setlibpath", default="/usr/lib", expected_type=str)
    envvars = get_apprunconf_value(config, "envvars", default={}, expected_type=dict)

    # -- Generate environment variable exports dynamically.

    env_exports = "\n".join([f'export {key}="{value}"' for key, value in envvars.items()])

    # -- Conditionally add initialization for Qt environment variables **only if they exist in envvars**

    qt_env_init = ""
    if "QT_PLUGIN_PATH" in envvars:
        qt_env_init += 'if [ -z "${QT_PLUGIN_PATH+x}" ]; then export QT_PLUGIN_PATH=""; fi\n'
    if "QT_QML_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QT_QML_IMPORT_PATH+x}" ]; then export QT_QML_IMPORT_PATH=""; fi\n'
    if "QML_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QML_IMPORT_PATH+x}" ]; then export QML_IMPORT_PATH=""; fi\n'
    if "QML2_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QML2_IMPORT_PATH+x}" ]; then export QML2_IMPORT_PATH=""; fi\n'

    # -- Determine multiarch triplet dynamically.

    arch_map = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }

    arch = get_architecture()
    multiarch_triplet = arch_map.get(arch)

    # -- Construct the script.

    current_year = datetime.now().year

    apprun_script = f"""#!/usr/bin/env bash

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
#   Copyright <{current_year}> <Nitrux Latinoamericana <hello@nxos.org>>                                                                                                              #
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

REALPATH=$(readlink -f "$0")
APPDIR=$(dirname "$REALPATH")


# -- Ensure environment variables are always set to avoid unbound variable errors.

if [ -z "${{PATH+x}}" ]; then export PATH=""; fi
if [ -z "${{LD_LIBRARY_PATH+x}}" ]; then export LD_LIBRARY_PATH=""; fi
if [ -z "${{XDG_DATA_DIRS+x}}" ]; then export XDG_DATA_DIRS=""; fi


# -- Set environment variables for proper execution inside the AppImage.

export PATH="$APPDIR{setpath}:$APPDIR/usr/sbin:$PATH"
export LD_LIBRARY_PATH="$APPDIR{setlibpath}:$APPDIR{setlibpath}/{multiarch_triplet}:$APPDIR{setlibpath}64:$APPDIR{setlibpath}/{multiarch_triplet}/libproxy:$LD_LIBRARY_PATH"
export XDG_DATA_DIRS="$APPDIR/usr/share:$XDG_DATA_DIRS"


# -- Initialize Qt environment variables if required.

{qt_env_init}


# -- Additional environment variables from YAML.

{env_exports}


# -- Run the application.

exec "$APPDIR{exec_cmd}" "$@"
"""

    with open(apprun_path, "w") as f:
        f.write(apprun_script)

    apprun_path.chmod(0o755)
    # print(f"Generated AppRun at {apprun_path}")


def patch_binary_rpath(binary_path, config):
    """Patch the RPATH of the application binary to use $ORIGIN with the correct paths."""

    # -- Fetch settings from YAML.

    setlibpath = get_apprunconf_value(config, "setlibpath", "/usr/lib")

    # -- Determine multiarch triplet dynamically.

    arch_map = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }

    arch = get_architecture()
    multiarch_triplet = arch_map.get(arch)

    if not multiarch_triplet:
        print(f"❌ Error: Unsupported architecture detected: {arch}. Aborting.")
        return

    # -- Patch the RPATH of the executable.

    try:
        rpath_value = f"$ORIGIN/../..{setlibpath}:$ORIGIN/../..{setlibpath}/{multiarch_triplet}:$ORIGIN/../..{setlibpath}64:$ORIGIN/../../..{setlibpath}/{multiarch_triplet}/libproxy:$ORIGIN/../../../..{setlibpath}/{multiarch_triplet}/qt5/qml:$ORIGIN/../../../..{setlibpath}/{multiarch_triplet}/qt6/qml:$ORIGIN/../../../..{setlibpath}/{multiarch_triplet}/qt5/plugins:$ORIGIN/../../../..{setlibpath}/{multiarch_triplet}/qt6/plugins:$ORIGIN/../../../..{setlibpath}/qt5/libexec:$ORIGIN/../../../..{setlibpath}/qt5/bin:$ORIGIN/../../../..{setlibpath}/qt6/libexec:$ORIGIN/../../../..{setlibpath}/qt6/bin"
        subprocess.run(
            ["patchelf", "--set-rpath", rpath_value, "--force-rpath", binary_path],
            check=True
        )
        print(f"✔️  Patched RPATH for: {binary_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: Failed to patch RPATH for {binary_path}: {e}")


def package_appdir(app_name, app_dir, output_file, quiet=True):
    """Run appimagetool to make an AppDir into an AppImage."""
    if not quiet:
        print(f"\n🛠  Building AppImage: {output_file} ...")

    try:
        with open(os.devnull, 'w') as devnull:
            subprocess.run(
                [str(appimagetool_path), str(app_dir), str(output_file)],
                check=True,
                stdout=None if not quiet else devnull,
                stderr=None if not quiet else devnull
            )

        if not quiet:
            print(f"✅ AppImage built successfully: {output_file}")

        # -- Clean cache after successful build.

        cleanup_cache(app_name)

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: AppImage build failed! {e}")
        cleanup_cache(app_name)
        exit(1)


def prepare_appimage(config, install_mode=False, quiet=True):
    """Prepare and build an AppImage with the version in the filename."""
    
    app_name = config["buildinfo"]["name"]
    version = config["buildinfo"].get("version", "unknown")
    binary_path = config["buildinfo"].get("binarypath")

    if not binary_path:
        print(f"❌ Error: No binary path specified for {app_name}. Aborting.")
        return


    # -- Ensure AppDir is properly set up before running any commands.

    extracted_binary_path, app_dir = setup_appimage_directories(app_name, binary_path)

    if not extracted_binary_path.exists():
        print(f"❌ Error: Binary {extracted_binary_path} not found! AppImage might fail.")
        return

    # -- Run prebuild commands inside the AppDir.

    prebuild_commands = config.get("apprunconf", {}).get("prebuild_commands", [])
    if prebuild_commands:
        print(f"🔧 Running prebuild commands for {app_name} inside {app_dir}...")
        env = os.environ.copy()
        env["APPDIR"] = str(app_dir)

        for cmd in prebuild_commands:
            cmd_resolved = cmd.replace("$APPDIR", str(app_dir))
            try:
                subprocess.run(cmd_resolved, shell=True, check=True, env=env, cwd=app_dir, stderr=subprocess.PIPE)
                print(f"    🤖 Command executed: {cmd_resolved}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Error: Failed to execute prebuild command '{cmd_resolved}'.\n")
                print(f"📜 Output:\n{e.stderr.decode()}\n")
                cleanup_cache(app_name)
                return

    get_appimagetool()

    # -- Move binary to correct location BEFORE generating AppRun.

    bin_dir = app_dir / "usr/bin"
    new_binary_path = bin_dir / extracted_binary_path.name

    if extracted_binary_path != new_binary_path:
        shutil.move(str(extracted_binary_path), str(new_binary_path))
        if not quiet:
            print(f"📂 Moved binary: {extracted_binary_path} → {new_binary_path}")

    # -- Generate metadata & AppRun.

    print(f"📌 Setting up AppRun and metadata for: {app_name}...")
    generate_apprun(app_dir, config)
    fix_desktop_entry(app_name, app_dir, new_binary_path)
    copy_system_icon(app_name, app_dir, config["buildinfo"].get("iconpath", None))

    # -- Determine the final AppImage location.

    output_dir = Path.home() / ".local/bin/nx-apphub" if install_mode else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Use versioned filename for tracking updates.

    file_ext = "AppBox" if install_mode else "AppImage"
    output_file = output_dir / f"{app_name}-{version}-{platform.machine().lower()}.{file_ext}"

    # -- Patch binary RPATH before building the AppImage.

    patch_binary_rpath(str(new_binary_path), config)

    # -- Build the final AppImage.

    package_appdir(app_name, app_dir, output_file, quiet)

    if not quiet:
        print(f"📦 AppImage ready: {output_file}\n")
