# nx_apphub/build.py

import subprocess
import logging
import sys
import os
import shutil
import difflib
import yaml

from .container import (
    run_distrobox_command,
    stop_and_remove_container,
    create_distrobox_container
)
from .utils import (
    compute_sha512,
    create_directory,
    remove_directory,
    get_kernel_architecture
)
from .constants import (
    DEFAULT_ICON_URL,
    APPIMAGE_DIR,
    INSTALLED_FILES_PATH
)

##########################
# YAML Representers       #
##########################

class QuotedStr(str):
    """String subclass to enforce single-quoted YAML strings."""
    pass

def quoted_str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")

yaml.SafeDumper.add_representer(QuotedStr, quoted_str_representer)

class LiteralStr(str):
    """String subclass to enforce literal block style YAML strings."""
    pass

def literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

yaml.SafeDumper.add_representer(LiteralStr, literal_representer)

##########################
# Build Process Functions#
##########################

def install_appimage_builder_in_container(container_name):
    """Installs appimage-builder inside the specified container."""
    logging.info(f"Installing appimage-builder in container: '{container_name}'...")
    try:
        run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'sudo', 'pip3', 'install', '--break-system-packages',
            'git+https://github.com/AppImageCrafters/appimage-builder.git'
        ])
        logging.info("appimage-builder installed successfully.")
    except subprocess.CalledProcessError:
        logging.error(f"Error installing appimage-builder in container '{container_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def get_app_section(container_name, app_name):
    """Retrieves the section of the application using apt-cache show."""
    logging.debug(f"Fetching section for '{app_name}' from container: {container_name}...")
    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-cache', 'show', app_name
        ])
        for line in result.stdout.splitlines():
            if line.startswith("Section:"):
                section = line.split(":", 1)[1].strip()
                logging.debug(f"Detected section for '{app_name}': {section}")
                return section
        logging.error("Section not found.")
        stop_and_remove_container(container_name)
        sys.exit(1)
    except subprocess.CalledProcessError:
        logging.error(f"Error retrieving section for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def get_app_architecture(container_name, app_name):
    """Retrieves the architecture of the application using apt-cache show."""
    logging.debug(f"Fetching architecture for '{app_name}' from container: {container_name}'...")
    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-cache', 'show', app_name
        ])
        for line in result.stdout.splitlines():
            if line.startswith("Architecture:"):
                architecture = line.split(":", 1)[1].strip()
                logging.info(f"Detected package architecture for '{app_name}': {architecture}")
                return architecture
        logging.error("Architecture not found.")
        stop_and_remove_container(container_name)
        sys.exit(1)
    except subprocess.CalledProcessError:
        logging.error(f"Error retrieving architecture for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def get_app_version(container_name, app_name):
    """Retrieves the version of the application using apt-cache show."""
    logging.debug(f"Fetching version for '{app_name}' from container: {container_name}...")
    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-cache', 'show', app_name
        ])
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
                logging.info(f"Detected version for '{app_name}': {version}")
                return version
        logging.error("Version not found.")
        stop_and_remove_container(container_name)
        sys.exit(1)
    except subprocess.CalledProcessError:
        logging.error(f"Error retrieving version for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def get_app_checksum(container_name, app_name):
    """Retrieves the MD5 checksum of the application using apt-cache show."""
    logging.debug(f"Fetching MD5 checksum for '{app_name}' from container: {container_name}...")
    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-cache', 'show', app_name
        ])
        for line in result.stdout.splitlines():
            if line.startswith("MD5sum:"):
                checksum = line.split(":", 1)[1].strip()
                logging.info(f"Detected MD5 checksum for '{app_name}': {checksum}")
                return checksum
        logging.error("MD5sum not found.")
        stop_and_remove_container(container_name)
        sys.exit(1)
    except subprocess.CalledProcessError:
        logging.error(f"Error retrieving MD5 checksum for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def get_executable_path(container_name, app_name):
    """Determines the primary executable path of the application."""
    logging.debug(f"Fetching executable path for '{app_name}' from container: {container_name}...")
    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-file', 'list', app_name
        ])

        exec_paths = []
        for line in result.stdout.splitlines():
            if ':' in line:
                _, file_path = line.split(':', 1)
                file_path = file_path.strip()
                if (file_path.startswith('/usr/bin/') or
                    file_path.startswith('/bin/') or
                    file_path.startswith('/usr/games/')):
                    exec_paths.append(file_path.lstrip('/'))

        if not exec_paths:
            fallback_exec_path = f"usr/bin/{app_name}"
            logging.warning(f"No executables found under '/usr/bin/', '/bin/', or '/usr/games/' for '{app_name}'. Falling back to '{fallback_exec_path}'.")
            return fallback_exec_path
        else:
            executable_names = [os.path.basename(path) for path in exec_paths]
            similarity_scores = [(name, difflib.SequenceMatcher(None, app_name, name).ratio()) for name in executable_names]
            similarity_scores.sort(key=lambda x: x[1], reverse=True)
            best_match_name, best_score = similarity_scores[0]
            logging.debug(f"Best match for '{app_name}' is '{best_match_name}' with similarity score {best_score:.2f}")
            for path in exec_paths:
                if os.path.basename(path) == best_match_name:
                    selected_path = path
                    logging.debug(f"Selected executable path: {selected_path}")
                    return selected_path
            logging.error(f"Executable '{best_match_name}' not found in paths.")
            stop_and_remove_container(container_name)
            sys.exit(1)
    except subprocess.CalledProcessError:
        logging.error(f"Error retrieving executable path for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

def process_icons_and_desktop_files(container_name, app_name, staging_dir, exec_path):
    """Ensures that the AppImage has the necessary icon and desktop launcher."""
    logging.debug(f"Processing icons and desktop files for '{app_name}'...")

    includes_icon = False
    includes_desktop = False
    icon_name = None

    try:
        result = run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--',
            'apt-file', 'list', app_name
        ])

        for line in result.stdout.splitlines():
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            file_path = parts[1].strip()
            if not includes_icon:
                icon_extensions = ['.svg', '.png', '.xpm']
                if any('/icons/' in file_path and file_path.lower().endswith(ext) for ext in icon_extensions):
                    includes_icon = True
                    icon_file_name = os.path.basename(file_path)
                    icon_name, _ = os.path.splitext(icon_file_name)
                    logging.debug(f"Found icon file: {file_path}, icon_name: {icon_name}")
            if not includes_desktop:
                if file_path.startswith('/usr/share/applications/') and file_path.endswith('.desktop'):
                    includes_desktop = True
                    logging.debug(f"Found desktop launcher file: {file_path}")
            if includes_icon and includes_desktop:
                break

        logging.debug(f"Package '{app_name}' includes icon: {includes_icon}, includes desktop launcher: {includes_desktop}")

    except subprocess.CalledProcessError:
        logging.error(f"Error checking package files for '{app_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)

    if not includes_icon:
        logging.debug(f"No icon found for '{app_name}'. Downloading default icon...")
        icon_dest_dir = os.path.join(staging_dir, 'AppDir', 'usr', 'share', 'icons', 'hicolor', 'scalable', 'apps')
        try:
            create_directory(icon_dest_dir)
        except Exception:
            stop_and_remove_container(container_name, staging_dir)
            sys.exit(1)

        icon_name = app_name
        icon_dest_path = os.path.join(icon_dest_dir, f'{icon_name}.svg')
        default_icon_url = DEFAULT_ICON_URL
        try:
            run_distrobox_command([
                'distrobox', 'enter', '-n', container_name, '--',
                'wget', '-O', icon_dest_path, default_icon_url
            ])
            logging.debug(f"Default icon downloaded to {icon_dest_path}")
        except subprocess.CalledProcessError:
            logging.error(f"Failed to download default icon for '{app_name}'")
            stop_and_remove_container(container_name, staging_dir)
            sys.exit(1)

    if not includes_desktop:
        logging.debug(f"No desktop launcher found for '{app_name}'. Generating generic desktop launcher...")
        desktop_dir = os.path.join(staging_dir, 'AppDir', 'usr', 'share', 'applications')
        try:
            create_directory(desktop_dir)
        except Exception:
            stop_and_remove_container(container_name, staging_dir)
            sys.exit(1)
        desktop_file_path = os.path.join(desktop_dir, f'{app_name}.desktop')

        desktop_entry = f"""[Desktop Entry]
Name={app_name}
Exec={exec_path}
Icon={icon_name}
Type=Application
Terminal=true
Categories=Utility;
"""
        try:
            with open(desktop_file_path, 'w') as desktop_file:
                desktop_file.write(desktop_entry)
            logging.debug(f"Generic desktop launcher created at '{desktop_file_path}'")
        except (OSError, IOError) as e:
            logging.error(f"Failed to create desktop launcher at '{desktop_file_path}': {e}")

    return icon_name

def create_staging_area(app_name, container_name):
    """Creates a staging directory for building the AppImage."""
    staging_dir = f"/tmp/{container_name}"
    try:
        create_directory(staging_dir)
        logging.debug(f"Staging area created at: '{staging_dir}'")
    except Exception:
        sys.exit(1)
    return staging_dir

def create_yaml_recipe(app_name, app_version, exec_path, container_name, staging_dir, app_architecture, kernel_architecture, icon_name):
    """Generates a YAML recipe for appimage-builder."""
    default_dependencies = ['bash', 'dash', app_name]

    appimage_builder_dir = os.path.join(staging_dir, f"{app_name}-appimage")
    try:
        create_directory(appimage_builder_dir)
        logging.debug(f"AppImage builder directory created at: {appimage_builder_dir}")
    except Exception:
        stop_and_remove_container(container_name, staging_dir)
        sys.exit(1)

    recipe_path = os.path.join(appimage_builder_dir, f"{app_name}-appimage.yaml")

    repo_codename = 'stable'

    recipe = {
        'version': 1,
        'AppDir': {
            'path': './AppDir',
            'app_info': {
                'id': app_name,
                'name': app_name,
                'icon': icon_name,
                'version': app_version,
                'exec': exec_path,
                'exec_args': '$@'
            },
            'runtime': {
                'env': {
                    'PATH': QuotedStr(f"${{APPDIR}}/usr/bin:${{APPDIR}}/bin:${{APPDIR}}/usr/lib/{kernel_architecture}-linux-gnu/libexec/kf5:$PATH")
                }
            },
            'after_bundle': [
                "cd ./AppDir/usr/bin && ln -sf bash sh && cd -"
            ],
            'apt': {
                'arch': [app_architecture],
                'allow_unauthenticated': True,
                'sources': [
                    {
                        'sourceline': LiteralStr(f"deb [arch={app_architecture}] http://deb.debian.org/debian {repo_codename} main contrib non-free non-free-firmware"),
                        'key_url': 'https://ftp-master.debian.org/keys/archive-key-12.asc'
                    }
                ],
                'include': default_dependencies,
                'exclude': ['systemd']
            },
            'files': {
                'include': ['/usr/bin/which'],
                'exclude': [
                    'usr/include', 'usr/share/man', 'usr/share/doc', 'usr/share/doc/*/README.*',
                    'usr/share/doc/*/changelog.*', 'usr/share/doc/*/NEWS.*', 'usr/share/doc/*/TODO.*',
                    'lib/systemd', 'etc/systemd', 'usr/lib/systemd', 'usr/bin/systemd*',
                    'usr/bin/dpkg*', 'usr/bin/*-linux-gnu-*', 'usr/lib/*-linux-gnu/systemd',
                    'usr/bin/systemd-*', 'usr/share/locale'
                ]
            }
        },
        'AppImage': {
            'arch': kernel_architecture,
            'comp': 'xz',
            'file_name': f"{app_name}-{kernel_architecture}.AppImage",
            'update-information': f"gh-releases-zsync|Nitrux|{app_name}|{app_version}|*{kernel_architecture}.AppImage.zsync"
        }
    }

    try:
        with open(recipe_path, 'w') as yaml_file:
            yaml.dump(
                recipe,
                yaml_file,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
                width=4096,
                allow_unicode=True,
                Dumper=yaml.SafeDumper
            )
        logging.debug(f"YAML recipe saved at: {recipe_path}")
    except (OSError, IOError) as e:
        logging.error(f"Failed to write YAML recipe to '{recipe_path}': {e}")
        stop_and_remove_container(container_name, staging_dir)
        sys.exit(1)

    return recipe_path

def build_appimage_in_container(container_name, app_name, recipe_path, staging_dir, exec_path, kernel_architecture):
    """Builds the AppImage inside the container and moves it to the Applications directory."""
    try:
        logging.info(f"Building AppImage for '{app_name}' using recipe at '{recipe_path}'...")

        run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--', 'bash', '-c',
            f'cd {staging_dir} && appimage-builder --recipe {recipe_path} --skip-tests'
        ])

        appimage_dir = APPIMAGE_DIR
        try:
            create_directory(appimage_dir)
        except Exception:
            remove_directory(staging_dir)
            return False

        built_appimage = os.path.join(staging_dir, f"{app_name}-{kernel_architecture}.AppImage")

        if os.path.exists(built_appimage):
            destination_path = os.path.join(appimage_dir, f"{app_name}-{kernel_architecture}.AppImage")
            try:
                shutil.move(built_appimage, destination_path)
                logging.debug(f"AppImage moved to: {destination_path}")
                return True
            except (OSError, shutil.Error) as e:
                logging.error(f"Failed to move AppImage to '{destination_path}': {e}")
                return False
        else:
            logging.error(f"AppImage not found at {built_appimage}. Checking for subdirectories...")

            for root, dirs, files in os.walk(staging_dir):
                for file in files:
                    if file.endswith(f"{app_name}-{kernel_architecture}.AppImage"):
                        built_appimage = os.path.join(root, file)
                        destination_path = os.path.join(appimage_dir, file)
                        try:
                            shutil.move(built_appimage, destination_path)
                            logging.debug(f"AppImage found and moved to: {destination_path}")
                            return True
                        except (OSError, shutil.Error) as e:
                            logging.error(f"Failed to move AppImage to '{destination_path}': {e}")
                            return False

            logging.error("Error: AppImage not found after checking subdirectories.")
            return False

    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.strip()
        if "RuntimeError: Main executable is not an elf executable" in stderr_output:
            logging.error(f"Build failed for '{app_name}': Main executable is not an ELF executable.")
        elif f"No such file or directory: '{exec_path}'" in stderr_output:
            logging.error(f"Build failed for '{app_name}': Executable '{exec_path}' not found.")
        else:
            logging.error(f"Error building AppImage for '{app_name}': {stderr_output}")

        remove_directory(staging_dir)
        return False

def create_installed_files_record(app_name, app_version, package_checksum, appimage_file, appimage_checksum):
    """Updates the installed files record with the new AppImage."""
    logging.debug("Updating installed files record...")
    columns = ["Application", "Version", "Package Checksum (MD5)", "AppImage File", "AppImage Checksum (SHA512)"]
    new_entry = [app_name, app_version, package_checksum, appimage_file, appimage_checksum]
    fixed_lengths = [0, 0, 32, 0, 128]

    # Check if the installed_files_path exists
    if not os.path.exists(INSTALLED_FILES_PATH) or os.path.getsize(INSTALLED_FILES_PATH) == 0:
        with open(INSTALLED_FILES_PATH, 'w') as f:
            f.write("| " + " | ".join(columns) + " |\n")
            f.write("|" + "|".join(['-' * (len(col)+2) for col in columns]) + "|\n")

    # Read existing entries
    with open(INSTALLED_FILES_PATH, 'r') as f:
        lines = f.readlines()

    if len(lines) < 2:
        # If file is somehow corrupted, reinitialize
        with open(INSTALLED_FILES_PATH, 'w') as f:
            f.write("| " + " | ".join(columns) + " |\n")
            f.write("|" + "|".join(['-' * (len(col)+2) for col in columns]) + "|\n")
        current_columns = columns
        max_lengths = [len(col) for col in columns]
    else:
        current_columns = [header.strip() for header in lines[0].strip().strip('|').split('|')]
        data_lines = [line.strip().strip('|').split('|') for line in lines[2:]]
        max_lengths = [len(col) if fixed_lengths[i] != 0 else len(col.strip()) for i, col in enumerate(current_columns)]

        for line in data_lines:
            parts = line.strip().split('|')[1:-1]
            for i, part in enumerate(parts):
                part = part.strip()
                if fixed_lengths[i] == 0:
                    max_lengths[i] = max(max_lengths[i], len(part))

        for i, item in enumerate(new_entry):
            if fixed_lengths[i] == 0:
                max_lengths[i] = max(max_lengths[i], len(item))

    # Write updated table
    header = "| " + " | ".join([columns[i].ljust(max_lengths[i]) for i in range(len(columns))]) + " |\n"
    separator = "|" + "|".join(['-' * (max_lengths[i]+2) for i in range(len(columns))]) + "|\n"

    with open(INSTALLED_FILES_PATH, 'w') as f:
        f.write(header)
        f.write(separator)
        for line in lines[2:]:
            parts = line.strip().split('|')[1:-1]
            formatted_line = "| " + " | ".join([
                parts[i].strip().ljust(max_lengths[i]) if fixed_lengths[i] == 0 else parts[i].strip()
                for i in range(len(parts))
            ]) + " |\n"
            f.write(formatted_line)
        formatted_new_line = "| " + " | ".join([
            new_entry[i].ljust(max_lengths[i]) if fixed_lengths[i] == 0 else new_entry[i]
            for i in range(len(new_entry))
        ]) + " |\n"
        f.write(formatted_new_line)
    logging.debug("Installed files record updated.")
