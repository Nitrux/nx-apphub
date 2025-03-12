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

from setuptools import setup, find_packages

setup(
    name="nx-apphub-cli",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pyyaml"
    ],
    entry_points={
        "console_scripts": [
            "nx-apphub-cli=nx_apphub_cli.cli:main"
        ]
    },
    author="Uri Herrera",
    author_email="uri_herrera@nxos.org",
    description="NX AppHub CLI is a lightweight command-line tool for managing and building applications in Nitrux as AppImages.",
    url="https://github.com/Nitrux/nx-apphub",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD 3 Clause License",
        "Operating System :: POSIX :: Linux"
    ],
    python_requires='>=3.6',
)
