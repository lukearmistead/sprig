# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Sprig."""

block_cipher = None

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = os.path.join(SPECPATH, '..')

# Collect metadata for packages that use importlib.metadata
datas = []
datas += copy_metadata('genai_prices')
datas += copy_metadata('pydantic_ai')
datas += copy_metadata('pydantic_ai_slim')
datas += copy_metadata('anthropic')
datas += copy_metadata('pydantic')
datas += copy_metadata('ruamel.yaml')
datas += copy_metadata('sprig')

# Bundle config-template.yml and connect.html template
datas += [(os.path.join(ROOT, 'config-template.yml'), '.')]
datas += [(os.path.join(ROOT, 'sprig/templates/connect.html'), 'sprig/templates')]
datas += [(os.path.join(ROOT, 'sprig/prompts/categorize.txt'), 'sprig/prompts')]

a = Analysis(
    [os.path.join(ROOT, 'sprig/cli.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pydantic_ai',
        'anthropic',
    ] + collect_submodules('ruamel.yaml'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['logfire', 'logfire.integrations', 'logfire.integrations.pydantic'],
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
    name='sprig',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
