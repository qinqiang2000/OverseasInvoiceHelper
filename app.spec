# -*- mode: python ; coding: utf-8 -*-

SETUP_DIR = r'.'
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[(SETUP_DIR+'/static', 'static'), (SETUP_DIR+'/templates', 'templates'), ('.env', '.')],
    # 指定包engineio.async_drivers.threading
    hiddenimports=['gevent','geventwebsocket','gevent.ssl', 'gevent.builtins','engineio.async_drivers.threading','engineio.async_drivers', 'engineio','socketio', 'flask_socketio'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='app',
)
