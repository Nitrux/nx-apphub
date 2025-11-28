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

# <---
# --->
# -- Ensure directories exist.

system_arch = get_architecture()

repo_base_dir = Path.home() / ".local/share/nx-apphub-cli"
repo_dir = repo_base_dir / "apps"
backup_dir = repo_base_dir / "backups"
install_dir = Path.home() / ".local/bin/nx-apphub"

# -- Create all necessary directories.

for directory in [repo_base_dir, repo_dir, backup_dir, install_dir]:
    directory.mkdir(parents=True, exist_ok=True)


def ensure_repo_updated():
    """Ensure the application repository is cloned and up-to-date."""

    git_repo_url = "https://github.com/Nitrux/nx-apphub-apps.git"

    if repo_dir.exists() and not (repo_dir / ".git").exists():
        print(f"🚨️ Warning: {repo_dir} is not a valid Git repository. Removing...\n")
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
                print(f"🚨 Warning: Repository has untracked files: {', '.join(untracked)}")
                print(" 🔹 Changes might be overwritten or cause conflicts.\n")

            pull_result = subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False
            )
            if pull_result.returncode == 0:
                print("🔄 Applications repository updated.\n")
            else:
                print("🚨 Warning: Failed to update repository. Continuing with existing version.\n")

        except Exception as e:
            print(f"🚨 Warning: Git update check failed ({e}). Continuing...\n")

    if not (repo_dir / ".git").exists():
        print("🔄 Applications repository is missing or empty. Cloning fresh copy...\n")
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
    """Fetch YAML metadata, build AppImage, and store metadata for multiple applications."""

    if not isinstance(app_names, list):
        app_names = [app_names]

    print(f"\n[ ⚡ Installing: {', '.join(app_names)} ]\n")

    ensure_repo_updated()

    to_build = []
    printed_installed_msg = False

    for app_name in app_names:
        app_yaml_path = repo_dir / "apps" / system_arch / app_name / "app.yml"
        
        if not app_yaml_path.exists():
            print(f"    ❌ Error: No YAML found for {app_name} ({system_arch}) in repository.\n")
            continue

        config = load_yaml_config(app_yaml_path)
        app_version = config["buildinfo"].get("version", "unknown")

        if not app_version or app_version == "unknown":
            print(f"    ❌ Error: No valid version found for {app_name}. Skipping installation.\n")
            continue

        installed_appbox = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)
        if installed_appbox:
            parts = installed_appbox.stem.split("-")
            installed_version = "-".join(parts[1:-1]) if len(parts) > 2 else "unknown"

            print(f"    ℹ️  {app_name} is already installed (version {installed_version}). Skipping installation.")
            printed_installed_msg = True
            continue

        to_build.append((app_name, config))

    if printed_installed_msg:
        print()

    for index, (app_name, config) in enumerate(to_build):
        repos_config = config["buildinfo"].get("distrorepo", {})
        if not repos_config:
            print(f"    ❌ Error: No 'distrorepo' specified for {app_name}. Skipping installation.\n")
            continue

        base_repos = repos_config if isinstance(repos_config, list) else repos_config.get("base", [])
        ppa_repos = {} if isinstance(repos_config, list) else {
            ppa["id"]: ppa for ppa in repos_config.get("ppas", [])
        }

        dependencies = config["buildinfo"].get("deps", [])

        concurrent_downloads(dependencies, base_repos, ppa_repos, app_name)

        print("\n🛠  Building AppBox...\n")
        prepare_appimage(config, install_mode=True)

        built_appbox = install_dir / f"{app_name}-{config['buildinfo'].get('version')}-{system_arch}.AppBox"
        if not built_appbox.exists():
            cleanup_cache(app_name)
            raise ManagerError(f"Failed to find the built {built_appbox} file.")

        print(f"✅ Installation successful!\n\n    📦 Available at: {built_appbox}")
        print()

        if index < len(to_build) - 1:
            print()

    print("🎉 All requested applications have been processed!\n")


def remove(app_names):
    """Remove one or more installed AppBoxes."""

    if isinstance(app_names, str):
        app_names = [app_names]

    print(f"\n[ 🗑  Removing: {', '.join(app_names)} ]\n")

    removed_apps = []
    missing_apps = []
    firejail_profiles_deleted = []

    for app_name in app_names:
        app_file = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not app_file:
            missing_apps.append(f"    ❌ {app_name} (Not Installed)")
            continue

        try:
            app_file.unlink()
            removed_apps.append(f"    ✅ {app_name} (Deleted)")

            firejail_profile = Path.home() / ".local/share/nx-apphub-cli/firejail.d" / f"{app_name}-profile.profile"
            if firejail_profile.exists():
                firejail_profile.unlink()
                firejail_profiles_deleted.append(firejail_profile.name)

        except PermissionError:
            missing_apps.append(f"    ❌ {app_name} (Permission Denied)")
            continue

    if removed_apps:
        print("🟢 Uninstalled:\n\n" + "\n".join(removed_apps))

    if firejail_profiles_deleted:
        print(f"\n🔒 Firejail profile(s) deleted: {', '.join(sorted(firejail_profiles_deleted))}")

    if missing_apps:
        if removed_apps or firejail_profiles_deleted:
            print()
        print("🔴 Skipped:\n\n" + "\n".join(missing_apps))

    print()
    print("🎉 All requested applications have been processed!\n")


def search(app_names):
    """Search for specific applications in the local repository."""

    print(f"\n[ 🔍 Searching for: {', '.join(app_names)} ]\n")

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
        print("\n🟢 Found Applications:\n")
        print("\n".join(found_apps), "\n")

    if missing_apps:
        print("\n🔴 Not Found:\n")
        print("\n".join(missing_apps), "\n")


def update(app_names):
    """Update one or more AppBoxes only if a newer version is available."""

    if isinstance(app_names, str):
        app_names = [app_names]

    app_names = list(dict.fromkeys(app_names))

    print(f"\n[ 📤 Updating: {', '.join(app_names)} ]\n")

    ensure_repo_updated()

    for app_name in app_names:
        print(f"\n[ 🔄 Checking updates for: {app_name} ]\n")

        installed_app = next(install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"), None)

        if not installed_app:
            print(f"    ❌ Error: {app_name} is not installed. Cannot update.\n")
            continue

        installed_parts = installed_app.stem.split("-")
        installed_version = "-".join(installed_parts[1:-1]) if len(installed_parts) > 2 else "unknown"

        app_yaml_path = repo_dir / "apps" / system_arch / app_name / "app.yml"
        
        if not app_yaml_path.exists():
            print(f"    ❌ Error: No YAML found for {app_name} ({system_arch}) in repository.\n")
            print()
            continue

        config = load_yaml_config(app_yaml_path)
        latest_version = config["buildinfo"].get("version", "unknown")

        if not latest_version or latest_version == "unknown":
            print(f"    ❌ Error: No valid version information found for {app_name}. Aborting update.\n")
            continue

        if installed_version == latest_version:
            print(f"    ✅ {app_name} is already up to date (version {installed_version}).\n")
            continue

        print(f"    🔄 New version available: {latest_version} (Installed: {installed_version})\n")

        try:
            installed_app.chmod(0o644)
        except OSError as e:
            print(f"🚨️ Warning: Failed to modify permissions of {installed_app}. Reason: {e}")

        backup_name = backup_dir / f"{app_name}-{installed_version}-{system_arch}.tar"
        try:
            with tarfile.open(backup_name, "w") as tar:
                tar.add(installed_app, arcname=installed_app.name)
            print(f"📦 Backup created: {backup_name}")
        except Exception as e:
            print(f"❌ Error creating backup for {app_name}: {e}")
            continue

        try:
            installed_app.unlink()
        except OSError as e:
            print(f"❌ Error deleting {installed_app}: {e}")
            continue

        try:
            install([app_name])
        except NxAppHubError as e:
            print(f"❌ Update failed: {e}")
            print("    Restoring backup...")

            try:
                with tarfile.open(backup_name, "r") as tar:
                    tar.extractall(path=install_dir)
                restored_appbox = install_dir / f"{app_name}-{installed_version}-{system_arch}.AppBox"
                if restored_appbox.exists():
                    restored_appbox.chmod(0o755)
                    print(f"♻️ Restored {app_name} to version {installed_version}\n")
                else:
                    print(f"❌ Failed to restore {app_name}.")
            except Exception as restore_err:
                print(f"❌ Critical error: Could not restore backup for {app_name}. Reason: {restore_err}")
            continue

        new_appbox = install_dir / f"{app_name}-{latest_version}-{system_arch}.AppBox"
        if new_appbox.exists():
            print(f"✅ {app_name} successfully updated to version {latest_version}!\n")
        else:
            print(f"❌ Update failed: No new AppImage found. Restoring backup...")
            try:
                with tarfile.open(backup_name, "r") as tar:
                    tar.extractall(path=install_dir)
                restored_appbox = install_dir / f"{app_name}-{installed_version}-{system_arch}.AppBox"
                if restored_appbox.exists():
                    restored_appbox.chmod(0o755)
                    print(f"♻️ Restored {app_name} to version {installed_version}\n")
            except Exception as e:
                print(f"❌ Critical error: Could not restore backup for {app_name}. Reason: {e}")


def downgrade(app_names):
    """Restore specific backups of multiple AppBoxes."""

    if isinstance(app_names, str):
        app_names = [app_names]

    print(f"\n[ ⏳ Downgrading: {', '.join(app_names)} ]\n")

    for app_name in app_names:
        print(f"\n🔽 Processing downgrade for: {app_name}...\n")

        backups = sorted(backup_dir.glob(f"{app_name}-*-{system_arch}.tar"), reverse=True)

        if not backups:
            print(f"    ❌ No backups found for {app_name}.\n")
            continue

        print("📦 Available backups:\n")
        for i, backup in enumerate(backups, 1):
            print(f"    {i}. {backup.name}")

        while True:
            choice = input(f"\n🔢 Enter the number of the backup to restore for {app_name} (default = latest): ").strip()
            if choice == "":
                index = 0
                break
            if choice.isdigit() and 1 <= int(choice) <= len(backups):
                index = int(choice) - 1
                break
            print("\n    ⛔ Invalid selection. Please enter a valid number.")

        selected_backup = backups[index]

        print(f"\n🔄 Restoring backup: {selected_backup.name}...\n")

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
                print(f"❌ Error: Restoration failed! No valid AppBox found in {install_dir}.\n")
                continue

            restored_appbox.chmod(0o755)
            print(f"✅ Successfully restored {app_name} to {restored_appbox.name}\n")

            for newer_version in install_dir.glob(f"{app_name}-*-{system_arch}.AppBox"):
                if newer_version != restored_appbox:
                    try:
                        newer_version.unlink()
                    except OSError as e:
                        print(f"🚨️ Warning: Failed to remove newer version {newer_version}. Reason: {e}")

        except (tarfile.TarError, OSError) as e:
            print(f"❌ Error: Could not restore {app_name} from backup. Reason: {e}")

    print("🎉 All requested applications have been processed!\n")


def format_size(size_bytes):
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PiB"


def show():
    """Show installed AppBoxes."""
    print("\n[ 📦 Installed AppBoxes ]\n")

    installed_apps = list(install_dir.glob(f"*-{system_arch}.AppBox"))

    if not installed_apps:
        print("❌ No applications installed.\n")
        return

    installed_apps.sort(key=lambda app: app.stat().st_size, reverse=True)

    total_size = 0

    for app in installed_apps:
        size = app.stat().st_size
        total_size += size
        print(f"    ✅ {app.name} ({format_size(size)})")

    print(f"\n📁 Total: {len(installed_apps)} installed in {install_dir}\n")
    print(f"📦 Size: {format_size(total_size)}\n")


# -- Export functions.

__all__ = ["install", "remove", "update", "downgrade", "search", "show"]
