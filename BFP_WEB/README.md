# Browser Forensics Pro v2.3 — pywebview Desktop App

## What this is
A **native desktop application** using pywebview — NOT a web app.
- `main.py` creates a native OS window (EdgeWebView2 on Windows, WebKit on macOS/Linux)
- `ui.html` is the UI rendered inside that window
- JavaScript calls Python directly via `window.pywebview.api.*` — no HTTP server, no browser, no ports

## Setup
```
pip install -r requirements.txt
```

## Run
```
python main.py
```

## Build EXE (when ready)
```
python build_exe.py
```
Output: `dist/BrowserForensicsPro.exe`

## Project structure
```
main.py          ← pywebview entry point + ForensicsAPI (Python↔JS bridge)
ui.html          ← full UI, calls window.pywebview.api.*
build_exe.py     ← PyInstaller build script
modules/         ← 15 forensic extraction modules
utils/           ← browser detection, forensic copy, timestamp utils
acquisition/     ← live capture, forensic image support
config.py        ← app config
```

## How the bridge works
JavaScript → Python:
```js
const r = await window.pywebview.api.get_data('history', 1, 300, '');
```
Python (main.py):
```python
class ForensicsAPI:
    def get_data(self, module, page, per, search):
        ...
        return {"rows": [...], "total": N}
```
