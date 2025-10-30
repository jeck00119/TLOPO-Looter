#!/usr/bin/env python3
"""
TLOPO Looter - Build Script
Creates a single executable with all assets using PyInstaller
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print()
    print("=" * 60)
    print(f"   {text}")
    print("=" * 60)
    print()


def print_step(step, total, text):
    """Print step progress"""
    print(f"[{step}/{total}] {text}")


def check_pyinstaller():
    """Check if PyInstaller is installed, install if not"""
    try:
        import PyInstaller
        return True
    except ImportError:
        print("[WARNING] PyInstaller is not installed!")
        print()
        response = input("Would you like to install PyInstaller now? (y/n): ")
        if response.lower() == 'y':
            print("Installing PyInstaller...")
            result = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
            if result.returncode != 0:
                print("[ERROR] Failed to install PyInstaller")
                return False
            print("PyInstaller installed successfully!")
            return True
        else:
            print("[ERROR] PyInstaller is required to build the executable")
            print("Install it with: pip install pyinstaller")
            return False


def clean_build_folders():
    """Remove old build and dist folders"""
    folders = ["build", "dist"]
    for folder in folders:
        if os.path.exists(folder):
            print(f"      Removing {folder}/")
            shutil.rmtree(folder)
    print("      Done!")
    print()


def build_executable():
    """Run PyInstaller with the spec file"""
    print("      This may take a few minutes...")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "main_gui.spec", "--clean"],
        capture_output=False
    )

    if result.returncode != 0:
        print()
        print("[ERROR] Build failed!")
        return False

    print()
    return True


def verify_build():
    """Verify the executable was created"""
    exe_path = Path("dist/TLOPO_Looter.exe")

    if not exe_path.exists():
        print("[ERROR] Executable not found in dist folder!")
        return False, None

    # Get file size
    size_bytes = exe_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    print("      Build successful!")
    print()

    return True, size_mb


def print_summary(size_mb):
    """Print build summary"""
    print_header("Build Summary")
    print(f"  Output:  dist\\TLOPO_Looter.exe")
    print(f"  Size:    {size_mb:.2f} MB")
    print()
    print("  The executable includes:")
    print("    - All Python code")
    print("    - img folder (templates + GIFs)")
    print("    - icon.ico")
    print("    - All dependencies (PyQt5, OpenCV, etc.)")
    print()
    print("  You can now distribute TLOPO_Looter.exe")
    print("  as a standalone application!")
    print("=" * 60)
    print()


def main():
    """Main build process"""
    print_header("TLOPO Looter - Build Script")

    # Check PyInstaller
    if not check_pyinstaller():
        return 1

    # Step 1: Clean old builds
    print_step(1, 4, "Cleaning old build files...")
    clean_build_folders()

    # Step 2: Build executable
    print_step(2, 4, "Building executable with PyInstaller...")
    if not build_executable():
        return 1

    # Step 3: Verify build
    print_step(3, 4, "Verifying build...")
    success, size_mb = verify_build()
    if not success:
        return 1

    # Step 4: Complete
    print_step(4, 4, "Build complete!")
    print()

    # Print summary
    print_summary(size_mb)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print()
        print("[CANCELLED] Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)
