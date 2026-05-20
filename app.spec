# -*- mode: python ; coding: utf-8 -*-
"""
Arquivo de especificação do PyInstaller para o aplicativo RPA
Este arquivo define como o PyInstaller deve compilar o app.py para .exe

Uso:
    pyinstaller app.spec
"""

import sys
from pathlib import Path

# Detecta o diretório base do projeto
base_dir = Path(__file__).parent

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[str(base_dir)],
    binaries=[],
    datas=[
        (str(base_dir / 'templates'), 'templates'),
    ],
    hiddenimports=[
        'win32com',
        'win32con',
        'win32gui',
        'webview',
        'flask',
        'reportlab',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir='C:\\Temp',  # Usar tmp sem espaços para evitar erro de DLL em caminhos com espaços
    console=False,  # Oculta a janela do prompt de comando (--windowed)
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Pode adicionar icon='icon.ico' se tiver
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app'  # Nome da pasta de saída (--onedir)
)
