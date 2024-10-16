# nx_apphub/utils.py

import random
import string
import hashlib
import os
import shutil
import logging

def generate_random_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def compute_sha512(file_path):
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
    try:
        os.makedirs(path, exist_ok=True)
        logging.debug(f"Directory created at: '{path}'")
    except OSError as e:
        logging.error(f"Failed to create directory '{path}': {e}")
        raise

def remove_directory(path):
    try:
        shutil.rmtree(path)
        logging.debug(f"Directory '{path}' deleted.")
    except Exception as e:
        logging.critical(f"Error deleting directory '{path}': {e}")
        raise
