#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2025> <Uri Herrera <uri_herrera@nxos.org>>

from setuptools import setup, find_packages

# <---
# --->
setup(
    name="nx-apphub-cli",
    version="1.1.1",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pyyaml",
        "rich",
        "python-debian",
        "pyelftools",
    ],
    entry_points={
        "console_scripts": [
            "nx-apphub-cli=nx_apphub_cli.cli:main"
        ]
    },
    author="Uri Herrera",
    author_email="uri_herrera@nxos.org",
    description="NX AppHub CLI — Lightweight command-line tool for managing and building applications in Nitrux.",
    url="https://github.com/Nitrux/nx-apphub",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD 3 Clause License",
        "Operating System :: POSIX :: Linux"
    ],
    python_requires='>=3.6',
)
