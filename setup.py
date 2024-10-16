# setup.py

from setuptools import setup, find_packages

setup(
    name='nx_apphub',
    version='1.0.0',
    description='NX Applications Hub — Locally built AppImages for Nitrux',
    author='Uri Herrera',
    author_email='uri_herrera@nxos.org',
    license='BSD-3-Clause',
    packages=find_packages(),
    install_requires=[
        'PyYAML',
    ],
    entry_points={
        'console_scripts': [
            'nx-apphub-cli=nx_apphub.main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
    ],
)
