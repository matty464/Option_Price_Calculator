# PyInstaller spec for Option Price Calculator (Windows .exe folder distribution).
# Build on Windows:  pyinstaller optioncalc.spec
# Output: dist/OptionPriceCalculator/OptionPriceCalculator.exe  (+ _internal folder — zip the whole folder for customers)

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
