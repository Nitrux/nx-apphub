# NX Applications Hub | [![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<p align="center">
  <img width="128" height="128" src="https://raw.githubusercontent.com/Nitrux/luv-icon-theme/refs/heads/master/Luv/mimetypes/64/application-x-iso9660-appimage.svg">
</p>

# Introduction

NX Applications Hub is a powerful CLI tool developed to streamline the creation and management of AppImages on [Nitrux OS](https://nxos.org/). Leveraging the capabilities of [Distrobox](https://distrobox.it/) containers, NX Applications Hub automates the intricate process of packaging software, enabling developers and advanced users to generate portable and self-contained applications with ease and efficiency.

> ⚠️ Important: NX Applications Hub is designed for use on Nitrux OS. Attempting to use this utility on other distributions may lead to unexpected behavior and is not supported. Please refrain from opening issues related to using NX Applications Hub on non-Nitrux distributions, as they will be closed.

# Overview

NX Applications Hub offers a suite of features that simplify the AppImage packaging workflow:

- Automated Packaging: Seamlessly package applications into AppImages using Distrobox containers.
- Parallel Processing: Accelerate the build process by running multiple builds in parallel.
- Comprehensive Logging: Monitor build, removal, and update processes with detailed logs.
- Dependency Management: Automatically handle dependencies required for building AppImages.
- Rollback Support: Maintain system stability with rollback capabilities in case of build failures.

---

### What NX Applications Hub is

- A packaging tool: Facilitates the conversion of applications into AppImage format for portability.
- An automation utility: Streamlines the build, removal, and update processes through automation.

### What NX Applications Hub is not

- A distribution manager: Does not handle system package management outside AppImage creation.
- Compatible with all fistributions: Specifically tailored for Nitrux OS; not intended for use on other Linux distributions.

----

### Requirements

Before installing NX Applications Hub, ensure that your system meets the following requirements:

- Distrobox: Required for container management. Install it by following the [Distrobox Installation Guide](https://distrobox.it/#installation).
- Python 3.6 or Higher: Ensure Python is installed. Check with `python3 --version`.
- PyYAML: Python library for YAML parsing. Automatically installed via setup.py, but can be manually installed using:

```
pip3 install PyYAML
```

# Installation

Follow the steps below to install NX Applications Hub on your Nitrux OS system.

1. Clone the Repository

```
git clone https://github.com/Nitrux/nx-apphub.git
cd nx-apphub-cli
```

2. Create a Virtual Environment (Optional but Recommended)

```
python3 -m venv venv
source venv/bin/activate
```

3. Install the Package

Install NX Applications Hub in editable mode to allow for easy updates during development.

```
pip3 install -e .
```

4. Verify the Installation

Ensure that the nx-apphub-cli command is available:

```
nx-apphub-cli --help
```

You should see a help message detailing available commands and options.

# Usage

NX Applications Hub provides three primary commands: install, remove, and update. Below are detailed instructions and examples for each.

### Install AppImages

Build AppImages for specified applications.

#### Syntax:

```
nx-apphub-cli install <app-name> [<app-name> ...] [--parallel <number>] [--log-level <level>]
```

#### Options:

`--parallel <number>`: Number of parallel build processes to run. (Default: 1)
`--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set the logging level. (Default: INFO)

#### Example:

```
# Build AppImages for 'testapp' and 'sampleapp' with default settings
nx-apphub-cli install testapp sampleapp

# Build AppImages with increased parallelism and debug logging
nx-apphub-cli install testapp sampleapp --parallel 4 --log-level DEBUG
```

### Remove AppImages

Remove specified AppImages from your system.

#### Syntax:

```
nx-apphub-cli remove <app-name> [<app-name> ...] [--log-level <level>]

```

#### Options:

`--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set the logging level. (Default: INFO)

#### Example:

```
# Remove AppImage for 'testapp'
nx-apphub-cli remove testapp

# Remove AppImages with warning level logging
nx-apphub-cli remove testapp sampleapp --log-level WARNING
```

### Update AppImages

#### Syntax:

```
nx-apphub-cli update [--log-level <level>]
```

#### Options:

`--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set the logging level. (Default: INFO)

#### Example:

```
# Update all AppImages with default settings
nx-apphub-cli update

# Update all AppImages with debug logging
nx-apphub-cli update --log-level DEBUG
```

# Licensing

The license for this repository and its contents is **BSD-3-Clause**.

# Contributing

Contributions are welcome! If you'd like to contribute to NX Applications Hub, please follow these steps:

1. Fork the Repository: Click the "Fork" button at the top-right corner of the repository page.
2. Clone Your Fork:

```
git clone https://github.com/yourusername/nx-apphub-cli.git
cd nx-apphub-cli
```

3. Create a New Branch:

```
git checkout -b feature/your-feature-name
```

4. Make Your Changes: Implement your feature or fix.
5. Commit Your Changes:

```
git commit -m "Add feature: Your feature description."
```
6. Push to Your Fork:

```
git push origin feature/your-feature-name
```

7. Create a Pull Request: Navigate to the original repository and click "New Pull Request."

# Issues

If you encounter any problems or have suggestions for improvements, please create an issue in the GitHub Issues section of the repository. Provide detailed information to help us address the issue effectively.

> Note: As mentioned earlier, NX Applications Hub is intended for use on Nitrux OS. Issues related to using this tool on other distributions will not be addressed.

©2024 Nitrux Latinoamericana S.C.
