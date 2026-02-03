#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import shutil
import subprocess
from pathlib import Path

from .exceptions import ExtractionError
from .console import print_success, print_info

# <---
# --->
# -- Extract .deb files into the correct package directory.

def extract_deb(deb_path, package_name, quiet=True):
    """Extracts a .deb package into its designated AppDir."""

    if deb_path is None:
        return

    package_dir = Path.home() / ".cache/nx-apphub-cli" / package_name
    app_dir = package_dir / "AppDir"
    deb_dir = package_dir / "debs"

    app_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = deb_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print_info(f"Extracting {deb_path}...", prefix="🗄️")

    try:
        subprocess.run(
            ["ar", "x", deb_path], 
            cwd=temp_dir, 
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        archive_files = list(temp_dir.glob("data.tar.*"))
        if not archive_files:
            raise ExtractionError(f"No valid data archive found in {deb_path}.")

        data_archive = archive_files[0]

        if data_archive.suffix in [".xz", ".gz"]:
            subprocess.run(
                ["tar", "xf", str(data_archive), "-C", str(app_dir)], 
                check=True,
                stderr=subprocess.PIPE
            )
        elif data_archive.suffix == ".zst":
            decompressed_archive = temp_dir / "data.tar"
            subprocess.run(
                ["unzstd", "-d", str(data_archive), "-o", str(decompressed_archive)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            subprocess.run(
                ["tar", "xf", str(decompressed_archive), "-C", str(app_dir)], 
                check=True,
                stderr=subprocess.PIPE
            )
        else:
            raise ExtractionError(f"Unsupported archive format in {deb_path}: {data_archive.suffix}")

        if not quiet:
            print_success(f"Extracted {deb_path} successfully.", prefix="🗃️")

        # -- Ensure that libraries are correctly moved without overwriting existing ones.

        lib_dir = app_dir / "usr/lib"
        lib_dir.mkdir(parents=True, exist_ok=True)

        for extracted_file in (app_dir / "lib").glob("*.so*"):
            target_file = lib_dir / extracted_file.name
            if not target_file.exists():
                shutil.move(str(extracted_file), str(target_file))
                if not quiet:
                    print_info(f"Moved {extracted_file} → {target_file}", prefix="")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode(errors='replace').strip() if e.stderr else str(e)
        raise ExtractionError(f"Extraction failed for {deb_path}: {error_msg}") from e

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
