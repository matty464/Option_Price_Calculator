# Building on macOS (`.app` or folder)

Streamlit runs as a **local server** plus your browser. PyInstaller bundles Python, dependencies, and `launcher.py` (same entry as `streamlit run Main.py`).

**Build on a Mac** for a Mac bundle. You cannot turn the Windows `.exe` into a Mac app; build separately on each OS.

## 1. Prerequisites

- macOS 12+ recommended  
- [Python 3.11+](https://www.python.org/downloads/) (3.11 or 3.12; match what you test)  
- Apple Silicon or Intel — PyInstaller targets the machine you build on (use a Rosetta terminal only if you intentionally build an Intel binary on Apple Silicon).

## 2. Virtual environment and dependencies

```bash
cd path/to/optionCalc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-build.txt
```

## 3. Build

**Option A — Double-clickable `.app` (recommended for sharing)**

```bash
pyinstaller optioncalc_mac.spec
```

Result: **`dist/OptionPriceCalculator.app`**. Zip the `.app` (or put it in a `.dmg`) for others. Recipients drag it to **Applications** (or run from Downloads).

**Option B — Folder + executable (no `.app` wrapper)**

```bash
pyinstaller optioncalc.spec
```

Result: **`dist/OptionPriceCalculator/`** containing the **`OptionPriceCalculator`** executable (no `.exe`). Run:

```bash
./dist/OptionPriceCalculator/OptionPriceCalculator
```

Or from Finder: open the folder and double-click **`OptionPriceCalculator`** (a Terminal window may appear because `console=True`).

## 4. Gatekeeper (unsigned apps)

Apple may block unsigned downloads. Recipients can:

- **Right-click** the app → **Open** → confirm **Open** the first time, or  
- Clear quarantine after unzip:

```bash
xattr -dr com.apple.quarantine /path/to/OptionPriceCalculator.app
```

For wide distribution, **Apple Developer** code signing + notarization is the proper fix (separate process).

## 5. First launch

Expect **30–60+ seconds** the first time while the bundle initializes. The app opens your default browser to `http://localhost:8501` (or the port in `OPTIONCALC_PORT` if set).

## 6. Run without building (development)

```bash
source .venv/bin/activate
streamlit run Main.py
# or
python launcher.py
```

## 7. If the build fails

- Upgrade: `pip install -U pyinstaller streamlit`  
- Add missing packages to the `collect_all` loop in the spec file if PyInstaller omits a dependency  
- Prefer **onedir** (these specs) over **onefile** for Streamlit  

See also **[BUILD_WINDOWS.md](BUILD_WINDOWS.md)** for the Windows bundle.
