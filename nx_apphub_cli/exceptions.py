#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

# <---
# --->
# -- Define exception classes.

class NxAppHubError(Exception):
    """Base class for all nx-apphub-cli errors."""


class ConfigError(NxAppHubError):
    """Raised when the YAML configuration file is invalid."""


class DownloadError(NxAppHubError):
    """Raised when a download operation fails."""


class ExtractionError(NxAppHubError):
    """Raised when extracting packages or files fails."""


class BuildError(NxAppHubError):
    """Raised when building an AppDir fails."""


class RepoError(NxAppHubError):
    """Raised when repository metadata or sources are invalid."""


class SandboxError(NxAppHubError):
    """Raised when sandbox configuration or validation fails."""


class ManagerError(NxAppHubError):
    """Raised when install, update, or removal operations fail."""


class GeneratorError(NxAppHubError):
    """Raised when generating YAML or metadata fails."""
