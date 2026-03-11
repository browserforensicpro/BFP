# -*- mode: python ; coding: utf-8 -*-
# BrowserForensicsPro.spec — Windows x64, edgechromium backend
# Correctly bundles pythonnet + clr_loader required by pywebview edgechromium

from PyInstaller.utils.hooks import collect_all

# ── Collect webview package (all files) ────────────────────────────────────────
wv_datas, wv_binaries, wv_himports = collect_all('webview')

# Only filter out non-Windows GUI toolkits (gtk, cocoa, qt) —
# Do NOT filter winforms because edgechromium uses the WinForms host!
wv_datas    = [(s, d) for s, d in wv_datas
               if not any(x in s.lower() for x in ['gtk', 'cocoa', '/qt/', '\\qt\\'])]
wv_binaries = [(s, d) for s, d in wv_binaries
               if not any(x in s.lower() for x in ['gtk', 'cocoa', '/qt/', '\\qt\\'])]
wv_himports = [h for h in wv_himports
               if not any(x in h.lower() for x in ['gtk', 'cocoa', '.qt'])]

# ── Collect pythonnet (required by pywebview edgechromium on Windows) ──────────
pn_datas, pn_binaries, pn_himports = collect_all('pythonnet')
cl_datas, cl_binaries, cl_himports = collect_all('clr_loader')

datas = [('ui.html', '.')]
datas    += wv_datas + pn_datas + cl_datas
binaries  = wv_binaries + pn_binaries + cl_binaries

hiddenimports = [
    # ── webview (Windows edgechromium backend) ────────────────────────────────
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',   # edgechromium host is WinForms-based
    # ── pythonnet / CLR bridge ────────────────────────────────────────────────
    'pythonnet',
    'clr',
    'clr_loader',
    'clr_loader.ffi',
    'clr_loader.ffi.dlls',
    # ── BFP application modules ───────────────────────────────────────────────
    'modules.history',    'modules.downloads',  'modules.cookies',
    'modules.bookmarks',  'modules.logins',     'modules.formhistory',
    'modules.searches',   'modules.cache',      'modules.thumbnails',
    'modules.sitesettings', 'modules.sitestorage', 'modules.sessions',
    'modules.timeline',   'modules.categorizer', 'modules.vssrecovery',
    'modules.reportbuilder',
    # ── BFP utilities ─────────────────────────────────────────────────────────
    'utils.browserdetector', 'utils.cacherebuilder',
    'utils.forensiccopy',    'utils.sessionanalyzer', 'utils.timeutils',
    # ── acquisition ──────────────────────────────────────────────────────────
    'acquisition.livecapture', 'acquisition.mountedimage',
    # ── third-party ───────────────────────────────────────────────────────────
    'reportlab', 'reportlab.lib', 'reportlab.platypus',
    'openpyxl',
    'PIL', 'PIL.Image',
    'Crypto',
] + wv_himports + pn_himports + cl_himports

# ── Strip modules that are definitely not needed ───────────────────────────────
excludes = [
    # Non-Windows webview backends
    'webview.platforms.gtk',
    'webview.platforms.cocoa',
    'webview.platforms.qt',
    # Unused stdlib
    'tkinter', '_tkinter',
    'unittest', 'test', 'distutils',
    'xmlrpc', 'ftplib', 'imaplib', 'poplib', 'smtplib', 'telnetlib',
    'turtle', 'turtledemo',
    # Scientific / data science stack
    'numpy', 'scipy', 'matplotlib', 'pandas',
    # IPython / Jupyter
    'IPython', 'jupyter',
    # Qt bindings
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    # Alternative crypto (we use pycryptodome)
    'nacl',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_webview_patch.py'],
    excludes=excludes,
    noarchive=False,
    optimize=1,   # strip docstrings safely (optimize=2 can break some introspection)
)

pyz = PYZ(a.pure, optimize=1)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BrowserForensicsPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='bfp_icon.ico',
    version='version_info.txt',
)
