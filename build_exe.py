"""
Build script for creating standalone .exe file using PyInstaller
Run with: python build_exe.py
"""

import PyInstaller.__main__
import os
import shutil

# Clean previous builds
if os.path.exists("build"):
    shutil.rmtree("build")
if os.path.exists("dist"):
    shutil.rmtree("dist")

# PyInstaller command arguments
PyInstaller.__main__.run(
    [
        "App.py",
        "--name=AnimatorVsAnimationIRL",
        "--onefile",
        "--windowed",  # No console window
        "--icon=NONE",  # Add icon path if you have one
        # Add data files (assets)
        "--add-data=assets;assets",
        "--add-data=.env;.",
        # Hidden imports that might not be detected
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=pygame",
        "--hidden-import=numpy",
        "--hidden-import=mss",
        "--hidden-import=PIL",
        "--hidden-import=google.genai",
        "--hidden-import=elevenlabs",
        "--hidden-import=sounddevice",
        "--hidden-import=speech_recognition",
        # Exclude unnecessary packages to reduce size
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        # Optimize
        "--strip",
        "--noupx",
    ]
)

print("\n" + "=" * 60)
print("Build complete! Executable is in the 'dist' folder")
print("=" * 60)
