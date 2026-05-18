#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

from .builder import prepare_appimage, setup_appimage_directories
from .cli import main
from .config import load_yaml_config
from .downloader import get_latest_deb
from .extractor import extract_deb
from .manager import install, remove, update, downgrade, search
from .utils import ensure_executable, cleanup_cache

# <---
# --->
__all__ = [
    "main",
    "load_yaml_config",
    "get_latest_deb",
    "extract_deb",
    "prepare_appimage",
    "setup_appimage_directories",
    "install",
    "remove",
    "update",
    "downgrade",
    "search",
]

__version__ = "1.1.1"
