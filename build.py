#!/usr/bin/env python3
"""
Build standalone IPAM2 executable
Usage: python3 build.py [--version VERSION]

Environment Variables:
  VERSION: Version string (e.g., 1.0.13)
"""

import PyInstaller.__main__
import os
import sys

# Determine the source script
SCRIPT = "ipam2.py"
NAME = "ipam2"

# Get version from argument or environment
VERSION = None
if len(sys.argv) > 1 and sys.argv[1] == "--version":
    if len(sys.argv) > 2:
        VERSION = sys.argv[2]
    else:
        print("❌ Error: --version requires a version string")
        sys.exit(1)
elif len(sys.argv) > 1:
    print(f"❌ Unknown argument: {sys.argv[1]}")
    print("Usage: python3 build.py [--version VERSION]")
    sys.exit(1)

# Check if source exists
if not os.path.exists(SCRIPT):
    print(f"❌ Error: {SCRIPT} not found!")
    sys.exit(1)

# Check if config exists (either in current dir or XDG location)
CONFIG_FILE = "config.yaml"
if not os.path.exists(CONFIG_FILE):
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    xdg_config_file = os.path.join(xdg_config, "ipam2", "config.yaml")
    if os.path.exists(xdg_config_file):
        CONFIG_FILE = xdg_config_file
    else:
        print(f"❌ Error: config.yaml not found!")
        sys.exit(1)

# Determine output name
OUTPUT_NAME = NAME if VERSION is None else f"{NAME}-v{VERSION}"

print(f"🔨 Building standalone executable for {SCRIPT}...")
print(f"📦 Version: {VERSION if VERSION else 'latest'}")
print(f"📁 Output: dist/{OUTPUT_NAME}")

# Build command
PyInstaller.__main__.run(
    [
        SCRIPT,
        "--onefile",  # Single EXE file
        "--name=" + OUTPUT_NAME,  # Output name
        f"--add-data={CONFIG_FILE}:.",  # Include config
        "--hidden-import=sqlalchemy.dialects.sqlite",
        "--hidden-import=sqlalchemy.dialects.postgresql",
        "--hidden-import=rich",
        "--hidden-import=rich.console",
        "--hidden-import=rich.table",
        "--hidden-import=rich.panel",
        "--hidden-import=rich.box",
        "--hidden-import=pandas",
        "--collect-all=sqlalchemy",
        "--collect-all=rich",
        "--collect-all=pandas",
        "--clean",  # Clean cache
        "--noconfirm",  # Overwrite output dir
    ]
)

print(f"✅ Build complete! Executable: dist/{OUTPUT_NAME}")
