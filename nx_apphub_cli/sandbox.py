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

import os
from pathlib import Path


# -- Bubblewrap flag mappings.

bwrap_boolean_flags = {
    "ro-root": ["--ro-bind", "/", "/"],
    "dev": ["--dev", "/dev"],
    "proc": ["--proc", "/proc"],
    "tmpfs": ["--tmpfs", "/tmp"],
    "mqueue": ["--mqueue", "/dev/mqueue"],
    "ro-home": ["--ro-bind", os.getenv("HOME"), os.getenv("HOME")],
    "no-net": ["--unshare-net"],
    "no-ipc": ["--unshare-ipc"],
    "no-pid": ["--unshare-pid"],
    "unshare-user": ["--unshare-user"],
    "unshare-uts": ["--unshare-uts"],
    "unshare-cgroup": ["--unshare-cgroup"],
    "new-session": ["--new-session"],
    "cap-drop-all": ["--cap-drop", "ALL"],
    "die-with-parent": ["--die-with-parent"],
    "clearenv": ["--clearenv"]
}

bwrap_list_flags = {
    "bwrap_env": lambda key, val: [],
    "bwrap_unset-env": lambda k, v: ["--unsetenv", v],
    "cap-drop": lambda k, v: ["--cap-drop", v],
    "bind": lambda k, v: ["--bind"] + v.split(":", 1),
    "ro-bind": lambda k, v: ["--ro-bind"] + v.split(":", 1),
    "bind-try": lambda k, v: ["--bind-try"] + v.split(":", 1),
    "ro-bind-try": lambda k, v: ["--ro-bind-try"] + v.split(":", 1),
    "remount-ro": lambda k, v: ["--remount-ro", v]
}

bwrap_key_value_flags = {
    "hostname": "--hostname",
    "chdir": "--chdir",
    "file-label": "--file-label",
    "exec-label": "--exec-label",
    "seccomp": "--seccomp"
}


def get_known_apparmor_profiles():
    profile_dir = "/etc/apparmor.d/"
    try:
        return {f for f in os.listdir(profile_dir) if not f.startswith(".")}
    except FileNotFoundError:
        return set()


def generate_firejail_profile(profile_name: str):
    """Generate a minimal Firejail profile and save it."""
    
    profile_dir = Path.home() / ".local/share/nx-apphub-cli/firejail.d"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / f"{profile_name}.profile"
    profile_content = f"""# Minimal Firejail profile for {profile_name}

# Enable a default firewall

netfilter

# Restrict filesystem access

private
noroot
restrict-namespaces
seccomp
disable-mnt
private-cache
private-cwd
private-dev
caps
"""

    # -- Write the profile to the file.

    with open(profile_path, "w") as f:
        f.write(profile_content)

    print(f"🔒 Firejail profile saved to: {profile_path}\n")
    return profile_path


def get_sandbox_exec_block(sandbox: dict, exec_cmd: str) -> str:
    """Return the appropriate sandbox execution line."""
    sandbox_type = sandbox.get("type", "none")

    # -- Handle Firejail use.

    if sandbox_type == "firejail":
        profile_name = f"{sandbox.get('name', 'default-appbox')}-profile"
        firejail_profile = str(Path.home() / f".local/share/nx-apphub-cli/firejail.d/{profile_name}")

        if not os.path.exists(firejail_profile):
            firejail_profile = generate_firejail_profile(profile_name)

        apparmor_profile = sandbox.get("aa_profile", "none")
        cmd = f'"$APPDIR{exec_cmd}" "$@"'
        if apparmor_profile != "none":
            return f'exec /usr/bin/firejail --profile={firejail_profile} --apparmor="{apparmor_profile}" {cmd}'
        return f'exec /usr/bin/firejail --profile={firejail_profile} {cmd}'

    # -- Handle Bubblewrap use.

    if sandbox_type == "bwrap":
        bwrap_args = ["/usr/bin/bwrap"]

        for key, flag in bwrap_boolean_flags.items():
            if sandbox.get(key):
                bwrap_args += flag

        for key, transform in bwrap_list_flags.items():
            for item in sandbox.get(key, []):
                if isinstance(item, str):
                    item = item.replace("~", "$HOME")
                bwrap_args += [arg if arg.startswith("--") else f'"{arg}"' for arg in transform(key, item)]

        for item in sandbox.get("bwrap_env", []):
            if isinstance(item, dict):
                for k, v in item.items():
                    bwrap_args += ["--setenv", k, f'"{v}"']

        for item in sandbox.get("bwrap_unset-env", []):
            bwrap_args += ["--unsetenv", item]

        for key, flag in bwrap_key_value_flags.items():
            if key in sandbox:
                bwrap_args += [flag, f'"{sandbox[key]}"']

        bwrap_args.append(f'"$APPDIR{exec_cmd}"')
        bwrap_args.append('"$@"')

        return "exec " + " ".join(bwrap_args)

    return f'exec "$APPDIR{exec_cmd}" "$@"'
