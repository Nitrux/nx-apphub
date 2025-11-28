#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

import os
import subprocess
import gzip
import argparse
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re

import requests
import yaml
from elftools.elf.elffile import ELFFile

from .exceptions import BuildError

# <---
# --->
def detect_appdir(path):
    """Normalize a user-provided path and detect whether it points to a squashfs-root directory."""
    path = Path(path).expanduser().resolve()
    if path.name == "squashfs-root":
        return path
    if (path / "squashfs-root").is_dir():
        return path / "squashfs-root"
    return path


def is_elf(path):
    """Return True if the given file starts with an ELF header."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:
        return False


def library_exists_in_appdir(libname, appdir):
    """Check whether a library file with the given name exists somewhere inside the AppDir."""
    for _, _, files in os.walk(appdir):
        for file in files:
            if file == libname or file.startswith(libname + "."):
                return True
    return False


def find_missing_libs(appdir):
    """Scan ELF files in the AppDir and return a mapping of missing libraries to the binaries requiring them."""
    missing = {}
    for root, _, files in os.walk(appdir):
        for file in files:
            full_path = Path(root) / file
            if not is_elf(full_path):
                continue
            try:
                result = subprocess.check_output(['ldd', str(full_path)],
                                                 stderr=subprocess.DEVNULL,
                                                 text=True)
            except subprocess.CalledProcessError:
                continue
            for line in result.splitlines():
                if '=> not found' in line:
                    lib = line.split('=>')[0].strip()
                    if library_exists_in_appdir(lib, appdir):
                        continue
                    missing.setdefault(lib, []).append(str(full_path))
    return missing


def is_valid_appdir(appdir_path):
    """Return True if the given path appears to be a minimally valid AppDir."""
    if not appdir_path.is_dir():
        return False

    app_run = appdir_path / "AppRun"
    usr_dir = appdir_path / "usr"

    if not app_run.is_file():
        return False

    if not usr_dir.is_dir():
        return False

    return True


def suggest_providing_packages(missing_libs, repos, quiet=True):
    """
    Suggest Debian/Ubuntu packages that may provide the given missing libraries
    by scanning Contents-*.gz files from the appropriate repositories.
    """
    suggestions = {}
    seen_urls = set()

    lib_patterns = {
        lib: re.compile(rf"{re.escape(lib)}(\s|$)") for lib in missing_libs
    }

    if isinstance(repos, dict):
        repos = repos.get('base', []) + repos.get('ppas', [])

    for repo in repos:
        distro = repo.get("distro", "").lower()
        release = repo.get("release")
        arch = repo.get("arch")
        components = repo.get("components", ["main"])

        if not (distro and release and arch):
            if not quiet:
                print(f"⚠️  Skipping invalid repo definition: {repo}")
            continue

        if distro == "debian":
            mirrors = ["https://ftp.debian.org/debian"]
            subpath = "dists"
        elif distro == "ubuntu":
            mirrors = ["https://archive.ubuntu.com/ubuntu"]
            subpath = "dists"
        elif distro == "ubuntu-ports":
            mirrors = ["https://ports.ubuntu.com/ubuntu-ports"]
            subpath = "dists"
        elif distro == "devuan":
            mirrors = ["http://deb.devuan.org/merged"]
            subpath = "dists"
        elif distro == "kde-neon":
            mirrors = ["https://origin.archive.neon.kde.org/stable"]
            subpath = "dists"
        elif distro == "nitrux":
            if not quiet:
                print("⏩ Skipping Nitrux repository (no Contents file provided).")
            continue
        else:
            if not quiet:
                print(f"⏩ Unknown distro '{distro}', skipping.")
            continue

        for mirror in mirrors:
            for component in components:
                if distro in ("debian", "devuan"):
                    url = f"{mirror}/{subpath}/{release}/{component}/Contents-{arch}.gz"
                else:
                    url = f"{mirror}/{subpath}/{release}/Contents-{arch}.gz"

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                if not quiet:
                    print(f"📥 Downloading: {url}")

                try:
                    response = requests.get(url, timeout=20)
                    response.raise_for_status()

                    if not quiet:
                        print(f"📑 Parsing: {url}\n")

                    with gzip.open(BytesIO(response.content), 'rt',
                                   encoding='utf-8',
                                   errors='ignore') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.rsplit(None, 1)
                            if len(parts) != 2:
                                continue
                            path, pkg = parts
                            for lib, pattern in lib_patterns.items():
                                if pattern.search(path):
                                    if not quiet:
                                        print(f"✅ Matched {lib} → {pkg} in {url}")
                                    suggestions.setdefault(lib, set()).add(pkg)
                    if not quiet:
                        print()
                except Exception as e:
                    if not quiet:
                        print(f"⚠️  Failed to process {url}: {e}")
                    continue

    return {lib: sorted(set(pkgs)) for lib, pkgs in suggestions.items()}


def _read_dynamic_elf(path):
    """Extract DT_NEEDED, RPATH, and RUNPATH entries from an ELF binary."""
    with open(path, "rb") as f:
        elf = ELFFile(f)
        dyn = elf.get_section_by_name(".dynamic")
        if dyn is None:
            return [], None, None
        needed = []
        rpath = None
        runpath = None
        for tag in dyn.iter_tags():
            t = tag.entry.d_tag
            if t == "DT_NEEDED":
                needed.append(tag.needed)
            elif t == "DT_RPATH":
                r = tag.rpath
                rpath = r.decode() if isinstance(r, bytes) else r
            elif t == "DT_RUNPATH":
                r = tag.runpath
                runpath = r.decode() if isinstance(r, bytes) else r
        return needed, rpath, runpath


def _expand_origin_paths(raw, origin):
    """Expand $ORIGIN variables inside RPATH/RUNPATH entries."""
    if not raw:
        return []
    out = []
    for entry in raw.split(":"):
        out.append(entry.replace("$ORIGIN", str(origin)).replace("${ORIGIN}", str(origin)))
    return out


def _elf_search_paths(binary_path, appdir_path, rpath, runpath, extra=None):
    """Construct a list of library search paths for an ELF binary."""
    origin = Path(binary_path).parent.resolve()
    paths = []
    env = os.environ.get("LD_LIBRARY_PATH")
    if env:
        paths.extend([p for p in env.split(":") if p])
    paths.extend(_expand_origin_paths(runpath, origin))
    paths.extend(_expand_origin_paths(rpath, origin))
    if appdir_path:
        paths.extend([
            str(appdir_path / "usr/lib"),
            str(appdir_path / "usr/lib64"),
            str(appdir_path / "usr/lib/x86_64-linux-gnu"),
            str(appdir_path / "usr/lib/aarch64-linux-gnu"),
            str(appdir_path / "lib"),
            str(appdir_path / "lib64"),
        ])
    if extra:
        paths.extend(extra)
    seen = set()
    uniq = []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def verify_elf_dependencies(binary, appdir):
    """Return detailed dependency resolution information for one ELF binary."""
    b = Path(binary).resolve()
    needed, rpath, runpath = _read_dynamic_elf(b)
    cpaths = _elf_search_paths(b, Path(appdir).resolve(), rpath, runpath)
    resolved = {}
    missing = []
    for soname in needed:
        hit = None
        for base in cpaths:
            cand = Path(base) / soname
            if cand.exists():
                hit = str(cand)
                break
        if hit:
            resolved[soname] = hit
        else:
            missing.append(soname)
    return {
        "binary": str(b),
        "needed": needed,
        "rpath": rpath,
        "runpath": runpath,
        "search_paths": cpaths,
        "resolved": resolved,
        "missing": missing
    }


def run_elf_checks(appdir):
    """Perform ELF dependency checks on all ELF binaries inside the AppDir."""
    results = []
    for root, _, files in os.walk(appdir):
        for file in files:
            full_path = Path(root) / file
            if is_elf(full_path):
                try:
                    results.append(verify_elf_dependencies(str(full_path), appdir))
                except Exception:
                    pass
    return results


def write_elf_report(appdir, details, report_path=None):
    """Write a textual report detailing ELF dependency issues."""
    if report_path is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = Path.home() / ".cache/nx-apphub-cli/reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"elf-check-{Path(appdir).name}-{ts}.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        for d in details:
            f.write(d["binary"] + "\n")
            if d["runpath"] is not None:
                f.write(f"  RUNPATH: {d['runpath']}\n")
            if d["rpath"] is not None:
                f.write(f"  RPATH:   {d['rpath']}\n")
            if d["needed"]:
                f.write(f"  NEEDED:  {', '.join(d['needed'])}\n")
            if d["missing"]:
                f.write(f"  MISSING: {', '.join(d['missing'])}\n")
            f.write("\n")
    return str(report_path)


def run_linter(args=None):
    """Entry point for running AppDir lint checks and reporting missing libraries."""
    if args is None:
        parser = argparse.ArgumentParser(description="Check missing shared libraries in an AppDir.")
        parser.add_argument("appdir", type=str, help="Path to the AppDir or squashfs-root directory")
        args = parser.parse_args()

    appdir_path = detect_appdir(args.appdir)

    # --- Handle uruntime symlink (squashfs-root -> AppDir).

    if appdir_path.is_symlink():
        resolved = appdir_path.resolve()
        print(f"ℹ️ squashfs-root is a symlink — resolved to: {resolved}")
        appdir_path = resolved

    if not is_valid_appdir(appdir_path):
        raise BuildError(f"Invalid or incomplete AppDir: {appdir_path}")

    print()
    print(f"🔍 Scanning AppDir: {appdir_path}\n")
    missing = find_missing_libs(appdir_path)

    details = run_elf_checks(appdir_path)
    any_missing = [d for d in details if d["missing"]]
    if any_missing:
        report_path = write_elf_report(appdir_path, any_missing)
        print(f"🧩 ELF dependency details: {report_path}\n")

    if not missing:
        print("✅ No missing shared libraries found.\n")
        return

    print("🚨 Missing shared libraries:\n")
    for lib, sources in sorted(missing.items()):
        print(f"{lib} — required by:")
        for src in sorted(set(sources)):
            print(f"  ↪ {src}")
        print()

    # -- Load YAML config to retrieve repositories.

    yaml_path = getattr(args, "yaml", None)
    if yaml_path and os.path.isfile(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        repos = config.get("buildinfo", {}).get("distrorepo", [])
        if isinstance(repos, dict):
            repos = repos.get("base", []) or []

        print("💡 Suggesting Debian packages that may provide the missing libraries...\n")
        suggestions = suggest_providing_packages(missing.keys(), repos)
        for lib in missing:
            pkgs = suggestions.get(lib)
            if pkgs:
                print(f"   ➤ {lib}: suggested packages → {', '.join(sorted(pkgs))}")
            else:
                print(f"   ➤ {lib}: no suggestion found")
        print()
