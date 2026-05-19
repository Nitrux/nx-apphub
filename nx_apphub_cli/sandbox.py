#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os
from pathlib import Path

# <---
# --->
# -- Bubblewrap flag mappings.

bwrap_boolean_flags = {
    "ro-root": ["--ro-bind", "/", "/"],
    "dev": ["--dev-bind", "/dev", "/dev"],
    "proc": ["--proc", "/proc"],
    "tmpfs": ["--tmpfs", "/tmp"],
    "mqueue": ["--mqueue", "/dev/mqueue"],
    "ro-home": ["--ro-bind", "$HOME", "$HOME"],
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
    "bwrap-env": lambda _k, _v: [],
    "bwrap-unset-env": lambda _k, _v: [],
    "cap-drop": lambda _k, v: ["--cap-drop", v],
    "bind": lambda _k, v: ["--bind"] + v.split(":", 1),
    "ro-bind": lambda _k, v: ["--ro-bind"] + v.split(":", 1),
    "bind-try": lambda _k, v: ["--bind-try"] + v.split(":", 1),
    "ro-bind-try": lambda _k, v: ["--ro-bind-try"] + v.split(":", 1),
    "remount-ro": lambda _k, v: ["--remount-ro", v]
}

bwrap_key_value_flags = {
    "hostname": "--hostname",
    "chdir": "--chdir",
    "file-label": "--file-label",
    "exec-label": "--exec-label",
    "seccomp": "--seccomp"
}


def get_known_apparmor_profiles():
    """Return a set of AppArmor profiles found in /etc/apparmor.d/."""
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

    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile_content)

    print(f"🔒 Firejail profile saved to: {profile_path}\n")
    return profile_path


def get_sandbox_exec_block(sandbox: dict, exec_cmd: str) -> str:
    """Add the sanbox options to the AppRun exec block."""
    sandbox_type = sandbox.get("type", "none")

    if sandbox_type == "firejail":
        profile_name = f"{sandbox.get('name', 'default-appbox')}-profile"
        firejail_profile_path = (
            Path.home()
            / ".local/share/nx-apphub-cli/firejail.d"
            / f"{profile_name}.profile"
        )

        if not firejail_profile_path.exists():
            generate_firejail_profile(profile_name)

        apparmor_profile = sandbox.get("aa-profile", "none")
        cmd = f'"$APPDIR{exec_cmd}" "$@"'
        firejail_profile_str = str(firejail_profile_path)

        if apparmor_profile != "none":
            return (
                f'exec /usr/bin/firejail --profile="{firejail_profile_str}" '
                f'--apparmor="{apparmor_profile}" {cmd}'
            )
        return f'exec /usr/bin/firejail --profile="{firejail_profile_str}" {cmd}'

    if sandbox_type == "bwrap":
        argv = ["/usr/bin/bwrap"]

        for key, flag in bwrap_boolean_flags.items():
            if sandbox.get(key):
                argv.extend(flag)

        for key, transform in bwrap_list_flags.items():
            for item in sandbox.get(key, []):
                if isinstance(item, str):
                    item = item.replace("~", "$HOME")
                argv.extend(transform(key, item))

        for item in sandbox.get("bwrap-env", []):
            if isinstance(item, dict):
                for k, v in item.items():
                    argv.extend(["--setenv", k, v])

        for item in sandbox.get("bwrap-unset-env", []):
            argv.extend(["--unsetenv", item])

        for key, flag in bwrap_key_value_flags.items():
            if key in sandbox:
                argv.extend([flag, str(sandbox[key])])

        argv.append(f"$APPDIR{exec_cmd}")
        argv.append("$@")

        rendered = []
        for arg in argv:
            if arg == "/usr/bin/bwrap" or arg.startswith("--"):
                rendered.append(arg)
            elif arg == "$@":
                rendered.append('"$@"')
            else:
                escaped = arg.replace('"', '\\"')
                rendered.append(f'"{escaped}"')

        return "exec " + " ".join(rendered)

    return f'exec "$APPDIR{exec_cmd}" "$@"'
