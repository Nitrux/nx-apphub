# nx_apphub/update.py

import os
import logging
import shutil
from .constants import INSTALLED_FILES_PATH, ROLLBACKS_DIR, APPIMAGE_DIR
from .utils import create_directory, compute_sha512
from .container import run_distrobox_command, create_distrobox_container, stop_and_remove_container
from .build import handle_build, get_kernel_architecture

def handle_update():
    """Updates all existing AppImages based on the latest package information."""
    installed_files_path = INSTALLED_FILES_PATH
    rollbacks_dir = ROLLBACKS_DIR
    create_directory(rollbacks_dir)
    applications_dir = APPIMAGE_DIR
    all_success = True
    any_updates = False

    if not os.path.exists(installed_files_path):
        logging.error(f"Can't list installed applications '{installed_files_path}'.")
        return False

    try:
        with open(installed_files_path, 'r') as f:
            lines = f.readlines()
    except IOError as e:
        logging.error(f"Failed to list installed applications: {e}")
        return False

    if len(lines) < 2:
        logging.info("No AppImages to update.")
        return None

    headers = [header.strip() for header in lines[0].strip().strip('|').split('|')]
    data_entries = [line.strip().strip('|').split('|') for line in lines[2:]]

    installed_apps = []
    for entry in data_entries:
        if len(entry) != len(headers):
            continue
        app_dict = {headers[i]: entry[i].strip() for i in range(len(headers))}
        installed_apps.append(app_dict)

    if not installed_apps:
        logging.info("No AppImages to update.")
        return None

    app_names = [app['Application'] for app in installed_apps]
    container_name = create_distrobox_container("update")

    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-cache', 'show'] + app_names
        )
    except subprocess.CalledProcessError:
        logging.error("Failed to retrieve package information for update.")
        stop_and_remove_container(container_name)
        sys.exit(1)

    package_info = {}
    current_app = None
    for line in result.stdout.splitlines():
        if line.startswith("Package:"):
            current_app = line.split(":", 1)[1].strip()
            package_info[current_app] = {}
        elif line.startswith("Version:") and current_app:
            package_info[current_app]['Version'] = line.split(":", 1)[1].strip()
        elif line.startswith("MD5sum:") and current_app:
            package_info[current_app]['MD5sum'] = line.split(":", 1)[1].strip()

    for app in installed_apps:
        app_name = app['Application']
        installed_version = app['Version']
        installed_md5 = app['Package Checksum (MD5)']
        current_version = package_info.get(app_name, {}).get('Version')
        current_md5 = package_info.get(app_name, {}).get('MD5sum')

        if not current_version or not current_md5:
            logging.warning(f"Package information for '{app_name}' is incomplete. Skipping update.")
            continue

        if installed_version != current_version or installed_md5 != current_md5:
            any_updates = True 
            appimage_file = app['AppImage File']
            appimage_path = os.path.join(applications_dir, appimage_file)
            if os.path.exists(appimage_path):
                try:
                    os.chmod(appimage_path, 0o644)
                    backup_path = os.path.join(rollbacks_dir, f"{appimage_file}.bak")
                    shutil.move(appimage_path, backup_path)
                    logging.info(f"Moved existing AppImage to rollback: {backup_path}")
                except OSError as e:
                    logging.error(f"Failed to backup AppImage '{appimage_path}': {e}")
                    all_success = False
                    continue
            else:
                logging.warning(f"AppImage file '{appimage_path}' does not exist. Skipping backup.")
                all_success = False
                continue

            success = handle_build(app_name)[1]
            if success:
                kernel_architecture = get_kernel_architecture()
                appimage_file_new = f"{app_name}-{kernel_architecture}.AppImage"
                appimage_path_new = os.path.join(applications_dir, appimage_file_new)
                appimage_checksum = compute_sha512(appimage_path_new)
                app['Version'] = current_version
                app['Package Checksum (MD5)'] = current_md5
                app['AppImage Checksum (SHA512)'] = appimage_checksum
                logging.info(f"Updated AppImage for '{app_name}' successfully.")
            else:
                logging.error(f"Failed to update AppImage for '{app_name}'.")
                all_success = False

    stop_and_remove_container(container_name)

    try:
        with open(installed_files_path, 'w') as f:
            fixed_lengths = [0, 0, 32, 0, 128] 
            headers = [header.strip() for header in lines[0].strip().strip('|').split('|')]
            max_lengths = [len(col) if fixed_lengths[i] == 0 else fixed_lengths[i] for i, col in enumerate(headers)]
            for app_entry in installed_apps:
                for i, col in enumerate(headers):
                    if fixed_lengths[i] == 0:
                        max_lengths[i] = max(max_lengths[i], len(app_entry[col]))

            header = "| " + " | ".join([headers[i].ljust(max_lengths[i]) for i in range(len(headers))]) + " |\n"
            f.write(header)
            separator = "|" + "|".join(['-' * (max_lengths[i] + 2) for i in range(len(headers))]) + "|\n"
            f.write(separator)
            for app_entry in installed_apps:
                row = "| " + " | ".join([
                    app_entry[col].ljust(max_lengths[i]) if fixed_lengths[i] == 0 else app_entry[col]
                    for i, col in enumerate(headers)
                ]) + " |\n"
                f.write(row)
    except IOError as e:
        logging.error(f"Failed to write updated installed files list: {e}")
        return False

    if any_updates:
        return all_success
    else:
        return None
