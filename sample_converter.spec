# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Build datas dynamically per-platform
datas = [('options.json', '.')]
if sys.platform == 'win32':
    # Bundle ffmpeg only on Windows, where we ship redistributables in repo
    ff_bin_glob = 'redistributables/ffmpeg/bin/*'
    ff_license = 'redistributables/ffmpeg/LICENSE'
    if os.path.exists('redistributables/ffmpeg'):
        if os.path.isdir('redistributables/ffmpeg/bin'):
            datas.append((ff_bin_glob, 'redistributables/ffmpeg/bin'))
        if os.path.isfile(ff_license):
            datas.append((ff_license, 'redistributables/ffmpeg'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],  # binaries added in COLLECT
        [],  # zipfiles added in COLLECT
        [],  # datas added in COLLECT
        [],
        name='SampleConverter',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # windowed app, no console
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,  # set to a .icns if you add one
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='SampleConverter',
    )
    app = BUNDLE(
        coll,
        name='SampleConverter.app',
        icon=None,  # set to .icns to brand the app
        bundle_identifier=None,
        info_plist=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='SampleConverter',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,  # keep console on Windows; change to False to hide
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
