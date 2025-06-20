# NX AppHub CLI | [![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<p align="center">
  <img width="128" height="128" src="https://raw.githubusercontent.com/Nitrux/luv-icon-theme/refs/heads/master/Luv/mimetypes/64/application-x-iso9660-appimage.svg">
</p>

# Introduction

NX AppHub CLI is a lightweight command-line tool for managing and building applications in Nitrux.

> _⚠️ Important: NX AppHub CLI primarily targets Nitrux OS, and using this utility in other distributions may or may not work. Compatibility with other distributions is incidental, not intentional._

For more in-depth information about NX AppHub CLI, please see the [Wiki](https://github.com/Nitrux/nx-apphub/wiki).

## Requirements

- Nitrux 4.0.0 and newer.
    - _♦ Information: To use `nx-apphub-cli` in previous versions of Nitrux use a container; see our tutorial on [how to use Distrobox](https://nxos.org/tutorial/how-to-use-distrobox-in-nitrux/)._
- Python 3.10 and newer.

### Runtime Requirements

```
appstream
binutils
bubblewrap
file
firejail
fuse3
git
libfuse2t64
patchelf
zstd
```

# Installation

To install NX AppHub CLI we recommend using `pipx`.

## Single-user

```
pipx install git+https://github.com/Nitrux/nx-apphub.git
```

> _⚠️ Important: pipx will install `nx-apphub-cli` to `$HOME/.local/bin`, add this directory to `$PATH`._

## System-wide

```
pipx install --system-site-packages git+https://github.com/Nitrux/nx-apphub.git
```

# Uninstallation

To uninstall NX AppHub CLI, do the following.

```
pipx uninstall nx-apphub-cli
```

# Usage

To use NX AppHub CLI check the commands below.

- `install`→ Install one or more applications.
- `remove` → Remove one or more installed applications.
- `update` → Update one or more installed applications.
- `downgrade` → Downgrade one or more installed applications.
- `search` → Search for specific applications.
- `show` → Show installed applications.
- `build` → Build an AppImage from a local YAML file.
  - `--appdir-lint` → Optionally debug missing shared libraries in an AppImage.
- `generate` → Generate YAML template from package metadata.
  - `--package` → Specify package name.
  - `--distro` → Choose the distribution from which to get metadata.
  - `--release` → The release of the selected distribution.
  - `--arch` → Specify the target architecture.
  - `--output` → The file name of the generated YAML file.
  - `--description-output` → The file name of the generated metadata file.


## Examples

```
nx-apphub-cli install inkscape

nx-apphub-cli remove fiery

nx-apphub-cli update nano

nx-apphub-cli downgrade mc

nx-apphub-cli search nano mc fiery

nx-apphub-cli show

nx-apphub-cli build app.yml 
  ↪ (debug) nx-apphub-cli build app.yml --appdir-lint squashfs-root/

nx-apphub-cli generate \
  --package mc \
  --distro debian \
  --release testing \
  --arch amd64 \
  --components main \
  --output mc.yml
```

# Licensing

The license for this repository and its contents is **BSD-3-Clause**.

# Issues

If you find problems with the contents of this repository, please create an issue and use the **🐞 Bug report** template.

## Submitting a bug report

Before submitting a bug, you should look at the [existing bug reports]([url](https://github.com/Nitrux/nx-apphub/issues)) to verify that no one has reported the bug already.

©2025 Nitrux Latinoamericana S.C.
