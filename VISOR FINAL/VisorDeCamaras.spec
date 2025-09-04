# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['visor_camaras7.py'],
    pathex=[],
    binaries=[],
    datas=[
    ('/home/salvador/Documentos/ProyectoCamaras/.venv/lib/python3.12/site-packages/cv2', 'cv2'),
    ('/home/salvador/Documentos/ProyectoCamaras/.venv/lib/python3.12/site-packages/PIL', 'PIL'),
],

    hiddenimports=['cv2', 'sv_ttk', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VisorDeCamaras',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VisorDeCamaras',
)
