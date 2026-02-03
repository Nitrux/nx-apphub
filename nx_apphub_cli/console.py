#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright <2026> <Uri Herrera <uri_herrera@nxos.org>>

"""Console output utilities using Rich library for proper formatting."""

from rich.console import Console
from rich.theme import Theme

# Custom theme for nx-apphub-cli
custom_theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "header": "bold cyan",
})

# Global console instance
console = Console(theme=custom_theme)


def print_header(text):
    """Print a header message."""
    console.print(f"\n[ {text} ]\n")


def print_success(text, prefix="✅"):
    """Print a success message."""
    console.print(f"{prefix} {text}", style="success")


def print_error(text, prefix="❌"):
    """Print an error message."""
    console.print(f"{prefix} {text}", style="error")


def print_warning(text, prefix="🚨"):
    """Print a warning message."""
    console.print(f"{prefix} {text}", style="warning")


def print_info(text, prefix="ℹ️"):
    """Print an info message."""
    console.print(f"{prefix} {text}", style="info")


def print_message(text):
    """Print a plain message."""
    console.print(text)


def print_blank():
    """Print a blank line."""
    console.print()


def print_section(title, items, style="success"):
    """Print a section with a title and list of items."""
    console.print(f"\n{title}\n", style=style)
    for item in items:
        console.print(item)
