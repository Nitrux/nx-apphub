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

import argparse
import gzip
import lzma
import re
from io import BytesIO
from pathlib import Path

import requests
import yaml
# <---
# --->
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
        "https://ftp.debian.org/debian",
        "https://uk.mirrors.clouvider.net/debian",
        "https://atl.mirrors.clouvider.net/debian",
        "https://ftp.tu-clausthal.de/debian",
    ],
    "ubuntu": [
        "https://archive.ubuntu.com/ubuntu",
        "https://security.ubuntu.com/ubuntu",
        "https://mirrors.kernel.org/ubuntu",
    ],
    "devuan": [
        "http://deb.devuan.org/merged",
    ],
    "kde-neon": [
        "https://origin.archive.neon.kde.org/stable/",
    ],
    "nitrux": [
        "https://packagecloud.io/nitrux/mauikit/debian",
        "https://packagecloud.io/nitrux/area51/debian",
    ]
}


def fetch_repository_metadata(distro, release, arch, components):
    metadata = ""
    mirrors = distro_mirrors.get(distro, [])

    for mirror in mirrors:
        for component in components:
            base_url = f"{mirror}/dists/{release}/{component}/binary-{arch}/"
            urls_to_try = [base_url + "Packages.gz", base_url + "Packages.xz"]
            
            for url in urls_to_try:
                try:
                    r = requests.get(url, timeout=10)

                    if r.status_code == 404:
                        continue
                    
                    r.raise_for_status()

                    content = r.content
                    if url.endswith(".gz"):
                        with gzip.open(BytesIO(content), 'rt', encoding='utf-8', errors='ignore') as f:
                            metadata += f.read()
                    elif url.endswith(".xz"):
                        with lzma.open(BytesIO(content), 'rt', encoding='utf-8', errors='ignore') as f:
                            metadata += f.read()
                    
                    break

                except requests.exceptions.RequestException as e:
                    print(f"🚧 Could not fetch metadata from the repository.")
                    print(f"  ↪ URL: {url}")
                    
                    if hasattr(e, 'response') and e.response is not None:
                        print(f"  ↪ Issue: The server returned a '{e.response.status_code} {e.response.reason}' error.")
                    else:
                        print(f"  ↪ Issue: {e}")
                    print()
                    print("👉 Tip: A '404 Not Found' error usually means the combination of distribution, release, or component is incorrect.")
                    print()

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


def parse_fields(entry):
    fields = {}
    current_key = None
    buffer = []

    for line in entry.splitlines():
        if line.strip() == "":
            continue
        if re.match(r"^[A-Z][A-Za-z0-9-]*: ", line):
            if current_key:
                fields[current_key] = " ".join(buffer).strip()
            current_key, value = line.split(":", 1)
            buffer = [value.strip()]
        elif current_key:
            buffer.append(line.strip())

    if current_key:
        fields[current_key] = " ".join(buffer).strip()

    return fields


def generate_yaml(package_name, distro, release, arch, components, integration_key="gui_app", runtime="classic"):
    metadata = fetch_repository_metadata(distro, release, arch, components)
    if not metadata:
        return None, None

    entry = parse_package_info(package_name, metadata)
    if not entry:
        print()
        print(f"🚧 Unable to find '{package_name}' in the repository metadata.")
        print(f"  ↪ (Searched in Distro: {distro}, Release: {release}, Components: {', '.join(components)})")
        print()
        print(f"👉 Tip: The package might be in a different component. Try adding them to your command, e.g.: --components main universe")
        print()
        return None, None

    fields = parse_fields(entry)

    version = fields.get("Version", "latest")
    depends = fields.get("Depends", "")
    deps = parse_dependencies(depends)

    deps.append(package_name)

    distro_entry = {
        "distro": distro,
        "release": release,
        "arch": arch,
        "components": components
    }

    yaml_data = {
        "buildinfo": {
            "name": package_name,
            "version": version,
            "binarypath": "/usr/bin/REPLACE-ME",
            "distrorepo": [distro_entry],
            "deps": deps,
            "runtime": runtime
        },
        "apprunconf": {
            "exec": "/usr/bin/REPLACE-ME",
            "setpath": "/usr/bin",
            "setlibpath": "/usr/lib",
            "envvars": {},
            "extra_rpaths" : [],
            "prebuild_commands": []
        },
        "sandbox": {
            "type": "none"
        },
        "integration": {
            "type": integration_key
        }
    }
    return yaml_data, fields


def generate_description_md(fields):
    name = fields.get("Package", "UNKNOWN")
    summary = fields.get("Description", "No summary available").split("--", 1)[-1].strip()
    full_desc = fields.get("Description", "No description provided.")
    apphub_category = fields.get("Category", "Not specified in metadata.")
    homepage = fields.get("Homepage", "https://example.com")
    license_name = fields.get("License", "Not specified in metadata")

    depends = fields.get("Depends", "").split(",")
    depends = [d.strip().split(" ")[0].split("|")[0] for d in depends if d]

    markdown = f"""# {name}

## Summary

{summary}

## Description

{full_desc}

## Category

{apphub_category}

## Homepage

[{homepage}]({homepage})

## License

{license_name}
"""

    return markdown
