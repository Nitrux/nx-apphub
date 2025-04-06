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

import gzip
import requests
import argparse
import yaml
from io import BytesIO
from pathlib import Path
import re


# -- Packages to exclude from being added to the YAML.

excluded_packages = {
    "libc6", 
    "libglib2.0-0t64", 
    "libglib2.0-0", 
    "libgcc-s1", 
    "libstdc++6",
    "libglx0",
    "libegl1",
    "libgl1"
}

distro_mirrors = {
    "debian": [
        "http://deb.debian.org/debian",
        "http://ftp.debian.org/debian",
        "http://ftp.uk.debian.org/debian",
        "http://ftp.us.debian.org/debian",
        "http://ftp.de.debian.org/debian",
    ],
    "ubuntu": [
        "http://archive.ubuntu.com/ubuntu",
        "http://security.ubuntu.com/ubuntu",
    ],
    "devuan": [
        "http://deb.devuan.org/devuan",
        "http://devuan.ipacct.com/devuan",
        "http://mirror.vpgrp.io/devuan",
        "http://mirrors.dotsrc.org/devuan",
    ],
    "kde-neon": [
        "https://archive.neon.kde.org/user",
    ]
}


def fetch_packages_metadata(distro, release, arch, components):
    metadata = ""
    mirrors = distro_mirrors.get(distro, [])

    for mirror in mirrors:
        for component in components:
            url = f"{mirror}/dists/{release}/{component}/binary-{arch}/Packages.gz"
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                with gzip.open(BytesIO(r.content), 'rt', encoding='utf-8', errors='ignore') as f:
                    metadata += f.read()
                return metadata
            except Exception as e:
                print(f"❌ Error: Failed to fetch metadata from {url}: {e}")
    return metadata


def parse_package_info(package_name, metadata):
    packages = metadata.split('\n\n')
    for entry in packages:
        if f"Package: {package_name}\n" in entry:
            return entry
    return None


def extract_field(entry, field):
    pattern = re.compile(rf"^{field}: (.+)$", re.MULTILINE)
    match = pattern.search(entry)
    return match.group(1) if match else None


def parse_dependencies(dep_line):
    if not dep_line:
        return []
    deps = []
    for dep in dep_line.split(','):
        name = dep.strip().split('|')[0].strip().split(' ')[0]
        if name not in excluded_packages:
            deps.append(name)
    return deps


def generate_yaml(package_name, distro, release, arch, components):
    metadata = fetch_packages_metadata(distro, release, arch, components)
    entry = parse_package_info(package_name, metadata)

    if not entry:
        print(f"❌ Error: Package '{package_name}' not found in metadata.")
        return None

    version = extract_field(entry, "Version") or "latest"
    depends = extract_field(entry, "Depends")
    deps = parse_dependencies(depends)

    yaml_data = {
        "buildinfo": {
            "name": package_name,
            "version": version,
            "binarypath": "/usr/bin/REPLACE-ME",
            "distrorepo": [
                {
                    "distro": distro,
                    "release": release,
                    "arch": arch,
                    "components": components
                }
            ],
            "deps": deps
        },
        "apprunconf": {
            "exec": "/usr/bin/REPLACE-ME",
            "setpath": "/usr/bin",
            "setlibpath": "/usr/lib",
            "envvars": {},
            "prebuild_commands": []
        }
    }
    return yaml_data


def main():
    parser = argparse.ArgumentParser(description="Generate nx-apphub-cli YAML template from repository metadata")
    parser.add_argument("--package", required=True, help="Package name")
    parser.add_argument("--distro", required=True, help="Distribution name (e.g., ubuntu)")
    parser.add_argument("--release", required=True, help="Release codename (e.g., oracular)")
    parser.add_argument("--arch", default="amd64", help="Architecture (default: amd64)")
    parser.add_argument("--components", nargs="*", default=["main"], help="APT components (default: main)")
    parser.add_argument("--output", default="app.yml", help="Output YAML file")

    args = parser.parse_args()

    yaml_data = generate_yaml(
        args.package,
        args.distro,
        args.release,
        args.arch,
        args.components
    )

    if yaml_data:
        with open(args.output, "w") as f:
            yaml.dump(yaml_data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
        print(f"✅ YAML template written to: {args.output}")

if __name__ == "__main__":
    main()
