# Building a Windows `.exe` (folder) for distribution

Streamlit is a **local web server** + browser UI. PyInstaller produces a **`dist/OptionPriceCalculator/` folder** containing `OptionPriceCalculator.exe` and an `_internal` directory. Distribute the **whole folder** (or zip it) — the `.exe` alone is not enough.

> **Build on a Windows PC.** PyInstaller does not reliably cross-compile Windows `.exe` from macOS/Linux.

## 1. Prerequisites

- Windows 10/11, 64-bit  
- [Python 3.11+](https://www.python.org/downloads/) (3.11 or 3.12 recommended; match what you tested)

## 2. Project venv and deps

```powershell
cd path\to\optionCalc
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
```

## 3. Build

```powershell
pyinstaller optioncalc.spec
```

Result:

- `dist\OptionPriceCalculator\OptionPriceCalculator.exe` — launcher (opens browser to the app)  
- `dist\OptionPriceCalculator\_internal\` — bundled Python, Streamlit, your scripts  

First run may take **30–60+ seconds**. Windows **SmartScreen** may warn on unsigned builds; code signing reduces that.

## 4. Optional: hide console window

In `optioncalc.spec`, change `console=True` to `console=False` under `EXE(...)`. Errors will be harder to debug; use only when stable.

## 5. If the build fails

- Try upgrading: `pip install -U pyinstaller streamlit`  
- Add missing packages to the `collect_all` loop in `optioncalc.spec` if PyInstaller omits a dependency  
- Prefer **onedir** (this spec) over **onefile** for Streamlit — onefile is slower and more fragile  

## 6. Run without building (dev)

```powershell
python launcher.py
```

Same as `streamlit run Main.py`, but matches the frozen entry point.

## 7. macOS

Windows `.exe` files do not run on Mac. For a native Mac bundle, build on macOS — see **[BUILD_MAC.md](BUILD_MAC.md)**.
