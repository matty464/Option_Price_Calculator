# PyInstaller spec for Option Price Calculator — macOS (.app bundle).
# Build on macOS:  pyinstaller optioncalc_mac.spec
# Output: dist/OptionPriceCalculator.app  (zip or copy the .app for distribution)
#
# Folder-only build (Terminal): same Analysis as optioncalc.spec — use
#   pyinstaller optioncalc.spec
# then run:  ./dist/OptionPriceCalculator/OptionPriceCalculator

from PyInstaller.utils.hooks import collect_all

datas = [
    ("Main.py", "."),
    ("black_scholes.py", "."),
    ("iv_solve.py", "."),
    ("market_data.py", "."),
]
binaries = []
hiddenimports: list[str] = []

for pkg in (
    "streamlit",
    "altair",
    "pyarrow",
    "tornado",
    "watchdog",
    "jsonschema",
    "pydeck",
):
    try:
        ds, bs, hi = collect_all(pkg)
        datas += ds
        binaries += bs
        hiddenimports += hi
    except Exception:
        pass

hiddenimports += [
    "streamlit.web.bootstrap",
    "streamlit.web.server",
    "pandas",
    "numpy",
    "plotly",
    "yfinance",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="OptionPriceCalculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OptionPriceCalculator",
)

app = BUNDLE(
    coll,
    name="OptionPriceCalculator.app",
    bundle_identifier="com.optionpricecalculator.app",
    info_plist={
        "CFBundleName": "Option Price Calculator",
        "CFBundleDisplayName": "Option Price Calculator",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
