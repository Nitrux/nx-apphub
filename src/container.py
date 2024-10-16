# nx_apphub/container.py

import subprocess
import logging
import sys
from .utils import generate_random_id, create_directory, remove_directory
from .constants import INSTALLATION_PACKAGES

def check_distrobox_installed():
    try:
        run_distrobox_command(['distrobox', '--version'])
        logging.debug("Distrobox is installed.")
    except subprocess.CalledProcessError:
        logging.error("Error: 'distrobox' is not installed or not found in the host's $PATH.")
        sys.exit(1)

def run_distrobox_command(cmd):
    """
    Executes a command using subprocess.run and handles logging based on the log level.
    """
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            if result.stdout:
                logging.debug(f"Standard Output: {result.stdout}")
            if result.stderr:
                logging.debug(f"Standard Error: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            if e.stdout:
                logging.debug(f"Standard Output: {e.stdout}")
            if e.stderr:
                logging.debug(f"Standard Error: {e.stderr}")
        logging.error(f"Command '{' '.join(cmd)}' failed with return code {e.returncode}")
        raise e

def create_distrobox_container(app_name):
    from .constants import INSTALLATION_PACKAGES
    random_id = generate_random_id()
    container_name = f"{app_name}-{random_id}"
    logging.info(f"Creating Distrobox container: {container_name}...")
    try:
        run_distrobox_command([
            'distrobox', 'create', '-n', container_name, '-i', 'debian:stable',
            '--additional-packages', ' '.join(INSTALLATION_PACKAGES)
        ])
        logging.info(f"Container '{container_name}' created and packages installed.")

        run_distrobox_command([
            'distrobox', 'enter', '-n', container_name, '--', 'sudo', 'apt-file', 'update'
        ])

    except subprocess.CalledProcessError:
        logging.error(f"Error creating Distrobox container '{container_name}'.")
        stop_and_remove_container(container_name)
        sys.exit(1)
    return container_name

def stop_and_remove_container(container_name, staging_dir=None):
    logging.info(f"Cleaning up container: {container_name}...")
    try:
        result = run_distrobox_command(['distrobox', 'list'])
        lines = result.stdout.splitlines()

        for line in lines:
            if container_name in line:
                container_id = line.split()[0]
                run_distrobox_command(['podman', 'container', 'kill', container_id])
                run_distrobox_command(['podman', 'container', 'rm', '-f', container_id])
                logging.info(f"Container '{container_name}' stopped and removed.")
                break
        else:
            logging.warning(f"Container '{container_name}' not found.")

        desktop_launcher = os.path.expanduser(f"~/.local/share/applications/{container_name}.desktop")
        if os.path.exists(desktop_launcher):
            try:
                os.remove(desktop_launcher)
                logging.info(f"Cleanup leftover launcher '{desktop_launcher}' deleted.")
            except OSError as e:
                logging.error(f"Failed to delete leftover launcher '{desktop_launcher}': {e}")
        else:
            logging.warning(f"Desktop launcher '{desktop_launcher}' not found.")

        if staging_dir and os.path.exists(staging_dir):
            try:
                remove_directory(staging_dir)
                logging.info(f"Staging area '{staging_dir}' deleted.")
            except Exception:
                pass  # Error already logged in utils.py

    except subprocess.CalledProcessError:
        logging.error(f"Error stopping and removing the container '{container_name}'.")
        desktop_launcher = os.path.expanduser(f"~/.local/share/applications/{container_name}.desktop")
        if os.path.exists(desktop_launcher):
            try:
                os.remove(desktop_launcher)
                logging.info(f"Cleanup leftover launcher '{desktop_launcher}' deleted.")
            except OSError as e:
                logging.error(f"Failed to delete leftover launcher '{desktop_launcher}': {e}")
        else:
            logging.warning(f"Desktop launcher '{desktop_launcher}' not found.")

        if staging_dir and os.path.exists(staging_dir):
            try:
                remove_directory(staging_dir)
                logging.info(f"Staging area '{staging_dir}' deleted.")
            except Exception:
                pass  # Error already logged in utils.py
        sys.exit(1)
