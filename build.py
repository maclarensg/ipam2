#!/usr/bin/env python3
"""
Build standalone IPAM2 executable
Usage: python3 build.py
"""

import PyInstaller.__main__
import os
import sys

# Determine the source script
SCRIPT = "ipam2.py"
NAME = "ipam2"
CONFIG_FILE = "config.yaml"

# Check if source exists
if not os.path.exists(SCRIPT):
    print(f"❌ Error: {SCRIPT} not found!")
    sys.exit(1)

# Check if config exists
if not os.path.exists(CONFIG_FILE):
    print(f"❌ Error: {CONFIG_FILE} not found!")
    sys.exit(1)

print(f"🔨 Building standalone executable for {SCRIPT}...")

# Build command
PyInstaller.__main__.run(
    [
        SCRIPT,
        "--onefile",  # Single EXE file
        "--name=" + NAME,  # Output name
        f"--add-data={CONFIG_FILE}:.",  # Include config
        "--hidden-import=sqlalchemy.dialects.sqlite",
        "--hidden-import=sqlalchemy.dialects.postgresql",
        "--hidden-import=rich",
        "--hidden-import=rich.console",
        "--hidden-import=rich.table",
        "--hidden-import=rich.panel",
        "--hidden-import=rich.box",
        "--collect-all=sqlalchemy",
        "--collect-all=rich",
        "--clean",  # Clean cache
        "--noconfirm",  # Overwrite output dir
    ]
)

print(f"✅ Build complete! Executable: dist/{NAME}")
