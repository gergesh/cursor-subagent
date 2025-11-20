#!/usr/bin/env python3
"""
Custom setup.py to build the dylib during wheel creation.
"""
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
from setuptools.command.bdist_wheel import bdist_wheel


class BuildDylib(build_py):
    """Custom build command that compiles the dylib before building the package."""

    def run(self):
        """Compile the dylib and copy source file before running the standard build."""
        # Only compile on macOS
        if platform.system() != "Darwin":
            print("⚠️  Skipping dylib compilation (not on macOS)", file=sys.stderr)
            super().run()
            return

        print("🔨 Compiling dylib for agent isolation...")

        # Check for clang
        if not shutil.which("clang"):
            raise RuntimeError(
                "clang not found. Install with: xcode-select --install"
            )

        # Paths
        src_file = Path("cursor_subagent/redirect_interpose.c")
        output_dir = Path("cursor_subagent")
        output_file = output_dir / "libcursor_redirect.dylib"

        if not src_file.exists():
            raise RuntimeError(f"Source file not found: {src_file}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Compile command (universal binary for Intel and Apple Silicon)
        cmd = [
            "clang",
            "-arch", "x86_64",
            "-arch", "arm64e",
            "-dynamiclib",
            "-o", str(output_file),
            str(src_file),
            "-Wall",
            "-Wextra",
            "-O2",
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            # Code sign the dylib
            subprocess.run(
                ["codesign", "-s", "-", "-f", str(output_file)],
                check=True,
                capture_output=True,
                text=True
            )

            print(f"✅ Dylib compiled and signed: {output_file}")
        except subprocess.CalledProcessError as e:
            print("❌ Compilation failed:", file=sys.stderr)
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            raise RuntimeError("Failed to compile dylib") from e

        # Continue with standard build
        super().run()


class BdistWheelMacOS(bdist_wheel):
    """Custom wheel builder that creates platform-specific wheels."""

    def finalize_options(self):
        """Set the wheel to be platform-specific (macOS only)."""
        super().finalize_options()
        # Only build platform-specific wheels on macOS
        if platform.system() == "Darwin":
            self.plat_name_supplied = True
            # Use a compatible macOS platform tag (11.0 = Big Sur, first to support universal2)
            self.plat_name = "macosx_11_0_universal2"


if __name__ == "__main__":
    setup(
        packages=find_packages(),
        include_package_data=True,
        cmdclass={
            "build_py": BuildDylib,
            "bdist_wheel": BdistWheelMacOS,
        }
    )




