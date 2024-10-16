# nx_apphub/__init__.py

"""
NX Applications Hub Package
===========================

NX Applications Hub is a command-line tool developed by Nitrux Latinoamericana S.C. to facilitate
the creation, management, and updating of AppImages for Nitrux OS. Leveraging Distrobox containers
and appimage-builder, it ensures that AppImages are built in isolated environments, maintaining system integrity.

Modules:
    - main: Entry point for the CLI tool.
    - args: Argument parsing.
    - logging_setup: Logging configuration.
    - container: Distrobox container management.
    - build: AppImage building process.
    - remove: Removal of AppImages.
    - update: Updating existing AppImages.
    - utils: Utility functions.
    - constants: Constant values used across the application.

Usage:
    The primary interface is through the `nx-apphub-cli` command after installation.
    Refer to the README.md for detailed usage instructions.

License:
    BSD-3-Clause License
"""

__version__ = "1.0.0"

from .main import main
