# NX AppHub CLI | [![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<p align="center">
  <img width="128" height="128" src="https://raw.githubusercontent.com/Nitrux/luv-icon-theme/refs/heads/master/Luv/mimetypes/64/application-x-iso9660-appimage.svg">
</p>

# Introduction

NX AppHub CLI is a lightweight command-line tool for managing and building applications in Nitrux as AppImages.

# Overview

NX AppHub CLI simplifies application management in Nitrux using AppImages as the primary application format. Instead of relying on traditional package managers, it fetches application definitions from a Git repository and builds AppImages locally.

With built-in backup and restore functionality, NX AppHub CLI ensures that applications remain portable, self-contained, and easy to manage.

The tool follows a minimal and repository-driven approach, meaning curated applications are available, ensuring quality control and consistency.

Key Features:
- Install, Update, Remove, and Downgrade applications with ease.
- Git-based repository to fetch curated application definitions.
- Backup and restore mechanisms to maintain application integrity.

NX AppHub CLI provides a flexible, efficient, and reproducible way to manage applications, making it an essential tool for Nitrux users who prefer self-contained AppImage-based application management.

### What NX AppHub CLI is

- A lightweight application manager for Nitrux that builds, installs, updates, and removes AppImages using a Git-based system that fetches application definitions from a curated repository, ensuring consistency and quality.
- A fully automated AppImage builder that handles the entire process of fetching Debian packages from the specified repositories in the YAML definition to construct AppImages.
- A flexible tool that prioritizes simplicity, enabling users to manage applications without complex configurations. It includes a backup-aware system that maintains application integrity, allowing downgrades and safe rollbacks or building their applications, even if they are not in the official Git repository.

### What NX AppHub CLI is not

- A traditional package manager – While downloading Debian packages, it does not use APT, DNF, or Pacman for system-wide management. It strictly deals with building AppImages.
- A system manager – It does not manage system updates, dependencies, or configurations.
- A sandboxing framework—Unlike Flatpak, which provides an entire environment with runtime management and sandboxing, NX AppHub CLI is a simpler approach focusing on building AppImages and adding package management-like functionality. It does not enforce sandboxing but relies on the distribution, providing security frameworks like AppArmor or SELinux.
- A closed ecosystem – While NX AppHub CLI primarily relies on curated applications, it also allows users to build applications manually.
- A tool for multiple distributions – NX AppHub CLI is designed specifically for Nitrux and does not aim for cross-distro compatibility, even if that's the stated goal of AppImages.

### Requirements

NX AppHub CLI requires the following utilities to function properly:

- ar, tar, xz-utils, gzip, and zstd
- Git
- file
- Appstream
- FUSE 3
- libfuse2
- Python 3.10+
- Patchelf
- Any icon theme (Breeze, Adwaita, etc.)

# Installation

To install Nx AppHub CLI we recommend using pipx.

```
pipx install git+https://github.com/Nitrux/nx-apphub-cli.git
```

```
pipx install --system-site-packages git+https://github.com/Nitrux/nx-apphub-cli.git
```

# Usage

`install`→ Install one or more applications.
`remove` → Remove one or more installed applications.
`update` → Update one or more installed applications.
`downgrade` → Downgrade one or more installed applications.
`search` → Search for specific applications.
`build` → Build an AppImage from a YAML file.

# Licensing

The license for this repository and its contents is **BSD-3-Clause**.

# Issues

If you find problems with the contents of this repository, please create an issue.

©2025 Nitrux Latinoamericana S.C.
