# nx_apphub/remove.py

import os
import logging
import shutil
from .constants import INSTALLED_FILES_PATH, APPIMAGE_DIR
from .utils import create_directory
import sys

def handle_remove(apps):
    apps_removed = []
    apps_not_found = []

    if not os.path.exists(INSTALLED_FILES_PATH):
        logging.error(f"Installed files list not found at '{INSTALLED_FILES_PATH}'. Nothing to remove.")
        return False

    try:
        with open(INSTALLED_FILES_PATH, 'r') as f:
            lines = f.readlines()
    except IOError as e:
        logging.error(f"Failed to read installed files list: {e}")
        return False

    if len(lines) < 2:
        logging.error("Installed files list is empty. Nothing to remove.")
        return False

    headers = [header.strip() for header in lines[0].strip().strip('|').split('|')]
    data_entries = [line.strip().strip('|').split('|') for line in lines[2:]]

    installed_apps = []
    for entry in data_entries:
        if len(entry) != len(headers):
            continue
        app_dict = {headers[i]: entry[i].strip() for i in range(len(headers))}
        installed_apps.append(app_dict)

    fixed_lengths = [0, 0, 32, 0, 128]

    for app in apps:
        matched = False
        for installed_app in installed_apps:
            if installed_app['Application'] == app:
                matched = True
                appimage_file = installed_app['AppImage File']
                appimage_path = os.path.join(APPIMAGE_DIR, appimage_file)

                if os.path.exists(appimage_path):
                    try:
                        os.remove(appimage_path)
                        logging.info(f"Deleted AppImage: {appimage_path}")
                        apps_removed.append(app)
                    except OSError as e:
                        logging.error(f"Failed to delete AppImage '{appimage_path}': {e}")
                        apps_not_found.append(app)
                else:
                    logging.warning(f"AppImage file '{appimage_path}' does not exist.")
                    apps_not_found.append(app)

                installed_apps.remove(installed_app)
                break
        if not matched:
            logging.warning(f"Application '{app}' not found in installed files list.")
            apps_not_found.append(app)

    if not installed_apps:
        logging.warning("No AppImages remain after removal.")

    max_lengths = [0] * len(headers)
    for i, col in enumerate(headers):
        if fixed_lengths[i] > 0:
            max_lengths[i] = fixed_lengths[i]
        else:
            max_length = len(col)
            for app_entry in installed_apps:
                content_length = len(app_entry[col])
                if content_length > max_length:
                    max_length = content_length
            max_lengths[i] = max_length

    try:
        with open(INSTALLED_FILES_PATH, 'w') as f:
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

    if apps_removed:
        logging.info(f"Successfully removed AppImage(s) for: {', '.join(apps_removed)}.")
    if apps_not_found:
        logging.warning(f"Could not remove AppImage(s) for: {', '.join(apps_not_found)}.")

    return len(apps_not_found) == 0
