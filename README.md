# NX AppHub CLI | [![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<p align="center">
  <img width="128" height="128" src="https://raw.githubusercontent.com/Nitrux/luv-icon-theme/refs/heads/master/Luv/mimetypes/64/application-x-iso9660-appimage.svg">
</p>

# Introduction

NX AppHub CLI is a streamlined tool for building and managing AppImages in Nitrux from simple YAML recipes — fast, portable, and fully container-aware.

> _⚠️ Important: NX AppHub CLI primarily targets Nitrux OS, and using this utility in other distributions may or may not work. To request formal support for other distributions, open a PR regarding this use case._

### Requirements

- Nitrux 4.0.0 and newer.
    - _♦ Information: To use `nx-apphub-cli` in previous versions of Nitrux use a container._
- Python 3.10 and newer.

NX AppHub CLI requires the following utilities to function properly:

- appstream
- binutils
- file
- fuse3
- git
- libfuse2t64
- patchelf
- zstd

# Installation

To install NX AppHub CLI we recommend using pipx.

### Single-user

```
pipx install git+https://github.com/Nitrux/nx-apphub-cli.git
```


### System-wide

```
pipx install --system-site-packages git+https://github.com/Nitrux/nx-apphub-cli.git
```

# Usage

To use NX AppHub CLI check the commands below.

- `install`→ Install one or more applications.
- `remove` → Remove one or more installed applications.
- `update` → Update one or more installed applications.
- `downgrade` → Downgrade one or more installed applications.
- `search` → Search for specific applications.
- `show` → Show installed applications.
- `build` → Build an AppImage from a YAML file.
    - _♦ Information: The command "build" is exposed to allow users to test YAML files before adding them to the curated apps repository._

To create a YAML fiel for NX AppHub CLI please see the [Wiki](https://github.com/Nitrux/nx-apphub/wiki).

# Licensing

The license for this repository and its contents is **BSD-3-Clause**.

# Issues

If you find problems with the contents of this repository, please create an issue.

©2025 Nitrux Latinoamericana S.C.
