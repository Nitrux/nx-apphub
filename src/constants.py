# nx_apphub/constants.py

DESCRIPTION = """
NX Applications Hub — «Locally built AppImages for Nitrux»

NX Applications Hub is a tool developed By Nitrux Latinoamericana S.C. to facilitate the creation and management of AppImages. 
Using Distrobox containers and appimage-builder, we generate portable and self-contained applications efficiently locally without external CI configuration.

This software is under the conditions of the BSD 3-Clause license.

    ⚠️ Important: This application was designed for Nitrux OS. Using it in other distributions may cause problems or not work at all. 
                 Please don't open issues about this; they will be closed.

If you encounter problems with this software, please create an issue at https://github.com/Nitrux/nx-apphub/issues.

©2024 Nitrux Latinoamericana S.C.
"""

INSTALLATION_PACKAGES = [
    'python3-pip', 'fakeroot', 'libglib2.0-bin', 'squashfs-tools', 'zsync', 'git',
    'apt-file', 'python3-yaml', 'wget', 'adwaita-icon-theme',
    'breeze-icon-theme', 'oxygen-icon-theme', 'tango-icon-theme'
]

DEFAULT_ICON_URL = 'https://raw.githubusercontent.com/Nitrux/luv-icon-theme/refs/heads/master/Luv/mimetypes/64/application-x-iso9660-appimage.svg'

APPIMAGE_DIR = os.path.expanduser("~/Applications")
INSTALLED_FILES_PATH = os.path.expanduser("~/.local/share/nx-apphub/installed_files")
ROLLBACKS_DIR = os.path.expanduser("~/.local/share/nx-apphub/rollbacks")
