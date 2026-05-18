#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from .exceptions import BuildError
from .config import get_apprunconf_value
from .utils import cleanup_cache, get_appimagetool, get_go_appimagetool, get_uruntime, get_architecture
from .apprun import generate_apprun
from .console import print_success, print_error, print_info, print_blank

# <---
# --->
# -- Base working directory for all packages.

app_base_dir = Path.home() / ".cache/nx-apphub-cli"
local_bin = Path.home() / ".local/bin"


def setup_appimage_directories(app_name, binary_path):
    """Ensure required directories exist for building."""
    package_dir = app_base_dir / app_name
    app_dir = package_dir / "AppDir"
    bin_dir = app_dir / "usr/bin"

    app_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    extracted_binary_path = app_dir / binary_path.lstrip("/")
    return extracted_binary_path, app_dir


# -- Get an icon from the default icon themes. Search in /usr/share/icons and use /usr/share/pixmaps as a fallback.

icon_themes = ["breeze-dark", "breeze", "Adwaita", "Luv", "hicolor"]


def find_system_icon(icon_name, app_dir, preferred_theme=None):
    """Search for the system icon in the specified or standard themes, preferring exact matches."""
    search_themes = [preferred_theme] + icon_themes if preferred_theme else icon_themes
    icon_exts = [".png", ".svg", ".xpm"]

    for ext in icon_exts:
        for theme in search_themes:
            theme_path = app_dir / f"usr/share/icons/{theme}"
            if theme_path.exists():
                exact_match = theme_path / f"{icon_name}{ext}"
                if exact_match.exists():
                    return exact_match
                for icon_file in theme_path.rglob(f"{icon_name}{ext}"):
                    return icon_file

    pixmaps_path = app_dir / "usr/share/pixmaps"
    for ext in icon_exts:
        exact_match = pixmaps_path / f"{icon_name}{ext}"
        if exact_match.exists():
            return exact_match
        for icon_file in pixmaps_path.glob(f"{icon_name}{ext}"):
            return icon_file

    return None


def get_icon_name_from_desktop(app_dir):
    """Attempt to extract icon name from a .desktop file."""
    for file in app_dir.glob("*.desktop"):
        with file.open(encoding="utf-8") as f:
            for line in f:
                if line.startswith("Icon="):
                    return line.strip().split("=", 1)[1]
    return None


def copy_system_icon(app_name, app_dir, config, icon_path, quiet=True):
    """Copy the icon referenced in the .desktop file to the root of AppDir with the correct name and extension."""

    icon_name = get_icon_name_from_desktop(app_dir) or app_name

    if icon_path:
        icon_path = Path(icon_path)
        if icon_path.exists():
            icon_dest = app_dir / f"{icon_name}{icon_path.suffix}"
            shutil.copy(icon_path, icon_dest)
            if not quiet:
                print_success(f"Using provided icon: {icon_dest.name}", prefix="✔️")
            return

    integration_type = config.get("integration", {}).get("type", "gui")

    if integration_type == "wm":
        system_icon = find_system_icon("preferences-system-windows", Path("/"))
    else:
        system_icon = (
            find_system_icon(icon_name, app_dir)
            or find_system_icon("utilities-terminal", Path("/"))
        )

    if system_icon:
        icon_dest = app_dir / f"{icon_name}{system_icon.suffix}"
        shutil.copy(system_icon, icon_dest)
        if not quiet:
            print_success(f"Using icon from AppDir: {icon_dest.name}", prefix="✔️")
        return

    raise BuildError(
        f"No icon found for '{icon_name}'. "
        "This usually happens when the icon theme is missing in the AppDir or build system."
    )


def fix_desktop_entry(app_name, app_dir, binary_path, hide_from_menu=False, preferred_launcher=""):
    """Ensure the AppDir contains a valid .desktop file."""

    desktop_dir = app_dir / "usr/share/applications"
    existing_desktops = list(desktop_dir.glob("*.desktop")) if desktop_dir.exists() else []

    def is_valid_desktop(path):
        try:
            with path.open(encoding="utf-8") as f:
                lines = f.readlines()
                has_name = any(line.strip().startswith("Name=") for line in lines)
                has_exec = any(line.strip().startswith("Exec=") for line in lines)
                return has_name and has_exec
        except Exception:
            return False

    desktop_file_path = None

    # -- Use explicit launcher when requested.

    if preferred_launcher:
        preferred_path = desktop_dir / preferred_launcher
        if preferred_path.exists() and is_valid_desktop(preferred_path):
            desktop_file_path = preferred_path
        else:
            raise BuildError(
                f"Requested integration.launcher '{preferred_launcher}' was not found "
                f"or is invalid in: {desktop_dir}"
            )

    # -- Prefer exact match.

    if not desktop_file_path:
        exact_match = desktop_dir / f"{app_name}.desktop"
        if exact_match.exists() and is_valid_desktop(exact_match):
            desktop_file_path = exact_match
        else:

            # -- Look for partial matches.

            for file in existing_desktops:
                if app_name in file.name and is_valid_desktop(file):
                    desktop_file_path = file
                    break

            # -- Fallback to any valid one.

            if not desktop_file_path:
                for file in existing_desktops:
                    if is_valid_desktop(file):
                        desktop_file_path = file
                        break

    if desktop_file_path:

        # -- Copy to top-level AppDir.

        target_path = app_dir / desktop_file_path.name
        if desktop_file_path != target_path:
            shutil.copy(desktop_file_path, target_path)
        desktop_file_path = target_path

        # -- Patch Exec if necessary.

        lines = desktop_file_path.read_text(encoding="utf-8").splitlines()
        updated_lines = []
        found_nodisplay = False

        for line in lines:
            if line.startswith("Exec="):
                if f"/usr/bin/{binary_path.name}" not in line:
                    updated_lines.append(f"Exec=/usr/bin/{binary_path.name}")
                else:
                    updated_lines.append(line)
            elif line.startswith("NoDisplay="):
                found_nodisplay = True
                updated_lines.append(line)
            else:
                updated_lines.append(line)

        if hide_from_menu and not found_nodisplay:
            updated_lines.append("NoDisplay=true")

        desktop_file_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    else:

        # -- Generate new minimal .desktop.

        desktop_file_path = app_dir / f"{app_name}.desktop"
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec=/usr/bin/{binary_path.name}
Terminal=true
Categories=Utility;
Icon={app_name}
{'NoDisplay=true' if hide_from_menu else ''}
"""
        desktop_file_path.write_text(desktop_content.strip() + "\n", encoding="utf-8")


def prepare_window_manager_launcher(app_dir, preferred_launcher=""):
    """Locate and prepare a session launcher (.desktop) for a window manager inside the AppDir.

    Prioritize Wayland session launchers over X11.
    """
    session_dirs = [
        app_dir / "usr/share/wayland-sessions",
        app_dir / "usr/share/xsessions"
    ]

    if preferred_launcher:
        for session_dir in session_dirs:
            launcher_path = session_dir / preferred_launcher
            if launcher_path.is_file():
                target_path = app_dir / launcher_path.name
                shutil.copy(launcher_path, target_path)

                with target_path.open("r", encoding="utf-8") as f:
                    lines = f.readlines()

                updated_lines = []
                icon_found = False
                nodisplay_found = False

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("Type="):
                        updated_lines.append("Type=Application\n")
                    elif stripped.startswith("Icon="):
                        updated_lines.append("Icon=preferences-system-windows\n")
                        icon_found = True
                    elif stripped.startswith("NoDisplay="):
                        updated_lines.append("NoDisplay=true\n")
                        nodisplay_found = True
                    else:
                        updated_lines.append(line if line.endswith("\n") else line + "\n")

                if not icon_found:
                    updated_lines.append("Icon=preferences-system-windows\n")
                if not nodisplay_found:
                    updated_lines.append("NoDisplay=true\n")

                with target_path.open("w", encoding="utf-8") as f:
                    f.writelines(updated_lines)

                return target_path

        raise BuildError(
            f"Requested integration.launcher '{preferred_launcher}' was not found in "
            "usr/share/wayland-sessions or usr/share/xsessions."
        )

    for session_dir in session_dirs:
        if session_dir.is_dir():
            matches = sorted(session_dir.glob("*.desktop"))
            if matches:
                launcher_path = matches[0]
                target_path = app_dir / launcher_path.name

                shutil.copy(launcher_path, target_path)

                with target_path.open("r", encoding="utf-8") as f:
                    lines = f.readlines()

                updated_lines = []
                icon_found = False
                nodisplay_found = False

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("Type="):
                        updated_lines.append("Type=Application\n")
                    elif stripped.startswith("Icon="):
                        updated_lines.append("Icon=preferences-system-windows\n")
                        icon_found = True
                    elif stripped.startswith("NoDisplay="):
                        updated_lines.append("NoDisplay=true\n")
                        nodisplay_found = True
                    else:
                        updated_lines.append(line if line.endswith("\n") else line + "\n")

                if not icon_found:
                    updated_lines.append("Icon=preferences-system-windows\n")
                if not nodisplay_found:
                    updated_lines.append("NoDisplay=true\n")

                with target_path.open("w", encoding="utf-8") as f:
                    f.writelines(updated_lines)

                return target_path

    return None


def patch_binary_rpath(binary_path, config):
    """Patch the RPATH of the application binary to use $ORIGIN with the correct paths."""

    # -- Fetch settings from YAML.

    setlibpath = get_apprunconf_value(config, "setlibpath", default="/usr/lib", expected_type=str)

    # -- Determine multiarch triplet dynamically.

    arch_map = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }

    arch = get_architecture()
    multiarch_triplet = arch_map.get(arch)

    if not multiarch_triplet:
        raise BuildError(f"Unsupported architecture detected: {arch}. Aborting.")

    # -- Patch the RPATH of the executable; the paths are relative to the path of the binary.

    try:
        rpath_parts = [

            # -- Prefer AppDir/usr first.

            f"$ORIGIN/../..{setlibpath}",
            f"$ORIGIN/../..{setlibpath}/{multiarch_triplet}",
            f"$ORIGIN/../..{setlibpath}64",

            # -- Qt-specific plugin locations under /usr.

            f"$ORIGIN/../../..{setlibpath}/{multiarch_triplet}/qt5/qml",
            f"$ORIGIN/../../..{setlibpath}/{multiarch_triplet}/qt6/qml",
            f"$ORIGIN/../../..{setlibpath}/{multiarch_triplet}/qt5/plugins",
            f"$ORIGIN/../../..{setlibpath}/{multiarch_triplet}/qt6/plugins",
            f"$ORIGIN/../../..{setlibpath}/qt5/libexec",
            f"$ORIGIN/../../..{setlibpath}/qt5/bin",
            f"$ORIGIN/../../..{setlibpath}/qt6/libexec",
            f"$ORIGIN/../../..{setlibpath}/qt6/bin",

            # -- /lib multiarch.

            f"$ORIGIN/../../lib/{multiarch_triplet}",
            f"$ORIGIN/../../lib64/{multiarch_triplet}",

            # -- /lib non-multiarch (add these).

            f"$ORIGIN/../../lib",
            f"$ORIGIN/../../lib64",
        ]
        extras = config.get("apprunconf", {}).get("extra_rpaths", [])
        if isinstance(extras, str):
            extras = [extras]
        elif isinstance(extras, tuple):
            extras = list(extras)
        extras = [p for p in extras if isinstance(p, str) and p.strip()]
        ordered = []
        seen = set()
        for p in rpath_parts + extras:
            if p not in seen:
                ordered.append(p)
                seen.add(p)

        rpath_value = ":".join(ordered)

        subprocess.run(
            ["patchelf", "--set-rpath", rpath_value, "--force-rpath", str(binary_path)],
            check=True
        )
        print_success(f"Patched RPATH for: {binary_path}", prefix="🩹")
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Failed to patch RPATH for {binary_path}: {e}") from e


def package_appdir(app_name, app_dir, output_file, appimagetool_binary, runtime, config, quiet=True):
    """Package the AppDir."""
    if not quiet:
        print_blank()
        print_info(f"Packaging AppDir: {output_file} ...", prefix="🛠")

    try:
        env = os.environ.copy()
        cmd = []

        if runtime == "go":
            env["VERSION"] = config["buildinfo"]["version"]
            cmd = [str(appimagetool_binary), str(app_dir)]
        elif runtime == "uruntime":
            cmd = [
                str(appimagetool_binary),
                "--appimage-mkdwarfs",
                "-f",
                "--set-owner", "0",
                "--set-group", "0",
                "--no-history",
                "--no-create-timestamp",
                "--compression", "zstd:level=22",
                "-S22",
                "-B6",
                "--header", str(appimagetool_binary),
                "-i", str(app_dir),
                "-o", str(output_file)
            ]
        else:
            cmd = [str(appimagetool_binary), str(app_dir), str(output_file)]

        with open(os.devnull, 'w') as devnull:
            subprocess.run(
                cmd,
                check=True,
                stdout=sys.stdout if not quiet else devnull,
                stderr=sys.stderr if not quiet else devnull,
                env=env
            )

        if runtime == "go":
            output_dir = output_file.parent
            appimages = list(output_dir.glob("*.AppImage"))

            if not appimages:
                cleanup_cache(app_name)
                raise BuildError("No file found after Go appimagetool build.")

            built_appimage = appimages[0]
            built_appimage.rename(output_file)
            output_file.chmod(0o755)

        if runtime == "uruntime":
            output_file.chmod(0o755)

        if not output_file.exists():
            cleanup_cache(app_name)
            raise BuildError(f"Expected file not found: {output_file}")

        if not quiet:
            print_success(f"Built successfully: {output_file}")

        cleanup_cache(app_name)

    except subprocess.CalledProcessError as e:
        cleanup_cache(app_name)
        raise BuildError(f"Build failed! {e}") from e


def prepare_appimage(config, install_mode=False, quiet=True, yaml_dir=None):
    """Prepare and build with the version in the filename."""

    app_name = config["buildinfo"]["name"]
    version = config["buildinfo"].get("version", "unknown")
    binary_path = config["buildinfo"].get("binarypath")

    if not binary_path:
        cleanup_cache(app_name)
        raise BuildError(f"No binary path specified for {app_name}. Aborting.")

    # -- Ensure AppDir is properly set up before running any commands.

    extracted_binary_path, app_dir = setup_appimage_directories(app_name, binary_path)

    # -- Automatically copy scripts from scripts/ directory if it exists.

    if yaml_dir:
        scripts_dir = yaml_dir / "scripts"
        if scripts_dir.exists() and scripts_dir.is_dir():
            dest_bin_dir = app_dir / "usr" / "bin"
            dest_bin_dir.mkdir(parents=True, exist_ok=True)

            script_files = [f for f in scripts_dir.iterdir() if f.is_file()]
            if script_files:
                if not quiet:
                    print_info(f"Copying {len(script_files)} script(s) from {scripts_dir.name}/ to AppDir...", prefix="📜")

                for script_file in script_files:
                    dest_file = dest_bin_dir / script_file.name
                    shutil.copy(script_file, dest_file)
                    dest_file.chmod(0o755)
                    if not quiet:
                        print_success(f"   {script_file.name} → /usr/bin/{script_file.name}", prefix="✓")

                if not quiet:
                    print_blank()

    if not extracted_binary_path.exists():
        cleanup_cache(app_name)
        raise BuildError(f"Binary {extracted_binary_path} not found!. Aborting.")

    # -- Run prebuild commands inside the AppDir.

    prebuild_commands = config.get("apprunconf", {}).get("prebuild_commands", [])
    if prebuild_commands:
        print_info(f"Running prebuild commands for {app_name} inside {app_dir}...", prefix="🔧")
        print_blank()
        env = os.environ.copy()
        env["APPDIR"] = str(app_dir)

        for cmd in prebuild_commands:
            cmd_resolved = cmd.replace("$APPDIR", str(app_dir))
            try:
                subprocess.run(
                    cmd_resolved,
                    shell=True,
                    check=True,
                    env=env,
                    cwd=app_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
                print_info(f"    Command executed: {cmd_resolved}", prefix="🤖")
                print_blank()
            except subprocess.CalledProcessError as e:
                cleanup_cache(app_name)
                err_output = e.stderr.decode(errors='replace')
                raise BuildError(
                    f"Failed to execute prebuild command: '{cmd_resolved}'.\n"
                    f"Output: {err_output}"
                ) from e


    # -- Select runtime tool based on runtime.

    runtime = config.get("buildinfo", {}).get("runtime", "classic")

    if runtime == "classic":
        appimagetool_binary = get_appimagetool(quiet=quiet)
    elif runtime == "go":
        appimagetool_binary = get_go_appimagetool(quiet=quiet)
    elif runtime == "uruntime":
        appimagetool_binary = get_uruntime(quiet=quiet)
    else:
        cleanup_cache(app_name)
        raise BuildError(f"Unknown runtime '{runtime}' specified in buildinfo.")

    # -- Move binary to correct location BEFORE generating AppRun.

    bin_dir = app_dir / "usr/bin"
    new_binary_path = bin_dir / extracted_binary_path.name

    if extracted_binary_path != new_binary_path:
        shutil.move(str(extracted_binary_path), str(new_binary_path))
        if not quiet:
            print_info(f"Moved binary: {extracted_binary_path} → {new_binary_path}", prefix="📂")

    # -- Generate metadata & AppRun.

    print_info(f"Generating AppRun and metadata for: {app_name}...", prefix="🧳")
    print_blank()
    generate_apprun(app_dir, config)

    integration = config.get("integration", {})
    integration_type = integration.get("type", "gui")
    integration_launcher = integration.get("launcher", "")
    if integration_launcher is None:
        integration_launcher = ""
    if not isinstance(integration_launcher, str):
        cleanup_cache(app_name)
        raise BuildError("'integration.launcher' must be a string.")
    integration_launcher = integration_launcher.strip()
    if integration_launcher and "/" in integration_launcher:
        cleanup_cache(app_name)
        raise BuildError("'integration.launcher' must be a desktop file name, not a path.")
    if integration_launcher and not integration_launcher.endswith(".desktop"):
        cleanup_cache(app_name)
        raise BuildError("'integration.launcher' must end with '.desktop'.")

    hide_from_menu = integration_type == "cli"

    if integration_type == "wm":
        wm_launcher = prepare_window_manager_launcher(app_dir, preferred_launcher=integration_launcher)
        if not wm_launcher:
            cleanup_cache(app_name)
            raise BuildError("No session launcher (.desktop) found in Wayland/X11 session directories.")
    else:
        fix_desktop_entry(
            app_name,
            app_dir,
            new_binary_path,
            hide_from_menu=hide_from_menu,
            preferred_launcher=integration_launcher
        )
    try:
        copy_system_icon(app_name, app_dir, config, config["buildinfo"].get("iconpath", None))
    except (FileNotFoundError, BuildError) as e:
        cleanup_cache(app_name)
        raise BuildError(str(e)) from e

    # -- Determine the final file location.

    output_dir = Path.home() / ".local/bin/nx-apphub" if install_mode else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Use versioned filename for tracking updates.

    file_ext = "AppBox" if install_mode else "AppImage"
    output_file = output_dir / f"{app_name}-{version}-{platform.machine().lower()}.{file_ext}"

    # -- Patch binary RPATH before building.

    patch_binary_rpath(str(new_binary_path), config)

    # -- Build.

    package_appdir(app_name, app_dir, output_file, appimagetool_binary, runtime, config, quiet)

    # -- Create build marker file for AppBoxes to prove official build.

    if install_mode:
        nx_apphub_cli_dir = Path.home() / ".local/share/nx-apphub-cli"
        build_markers_dir = nx_apphub_cli_dir / ".built"
        build_markers_dir.mkdir(parents=True, exist_ok=True)

        marker_filename = f"{app_name}-{version}-{platform.machine().lower()}"
        marker_file = build_markers_dir / marker_filename

        marker_content = f"""# This file is a build marker created by nx-apphub-cli
# DO NOT manually create or modify this file
# Doing so may cause integration issues and is not supported
# Built: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# AppBox: {output_file.name}
"""

        marker_file.write_text(marker_content)

        if not quiet:
            print_info(f"Build marker created: {marker_file}", prefix="✓")

    if not quiet:
        print_info(f"Bundle ready: {output_file}", prefix="📦")
        print_blank()
