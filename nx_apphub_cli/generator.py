#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import gzip
import lzma
import re
from io import BytesIO

import requests
from rich.console import Console

from .exceptions import GeneratorError

console = Console()

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
        "https://origin.archive.neon.kde.org/stable",
    ],
    "nitrux": [
        "https://packagecloud.io/nitrux/mauikit/debian",
        "https://packagecloud.io/nitrux/area51/debian",
    ]
}


def fetch_repository_metadata(distro, release, arch, components):
    """Fetch the Debian repository metadata."""
    metadata = ""
    mirrors = distro_mirrors.get(distro)

    if mirrors is None:
        supported = ', '.join(distro_mirrors.keys())
        raise GeneratorError(f"Unknown distribution '{distro}'. Supported: {supported}")

    console.print(f" Fetching repository metadata for [cyan]{distro}/{release}[/cyan]...")
    console.print()

    total_tasks = len(mirrors) * len(components)
    completed = 0

    for mirror in mirrors:
        for component in components:
            completed += 1
            mirror_host = mirror.split('//')[1].split('/')[0]
            console.print(
                f"   [{completed}/{total_tasks}] Checking [yellow]{component}[/yellow] "
                f"from [dim]{mirror_host}[/dim]..."
            )

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
                    console.print("🚧 Could not fetch metadata from the repository.")
                    console.print(f"  ↪ URL: {url}")

                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code
                        reason = e.response.reason
                        console.print(
                            f"      ↪ Issue: The server returned a "
                            f"'{status_code} {reason}' error."
                        )
                    else:
                        console.print(f"      ↪ Issue: {e}")
                    console.print()
                    console.print(
                        "👉 Tip: A '404 Not Found' error usually means the "
                        "combination of distribution, release, or component is incorrect."
                    )
                    console.print()

    console.print()
    console.print(" Metadata fetched successfully.\n")
    return metadata


def parse_package_info(package_name, metadata):
    """Parse the package information from the repository metadata."""
    packages = metadata.split('\n\n')
    for entry in packages:
        if f"Package: {package_name}\n" in entry:
            return entry
    return None


def extract_field(entry, field):
    """Extract a specific field from the package information."""
    pattern = re.compile(rf"^{field}: (.+)$", re.MULTILINE)
    match = pattern.search(entry)
    return match.group(1) if match else None


def parse_dependencies(dep_line):
    """Parse the dependencies from the package information."""
    if not dep_line:
        return []
    deps = []
    for dep in dep_line.split(','):
        name = dep.strip().split('|')[0].strip().split(' ')[0]
        if name not in excluded_packages:
            deps.append(name)
    return deps


def parse_fields(entry):
    """Parse the fields from the package information."""
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


def generate_yaml(package_name, distro, release, arch, components, integration_key="gui", runtime="classic"):
    """Generate the YAML data for the package."""
    console.print(f"\n Searching for package: [bold cyan]{package_name}[/bold cyan]\n")

    metadata = fetch_repository_metadata(distro, release, arch, components)

    if not metadata:
        raise GeneratorError(
            f"Could not fetch metadata for {distro}/{release}.\n"
            "Please check your internet connection or the distribution parameters (release, components)."
        )

    console.print(f" Parsing package information for [cyan]{package_name}[/cyan]...\n")
    entry = parse_package_info(package_name, metadata)
    if not entry:
        components_str = ', '.join(components)
        raise GeneratorError(
            f"Unable to find '{package_name}' in the repository metadata.\n"
            f"  ↪ (Searched in Distro: {distro}, Release: {release}, "
            f"Components: {components_str})\n"
            "\n"
            "👉 Tip: The package might be in a different component. "
            "Try adding them to your command, e.g.: --components main universe"
        )

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
            "type": integration_key,
            "launcher": ""
        }
    }
    return yaml_data, fields


def generate_description_md(fields):
    """Generate the description in Markdown format."""
    name = fields.get("Package", "UNKNOWN")
    desc_raw = fields.get("Description", "No summary available")
    try:
        summary = desc_raw.split("--", 1)[-1].strip()
    except IndexError:
        summary = desc_raw.splitlines()[0] if desc_raw else "No summary available"

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
