# nx_apphub/utils.py

import random
import string
import hashlib
import os
import shutil
import logging
import subprocess
import sys

def generate_random_id(length=6):
    """Generates a random alphanumeric string of specified length."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def compute_sha512(file_path):
    """Computes the SHA512 checksum of the given file."""
    logging.info(f"Computing SHA512 checksum for '{file_path}'...")
    sha512 = hashlib.sha512()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha512.update(chunk)
        checksum = sha512.hexdigest()
        logging.info(f"SHA512 checksum for '{file_path}': {checksum}")
        return checksum
    except IOError as e:
        logging.error(f"Failed to compute SHA512 checksum for '{file_path}': {e}")
        return "N/A"

def create_directory(path):
    """Creates a directory if it does not exist."""
    try:
        os.makedirs(path, exist_ok=True)
        logging.debug(f"Directory created at: '{path}'")
    except OSError as e:
        logging.error(f"Failed to create directory '{path}': {e}")
        raise

def remove_directory(path):
    """Removes a directory and its contents."""
    try:
        shutil.rmtree(path)
        logging.debug(f"Directory '{path}' deleted.")
    except Exception as e:
        logging.critical(f"Error deleting directory '{path}': {e}")
        raise

def get_kernel_architecture():
    """Retrieves the system's CPU architecture."""
    logging.debug("Fetching kernel CPU architecture...")
    try:
        result = subprocess.run(['uname', '-m'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)
        arch = result.stdout.strip()
        logging.info(f"Building for CPU architecture: {arch}")
        return arch
    except subprocess.CalledProcessError:
        logging.error("Error retrieving CPU architecture.")
        sys.exit(1)
