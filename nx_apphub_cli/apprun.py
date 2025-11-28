#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

from datetime import datetime

from .exceptions import BuildError
from .config import get_apprunconf_value
from .utils import get_architecture
from .sandbox import get_sandbox_exec_block

# <---
# --->
def generate_apprun(app_dir, config):
    """Generate the AppRun script dynamically inside the AppImage."""
    apprun_path = app_dir / "AppRun"

    # -- Fetch and validate settings from YAML.

    exec_cmd = get_apprunconf_value(config, "exec", expected_type=str)
    setpath = get_apprunconf_value(config, "setpath", default="/usr/bin", expected_type=str)
    setlibpath = get_apprunconf_value(config, "setlibpath", default="/usr/lib", expected_type=str)
    envvars = get_apprunconf_value(config, "envvars", default={}, expected_type=dict)

    # -- Append to the base path in the generated AppRun.

    yaml_ld_value = envvars.pop("LD_LIBRARY_PATH", None)
    ld_append_line = ""
    if yaml_ld_value:
        if isinstance(yaml_ld_value, list):
            extra_ld = ":".join(str(v) for v in yaml_ld_value if v)
        else:
            extra_ld = str(yaml_ld_value).strip()
        if extra_ld:
            ld_append_line = f'\nexport LD_LIBRARY_PATH="$LD_LIBRARY_PATH:{extra_ld}"'

    # -- Generate environment variable exports dynamically.

    env_exports = "\n".join([f'export {key}="{str(value).replace("\"", "\\\"")}"' for key, value in envvars.items()])

    # -- Conditionally add initialization for Qt environment variables **only if they exist in envvars**.

    qt_keys = [
        "QT_QPA_PLATFORM",
        "QT_PLUGIN_PATH",
        "QT_QML_IMPORT_PATH",
        "QML_IMPORT_PATH",
        "QML2_IMPORT_PATH",
        "QTWEBENGINEPROCESS_PATH",
        "QTWEBENGINE_RESOURCES_PATH",
        "QTWEBENGINE_LOCALES_PATH",
        "QT_QUICK_CONTROLS_STYLE",
        "QT_QUICK_CONTROLS_MOBILE",
        "QT_DEBUG_PLUGINS",
    ]

    qt_lines = []
    for key in qt_keys:
        if key in envvars:
            qt_lines.append(f'if [ -z "${{{key}+x}}" ]; then export {key}=""; fi')

    qt_env_init = "\n".join(qt_lines)

    # -- Determine multiarch triplet dynamically.

    arch_map = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }

    arch = get_architecture()
    multiarch_triplet = arch_map.get(arch)
    if multiarch_triplet is None:
        raise BuildError(f"Unsupported architecture '{arch}' for AppRun generation.")


    # -- Construct the script.

    current_year = datetime.now().year
    copyright_str = f"# Copyright <{current_year}> <Nitrux Latinoamericana S.C. <hello@nxos.org>>"

    sandbox_exec_block = get_sandbox_exec_block(config.get("sandbox", {}), exec_cmd)

    apprun_script = f"""#!/usr/bin/env bash

# SPDX-License-Identifier: BSD-3-Clause
{copyright_str}


# -- Exit on errors.

set -eu


# -- Get the running directory of the AppImage.

REALPATH=$(readlink -f "$0")
APPDIR=$(dirname "$REALPATH")


# -- Ensure environment variables are always set to avoid unbound variable errors.

if [ -z "${{PATH+x}}" ]; then export PATH=""; fi
if [ -z "${{LD_LIBRARY_PATH+x}}" ]; then export LD_LIBRARY_PATH=""; fi
if [ -z "${{XDG_DATA_DIRS+x}}" ]; then export XDG_DATA_DIRS=""; fi


# -- Initialize Qt environment variables if required.

{qt_env_init}


# -- Set environment variables for proper execution inside the AppImage.

export PATH="$APPDIR{setpath}:$APPDIR/usr/sbin"
export LD_LIBRARY_PATH="$APPDIR{setlibpath}:$APPDIR{setlibpath}/{multiarch_triplet}:$APPDIR{setlibpath}64:$APPDIR/lib:$APPDIR/lib64:$APPDIR/lib/{multiarch_triplet}:$APPDIR/lib64/{multiarch_triplet}"{ld_append_line}
export XDG_DATA_DIRS="$APPDIR/usr/share:$XDG_DATA_DIRS"


# -- Additional environment variables from YAML.

{env_exports}


# -- Run the application.

{sandbox_exec_block}
"""

    with open(apprun_path, "w", encoding="utf-8") as f:
        f.write(apprun_script)

    apprun_path.chmod(0o755)
