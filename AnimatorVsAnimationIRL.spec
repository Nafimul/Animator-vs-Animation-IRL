# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['App.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('.env', '.')],
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'pygame', 'numpy', 'mss', 'PIL', 'google.genai', 'elevenlabs', 'sounddevice', 'speech_recognition'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AnimatorVsAnimationIRL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
