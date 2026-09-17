# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Beschreibung fuer die Windows-.exe.

Die .exe laeuft ohne Installation und ohne Adminrechte (GDD 15). Die
Konfigurationsdateien werden mitgepackt und zur Laufzeit ueber
``sys._MEIPASS`` gefunden (siehe rennmanager.konfiguration).
"""

analyse = Analysis(
    ["rennmanager/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[("konfiguration", "konfiguration")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # Nicht benoetigte Qt-Module weglassen, damit die .exe klein bleibt.
    excludes=[
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(analyse.pure)

exe = EXE(
    pyz,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="Rennmanager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Eine einzelne Datei ohne Konsolenfenster
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
