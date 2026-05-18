#!/usr/bin/env python3

# SPDX-License-Identifier: BSD-3-Clause

import platform
import shutil
import subprocess
import tarfile
from pathlib import Path

from .builder import prepare_appimage
from .config import load_yaml_config
from .utils import cleanup_cache, concurrent_downloads, get_architecture
from .exceptions import ManagerError, NxAppHubError
from .console import (
    console, print_header, print_success, print_error,
    print_warning, print_info, print_message, print_blank
)

# <---
# --->
# -- Ensure directories exist.

system_arch = get_architecture()

repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
repo_dir = repo_base_dir / "repo"
backup_dir = repo_base_dir / "backups"
install_dir = Path.home() / ".local/bin/nx-apphub"

# -- Create all necessary directories.

for directory in [repo_base_dir, repo_dir, backup_dir, install_dir]:
    directory.mkdir(parents=True, exist_ok=True)


def ensure_build_marker(appbox_path: Path):
    """Ensure a build marker exists for an installed AppBox."""
    build_markers_dir = repo_base_dir / ".built"
    build_markers_dir.mkdir(parents=True, exist_ok=True)

    marker_file = build_markers_dir / appbox_path.stem
    if marker_file.exists():
        return

    marker_content = f"""# This file is a build marker created by nx-apphub-cli
# DO NOT manually create or modify this file
# Doing so may cause integration issues and is not supported
# AppBox: {appbox_path.name}
"""
    marker_file.write_text(marker_content)
    print_info(f"Build marker created: {marker_file.name}", prefix="✓")


def ensure_repo_updated():
    """Ensure the application repository is cloned and up-to-date."""

    git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"

    if repo_dir.exists() and not (repo_dir / ".git").exists():
        print_warning(f"Warning: {repo_dir} is not a valid Git repository. Removing...")
        print_blank()
        shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True, exist_ok=True)

    if (repo_dir / ".git").exists():
        try:
            status_result = subprocess.run(
                ["git", "-C", str(repo_dir), "status", "--porcelain"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            untracked = [
                line[3:]
                for line in status_result.stdout.splitlines()
                if line.startswith("??")
            ]
            if untracked:
                print_warning(f"Warning: Repository has untracked files: {', '.join(untracked)}")
                print_blank()
                print_info("Discarding untracked files...", prefix="🔹")
                print_blank()

                subprocess.run(
                    ["git", "-C", str(repo_dir), "clean", "-fd"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False
                )

            pull_result = subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False
            )
            if pull_result.returncode == 0:
                print_success("Applications repository updated.", prefix="🔄")
            else:
                print_warning("Warning: Failed to update repository. Continuing with existing version.")
                print_blank()

        except Exception as e:
            print_warning(f"Warning: Git update check failed ({e}). Continuing...")
            print_blank()

    if not (repo_dir / ".git").exists():
        print_info("Applications repository is missing or empty. Cloning fresh copy...", prefix="🔄")
        try:
            if any(repo_dir.iterdir()):
                shutil.rmtree(repo_dir)
                repo_dir.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                ["git", "clone", "--depth=1", git_repo_url, str(repo_dir)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as e:
            raise ManagerError("Failed to clone app repository. Try again.") from e
        except Exception as e:
            raise ManagerError(f"Unexpected failure during clone: {e}") from e


def install(app_names):
    """Fetch YAML metadata, build bundle, and store metadata for multiple applications."""

    if not isinstance(app_names, list):
        app_names = [app_names]

    print_header(f"⚡ Installing: {', '.join(app_names)}")

    ensure_repo_updated()

    to_build = []
    printed_installed_msg = False

    for app_name in app_names:
        app_yaml_path = repo_dir / "apps" / system_arch / app_name / "app.yml"

        if not app_yaml_path.exists():
            print_error(f"Error: No YAML found for: {app_name} ({system_arch}) in repository.")
            continue

        config = load_yaml_config(app_yaml_path)
        app_version = config["buildinfo"].get("version", "unknown")

        if not app_version or app_version == "unknown":
            print_error(f"Error: No valid version found for: {app_name}. Skipping installation.")
            print_blank()
            continue

        installed_appbox = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)
        if installed_appbox:
            parts = installed_appbox.stem.split("-")
            installed_version = "-".join(parts[1:-1]) if len(parts) > 2 else "unknown"

            if installed_version == app_version:
                print_info(f"    {app_name} is already installed (version {installed_version}). Skipping installation.")
                printed_installed_msg = True
                continue
            else:
                print_info(f"    {app_name} version mismatch: installed {installed_version}, YAML has {app_version}. Replacing...", prefix="🔄")

                old_marker_filename = installed_appbox.stem
                try:
                    installed_appbox.unlink()

                    old_marker = repo_base_dir / ".built" / old_marker_filename
                    if old_marker.exists():
                        old_marker.unlink()
                except OSError as e:
                    print_error(f"Error removing old version {installed_version}: {e}")
                    continue

        to_build.append((app_name, config))

    if printed_installed_msg:
        print_blank()

    for index, (app_name, config) in enumerate(to_build):
        repos_config = config["buildinfo"].get("distrorepo", {})
        if not repos_config:
            print_error(f"Error: No 'distrorepo' specified for {app_name}. Skipping installation.")
            print_blank()
            continue

        base_repos = repos_config if isinstance(repos_config, list) else repos_config.get("base", [])
        ppa_repos = {} if isinstance(repos_config, list) else {
            ppa["id"]: ppa for ppa in repos_config.get("ppas", [])
        }

        dependencies = config["buildinfo"].get("deps", [])

        concurrent_downloads(dependencies, base_repos, ppa_repos, app_name)

        print_blank()
        print_info("Building AppBox...", prefix="🛠")
        print_blank()
        prepare_appimage(config, install_mode=True)

        built_appbox = install_dir / f"{app_name}-{config['buildinfo'].get('version')}-{system_arch}.AppBox"
        if not built_appbox.exists():
            cleanup_cache(app_name)
            raise ManagerError(f"Failed to find the built {built_appbox} file.")

        ensure_build_marker(built_appbox)

        print_success("Installation successful!")
        print_blank()
        print_info(f"    📦 Available at: {built_appbox}", prefix="")
        print_blank()

        if index < len(to_build) - 1:
            print_info(f"▬▬▬ Building next application ({index + 2}/{len(to_build)}): {to_build[index + 1][0]} ▬▬▬", prefix="")

    print_success("All requested applications have been processed!", prefix="🎉")
    print_blank()


def remove(app_names):
    """Remove one or more installed AppBoxes."""

    if isinstance(app_names, str):
        app_names = [app_names]

    print_header(f"🗑  Removing: {', '.join(app_names)}")

    removed_apps = []
    missing_apps = []
    firejail_profiles_deleted = []
    build_markers_deleted = []

    for app_name in app_names:
        app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not app_file:
            missing_apps.append(f"    ❌ {app_name} (Not Installed)")
            continue

        try:
            filename_stem = app_file.stem

            app_file.unlink()
            removed_apps.append(f"    ✅ {app_name} (Deleted)")

            firejail_profile = Path.home() / ".local/share/nx-apphub-cli/firejail.d" / f"{app_name}-profile.profile"
            if firejail_profile.exists():
                firejail_profile.unlink()
                firejail_profiles_deleted.append(firejail_profile.name)

            build_markers_dir = repo_base_dir / ".built"
            if build_markers_dir.exists():
                for marker_file in build_markers_dir.glob(f"{app_name}-*-{system_arch}"):
                    marker_file.unlink()
                    build_markers_deleted.append(marker_file.name)

        except PermissionError:
            missing_apps.append(f"    ❌ {app_name} (Permission Denied)")
            continue

    if removed_apps:
        print_success("Uninstalled:", prefix="🟢")
        print_blank()
        for app in removed_apps:
            print_message(app)

    if firejail_profiles_deleted:
        print_blank()
        print_info(f"Firejail profile(s) deleted: {', '.join(sorted(firejail_profiles_deleted))}", prefix="🔒")

    if build_markers_deleted:
        print_blank()
        print_info(f"Build marker(s) deleted: {', '.join(sorted(build_markers_deleted))}", prefix="✓")

    if missing_apps:
        if removed_apps or firejail_profiles_deleted:
            print_blank()
        print_error("Skipped:", prefix="🔴")
        print_blank()
        for app in missing_apps:
            print_message(app)

    print_blank()
    print_success("All requested applications have been processed!", prefix="🎉")
    print_blank()


def search(app_names):
    """Search for specific applications in the local repository."""

    print_header(f"🔍 Searching for: {', '.join(app_names)}")

    ensure_repo_updated()

    found_apps = []
    missing_apps = []

    for app_name in app_names:
        search_path = repo_dir / "apps" / system_arch

        if not search_path.exists():
            missing_apps.append(f"    ❌ {app_name} (Architecture directory '{system_arch}' missing in repository)")
            continue

        matched_paths = [
            p for p in search_path.glob("*")
            if app_name in p.name
        ]

        if not matched_paths:
            missing_apps.append(f"    ❌ {app_name} (Unknown application)")
            continue

        for p in matched_paths:
            app_yaml = p / "app.yml"
            if app_yaml.exists():
                config = load_yaml_config(app_yaml)
                version = config["buildinfo"].get("version", "unknown")
                found_apps.append(f"    ✅ {p.name} - Version: {version} - Arch: {system_arch}")
            else:
                missing_apps.append(f"    ❌ {p.name} (Missing YAML)")

    if found_apps:
        print_blank()
        print_success("Found Applications:", prefix="🟢")
        print_blank()
        for app in found_apps:
            print_message(app)
        print_blank()

    if missing_apps:
        print_blank()
        print_error("Not Found:", prefix="🔴")
        print_blank()
        for app in missing_apps:
            print_message(app)
        print_blank()


def update(app_names):
    """Update one or more AppBoxes only if a newer version is available."""

    if isinstance(app_names, str):
        app_names = [app_names]

    app_names = list(dict.fromkeys(app_names))

    print_header(f"📤 Updating: {', '.join(app_names)}")

    ensure_repo_updated()

    for app_name in app_names:
        print_header(f"🔄 Checking updates for: {app_name}")

        installed_app = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not installed_app:
            print_error(f"Error: {app_name} is not installed. Cannot update.")
            print_blank()
            continue

        installed_parts = installed_app.stem.split("-")
        installed_version = "-".join(installed_parts[1:-1]) if len(installed_parts) > 2 else "unknown"

        app_yaml_path = repo_dir / "apps" / system_arch / app_name / "app.yml"

        if not app_yaml_path.exists():
            print_error(f"Error: No YAML found for: {app_name} ({system_arch}) in repository.")
            print_blank()
            continue

        config = load_yaml_config(app_yaml_path)
        latest_version = config["buildinfo"].get("version", "unknown")

        if not latest_version or latest_version == "unknown":
            print_error(f"Error: No valid version information found for: {app_name}. Aborting update.")
            print_blank()
            continue

        if installed_version == latest_version:
            print_success(f"    {app_name} is already up to date (version {installed_version}).")
            print_blank()
            continue

        print_info(f"    New version available: {latest_version} (Installed: {installed_version})", prefix="🔄")
        print_blank()

        try:
            installed_app.chmod(0o644)
        except OSError as e:
            print_warning(f"Warning: Failed to modify permissions of {installed_app}. Reason: {e}")

        backup_name = backup_dir / f"{app_name}-{installed_version}-{system_arch}.tar"
        try:
            with tarfile.open(backup_name, "w") as tar:
                tar.add(installed_app, arcname=installed_app.name)
            print_info(f"Backup created: {backup_name}", prefix="📦")
        except Exception as e:
            print_error(f"Error creating backup for: {app_name}: {e}")
            continue

        try:
            old_marker_filename = installed_app.stem

            installed_app.unlink()

            old_marker = repo_base_dir / ".built" / old_marker_filename
            if old_marker.exists():
                old_marker.unlink()
                print_blank()
                print_info(f"Removed old build marker: {old_marker_filename}", prefix="✓")
        except OSError as e:
            print_error(f"Error deleting {installed_app}: {e}")
            continue

        try:
            install([app_name])
        except NxAppHubError as e:
            print_error(f"Update failed: {e}")
            print_info("    Restoring backup...", prefix="")

            try:
                with tarfile.open(backup_name, "r") as tar:
                    tar.extractall(path=install_dir)
                restored_appbox = install_dir / f"{app_name}-{installed_version}-{system_arch}.AppBox"
                if restored_appbox.exists():
                    restored_appbox.chmod(0o755)
                    print_info(f"Restored {app_name} to version {installed_version}", prefix="♻️")
                    print_blank()
                else:
                    print_error(f"Failed to restore {app_name}.")
            except Exception as restore_err:
                print_error(f"Error: Could not restore backup for: {app_name}. Reason: {restore_err}")
            continue

        new_appbox = install_dir / f"{app_name}-{latest_version}-{system_arch}.AppBox"
        if new_appbox.exists():
            print_success(f"{app_name} successfully updated to version {latest_version}!")
            print_blank()
        else:
            print_error("Update failed: No new AppImage found. Restoring backup...")
            try:
                with tarfile.open(backup_name, "r") as tar:
                    tar.extractall(path=install_dir)
                restored_appbox = install_dir / f"{app_name}-{installed_version}-{system_arch}.AppBox"
                if restored_appbox.exists():
                    restored_appbox.chmod(0o755)
                    print_info(f"Restored {app_name} to version {installed_version}", prefix="♻️")
                    print_blank()
            except Exception as e:
                print_error(f"Error: Could not restore backup for: {app_name}. Reason: {e}")


def downgrade(app_names):
    """Restore specific backups of multiple AppBoxes."""

    if isinstance(app_names, str):
        app_names = [app_names]

    print_header(f"⏳ Downgrading: {', '.join(app_names)}")

    for app_name in app_names:
        print_info(f"Processing downgrade for: {app_name}...", prefix="🔽")
        print_blank()

        backups = sorted(backup_dir.glob(f"{app_name}-*-{system_arch}.tar"), reverse=True)

        if not backups:
            print_error(f"Error: No backups found for: {app_name}.")
            print_blank()
            continue

        print_info("Available backups:", prefix="📦")
        print_blank()
        for i, backup in enumerate(backups, 1):
            print_message(f"    {i}. {backup.name}")

        while True:
            choice = input(f"\n🔢 Enter the number of the backup to restore for {app_name} (default = latest): ").strip()
            if choice == "":
                index = 0
                break
            if choice.isdigit() and 1 <= int(choice) <= len(backups):
                index = int(choice) - 1
                break
            print_blank()
            print_error("    Invalid selection. Please enter a valid number.", prefix="⛔")

        selected_backup = backups[index]

        print_blank()
        print_info(f"Restoring backup: {selected_backup.name}...", prefix="🔄")
        print_blank()

        try:
            with tarfile.open(selected_backup, "r") as tar:
                extracted_files = tar.getnames()
                tar.extractall(path=install_dir)

            restored_appbox = None
            for file in extracted_files:
                restored_path = install_dir / file
                if restored_path.suffix == ".AppBox" and restored_path.exists():
                    restored_appbox = restored_path
                    break

            if not restored_appbox:
                print_error(f"Error: Restoration failed! No valid AppBox found in {install_dir}.")
                print_blank()
                continue

            restored_appbox.chmod(0o755)
            print_success(f"Successfully restored {app_name} to {restored_appbox.name}")
            print_blank()

            # Create marker file for the restored AppBox
            from datetime import datetime
            marker_filename = restored_appbox.stem
            marker_file = repo_base_dir / ".built" / marker_filename
            marker_file.parent.mkdir(parents=True, exist_ok=True)
            marker_content = f"""# This file is a build marker created by nx-apphub-cli
# DO NOT manually create or modify this file
# Doing so may cause integration issues and is not supported
# Built: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# AppBox: {restored_appbox.name}
# Restored from backup: {selected_backup.name}
"""
            marker_file.write_text(marker_content)
            print_info(f"Build marker created: {marker_filename}", prefix="✓")
            print_blank()

            # Remove newer versions and their markers
            for newer_version in install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"):
                if newer_version != restored_appbox:
                    try:
                        newer_version.unlink()

                        # Also remove the marker for the newer version
                        newer_marker = repo_base_dir / ".built" / newer_version.stem
                        if newer_marker.exists():
                            newer_marker.unlink()
                    except OSError as e:
                        print_warning(f"Warning: Failed to remove newer version {newer_version}. Reason: {e}")

        except (tarfile.TarError, OSError) as e:
            print_error(f"Error: Could not restore {app_name} from backup. Reason: {e}")

    print_success("All requested applications have been processed!", prefix="🎉")
    print_blank()


def format_size(size_bytes):
    """Format a size in bytes to a human-readable string."""
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PiB"


def show():
    """Show installed AppBoxes."""
    print_header("📦 Installed AppBoxes")

    installed_apps = list(install_dir.glob(f"*-{system_arch}.AppBox"))

    if not installed_apps:
        print_error("No applications installed.")
        print_blank()
        return

    installed_apps.sort(key=lambda app: app.stat().st_size, reverse=True)

    total_size = 0

    for app in installed_apps:
        size = app.stat().st_size
        total_size += size
        print_success(f"    {app.name} ({format_size(size)})")

    print_blank()
    print_info(f"Total: {len(installed_apps)} installed in {install_dir}", prefix="📁")
    print_blank()
    print_info(f"Size: {format_size(total_size)}", prefix="📦")
    print_blank()


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search", "show"]
