#!/usr/bin/env python3

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
#   Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>                                                                                                                   #
#                                                                                                                                                                           #
#   Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:                          #
#                                                                                                                                                                           #
#    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.                                        #
#                                                                                                                                                                           #
#    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer                                      #
#       in the documentation and/or other materials provided with the distribution.                                                                                         #
#                                                                                                                                                                           #
#    3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software                    #
#       without specific prior written permission.                                                                                                                          #
#                                                                                                                                                                           #
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,                      #
#    THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS                  #
#    BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE                 #
#    GOODS OR SERVICES; LOSS OF USE, DATA,   OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,                      #
#    STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.   #
#############################################################################################################################################################################

from datetime import datetime

from .config import get_apprunconf_value
from .utils import get_architecture
from .sandbox import get_sandbox_exec_block


def generate_apprun(app_dir, config):
    """Generate the AppRun script dynamically inside the AppImage."""
    apprun_path = app_dir / "AppRun"

    # -- Fetch settings from YAML. Exit if missing.

    exec_cmd = get_apprunconf_value(config, "exec", expected_type=str)
    setpath = get_apprunconf_value(config, "setpath", default="/usr/bin", expected_type=str)
    setlibpath = get_apprunconf_value(config, "setlibpath", default="/usr/lib", expected_type=str)
    envvars = get_apprunconf_value(config, "envvars", default={}, expected_type=dict)

    # -- Generate environment variable exports dynamically.

    env_exports = "\n".join([f'export {key}="{value}"' for key, value in envvars.items()])

    # -- Conditionally add initialization for Qt environment variables **only if they exist in envvars**.

    qt_env_init = ""
    if "QT_PLUGIN_PATH" in envvars:
        qt_env_init += 'if [ -z "${QT_PLUGIN_PATH+x}" ]; then export QT_PLUGIN_PATH=""; fi\n'
    if "QT_QML_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QT_QML_IMPORT_PATH+x}" ]; then export QT_QML_IMPORT_PATH=""; fi\n'
    if "QML_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QML_IMPORT_PATH+x}" ]; then export QML_IMPORT_PATH=""; fi\n'
    if "QML2_IMPORT_PATH" in envvars:
        qt_env_init += 'if [ -z "${QML2_IMPORT_PATH+x}" ]; then export QML2_IMPORT_PATH=""; fi\n'
    if "QTWEBENGINEPROCESS_PATH" in envvars:
            qt_env_init += 'if [ -z "${QTWEBENGINEPROCESS_PATH+x}" ]; then export QTWEBENGINEPROCESS_PATH=""; fi\n'
    if "QTWEBENGINE_RESOURCES_PATH" in envvars:
            qt_env_init += 'if [ -z "${QTWEBENGINE_RESOURCES_PATH+x}" ]; then export QTWEBENGINE_RESOURCES_PATH=""; fi\n'
    if "QTWEBENGINE_LOCALES_PATH" in envvars:
            qt_env_init += 'if [ -z "${QTWEBENGINE_LOCALES_PATH+x}" ]; then export QTWEBENGINE_LOCALES_PATH=""; fi\n'

    # -- Determine multiarch triplet dynamically.

    arch_map = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }

    arch = get_architecture()
    multiarch_triplet = arch_map.get(arch)

    # -- Construct the script.

    current_year = datetime.now().year
    copyright_str = f"#   Copyright <{current_year}> <Nitrux Latinoamericana S.C. <hello@nxos.org>>"
    copyright_line = copyright_str.ljust(172) + "#"


    # -- Verify the content of the sandbox section.

    sandbox = config.get("sandbox", {})

    # -- Use get_sandbox_exec_block to generate the sandbox execution block.

    sandbox_exec_block = get_sandbox_exec_block(config, exec_cmd)

    # -- Verify that the sandbox_exec_block is correctly generated.

    sandbox_exec_block = get_sandbox_exec_block(config.get("sandbox", {}), exec_cmd)

    apprun_script = f"""#!/usr/bin/env bash

#############################################################################################################################################################################
#   The license used for this file and its contents is: BSD-3-Clause                                                                                                        #
#                                                                                                                                                                           #
{copyright_line}
#                                                                                                                                                                           #
#   Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:                          #
#                                                                                                                                                                           #
#    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.                                        #
#                                                                                                                                                                           #
#    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer                                      #
#       in the documentation and/or other materials provided with the distribution.                                                                                         #
#                                                                                                                                                                           #
#    3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software                    #
#       without specific prior written permission.                                                                                                                          #
#                                                                                                                                                                           #
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,                      #
#    THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS                  #
#    BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE                 #
#    GOODS OR SERVICES; LOSS OF USE, DATA,   OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,                      #
#    STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.   #
#############################################################################################################################################################################


# -- Exit on errors.

set -eu


# -- Get the running directory of the AppImage.

REALPATH=$(readlink -f "$0")
APPDIR=$(dirname "$REALPATH")


# -- Ensure environment variables are always set to avoid unbound variable errors.

if [ -z "${{PATH+x}}" ]; then export PATH=""; fi
if [ -z "${{LD_LIBRARY_PATH+x}}" ]; then export LD_LIBRARY_PATH=""; fi
if [ -z "${{XDG_DATA_DIRS+x}}" ]; then export XDG_DATA_DIRS=""; fi


# -- Set environment variables for proper execution inside the AppImage.

export PATH="$APPDIR{setpath}:$APPDIR/usr/sbin"
export LD_LIBRARY_PATH="$APPDIR{setlibpath}:$APPDIR{setlibpath}/{multiarch_triplet}:$APPDIR{setlibpath}64:$APPDIR{setlibpath}/{multiarch_triplet}/inkscape:$APPDIR{setlibpath}/{multiarch_triplet}/libproxy"
export XDG_DATA_DIRS="$APPDIR/usr/share:$XDG_DATA_DIRS"


# -- Initialize Qt environment variables if required.

{qt_env_init}


# -- Additional environment variables from YAML.

{env_exports}


# -- Run the application.

{sandbox_exec_block}
"""

    with open(apprun_path, "w") as f:
        f.write(apprun_script)

    apprun_path.chmod(0o755)