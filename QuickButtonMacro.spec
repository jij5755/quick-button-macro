# -*- mode: python ; coding: utf-8 -*-
# 2026-08-25 onefile → onedir 전환: onefile은 실행마다 전체를 임시폴더(_MEI)에
# 풀고 백신이 재스캔해 시작이 수 초 걸렸다. onedir은 풀린 채로 배포돼 즉시 실행.
# 산출물: dist/QuickButtonMacro/QuickButtonMacro.exe (프리셋도 이 폴더 기준)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('constants.py', '.')],
    hiddenimports=[],
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
    name='QuickButtonMacro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
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
    name='QuickButtonMacro',
)
