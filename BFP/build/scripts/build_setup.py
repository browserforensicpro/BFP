"""
build_setup.py — Browser Forensics Pro Complete Build Script
============================================================
Run this script from the BFP project root directory:

    python build_setup.py

What it does:
  1. Checks and installs all required build tools
  2. Downloads UPX (ultra compression) automatically
  3. Creates the app icon (.ico) if not present
  4. Builds the standalone .exe via PyInstaller
  5. Verifies the output size
  6. Optionally builds the Inno Setup installer

Requirements:
  pip install pyinstaller pywebview pycryptodome Pillow
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
import struct
import platform

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
APP_NAME    = "BrowserForensicsPro"
APP_VERSION = "1.0.0"
SPEC_FILE   = "BrowserForensicsPro.spec"
ICON_FILE   = "assets/bfp_icon.ico"
DIST_DIR    = "dist"
BUILD_DIR   = "build_temp"

# UPX download URL (Windows 64-bit) — check https://github.com/upx/upx/releases for latest
UPX_URL  = "https://github.com/upx/upx/releases/download/v4.2.2/upx-4.2.2-win64.zip"
UPX_DIR  = "upx"

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}"); sys.exit(1)

def run(cmd, check=True):
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()}")
    if result.returncode != 0 and check:
        print(f"    STDERR: {result.stderr.strip()}")
        err(f"Command failed: {cmd}")
    return result

def human_size(path):
    size = os.path.getsize(path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — ENVIRONMENT CHECK
# ══════════════════════════════════════════════════════════════════════════════
step("Step 1: Environment Check")

if platform.system() != "Windows":
    warn("This build script is designed for Windows (targets Windows .exe)")
    warn("You can still run it on Windows only. Cross-compilation is not supported.")

if sys.version_info < (3, 9):
    err(f"Python 3.9+ required. Found: {sys.version}")
ok(f"Python {sys.version.split()[0]}")

# Check we're in the right directory
if not os.path.isfile("main.py"):
    err("Run this script from the BFP project root (where main.py lives)")
ok("Running from project root")

# Check required files
required = ["main.py", "ui.html", "config.py", SPEC_FILE, "version_info.txt"]
for f in required:
    if not os.path.isfile(f):
        err(f"Missing required file: {f}")
    ok(f"Found {f}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — INSTALL PYTHON DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════
step("Step 2: Installing Python Build Dependencies")

packages = [
    "pyinstaller",
    "pywebview",
    "pycryptodome",
    "Pillow",
]

for pkg in packages:
    result = run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", pkg], check=False)
    if result.returncode == 0:
        ok(f"Installed/verified: {pkg}")
    else:
        warn(f"Could not install {pkg} — continuing anyway")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — DOWNLOAD UPX (compression tool)
# ══════════════════════════════════════════════════════════════════════════════
step("Step 3: Setting Up UPX Compression")

upx_exe = os.path.join(UPX_DIR, "upx.exe")
if os.path.isfile(upx_exe):
    ok(f"UPX already present at {upx_exe}")
else:
    print(f"  Downloading UPX from {UPX_URL} ...")
    try:
        zip_path = "upx_download.zip"
        urllib.request.urlretrieve(UPX_URL, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Find upx.exe inside the zip
            for member in zf.namelist():
                if member.endswith("upx.exe"):
                    os.makedirs(UPX_DIR, exist_ok=True)
                    with zf.open(member) as src, open(upx_exe, 'wb') as dst:
                        dst.write(src.read())
                    ok(f"UPX extracted to {upx_exe}")
                    break
        os.remove(zip_path)
    except Exception as e:
        warn(f"UPX download failed: {e}")
        warn("Build will continue WITHOUT UPX compression (larger output)")
        upx_exe = None

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — CREATE APP ICON
# ══════════════════════════════════════════════════════════════════════════════
step("Step 4: Creating Application Icon")

os.makedirs("assets", exist_ok=True)

if os.path.isfile(ICON_FILE):
    ok(f"Icon already exists: {ICON_FILE}")
else:
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # Create a clean forensic-style icon
        sizes = [256, 128, 64, 48, 32, 16]
        images = []

        for size in sizes:
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Dark navy background circle
            margin = max(2, size // 16)
            draw.ellipse([margin, margin, size-margin, size-margin],
                         fill=(14, 30, 64, 255),
                         outline=(41, 128, 185, 255),
                         width=max(1, size // 32))

            # Magnifying glass shape
            cx, cy = size // 2, int(size * 0.42)
            r = int(size * 0.22)
            ring = max(1, size // 20)
            draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                         outline=(41, 196, 255, 255), width=ring)

            # Handle
            hx1 = int(cx + r * 0.7)
            hy1 = int(cy + r * 0.7)
            hx2 = int(cx + r * 1.6)
            hy2 = int(cy + r * 1.6)
            draw.line([hx1, hy1, hx2, hy2],
                      fill=(41, 196, 255, 255), width=max(1, ring))

            images.append(img)

        # Save as .ico with all sizes
        images[0].save(
            ICON_FILE,
            format='ICO',
            sizes=[(s, s) for s in sizes],
            append_images=images[1:]
        )
        ok(f"Icon created: {ICON_FILE}")
    except ImportError:
        warn("Pillow not available — skipping icon creation")
        # Update spec to not use icon if not present
    except Exception as e:
        warn(f"Icon creation failed: {e} — continuing without icon")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — CLEAN PREVIOUS BUILD
# ══════════════════════════════════════════════════════════════════════════════
step("Step 5: Cleaning Previous Build Artifacts")

for d in [DIST_DIR, BUILD_DIR, "__pycache__"]:
    if os.path.isdir(d):
        shutil.rmtree(d)
        ok(f"Removed: {d}")

# Remove .pyc files
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ['.git', 'venv', '.venv', UPX_DIR]]
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))

ok("Clean complete")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — BUILD EXE WITH PYINSTALLER
# ══════════════════════════════════════════════════════════════════════════════
step("Step 6: Building EXE with PyInstaller")

cmd = [
    sys.executable, "-m", "PyInstaller",
    SPEC_FILE,
    "--distpath", DIST_DIR,
    "--workpath", BUILD_DIR,
    "--noconfirm",
    "--clean",
    "--log-level", "WARN",
]

if upx_exe and os.path.isfile(upx_exe):
    cmd += ["--upx-dir", UPX_DIR]
    ok("UPX compression ENABLED")
else:
    warn("UPX compression DISABLED — output will be larger")

print()
run(cmd)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — VERIFY OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
step("Step 7: Verifying Output")

exe_path = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
if not os.path.isfile(exe_path):
    err(f"Build failed — expected output not found: {exe_path}")

size = human_size(exe_path)
ok(f"EXE created: {exe_path}")
ok(f"File size:   {size}")
ok("Build SUCCESSFUL!")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — BUILD INNO SETUP INSTALLER (optional)
# ══════════════════════════════════════════════════════════════════════════════
step("Step 8: Building Inno Setup Installer (.exe setup)")

inno_script = "installer.iss"
inno_compiler = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not os.path.isfile(inno_script):
    warn(f"Inno Setup script not found: {inno_script}")
    warn("Skipping installer build. See installer.iss for setup script.")
elif not os.path.isfile(inno_compiler):
    warn("Inno Setup 6 not installed. Download from: https://jrsoftware.org/isinfo.php")
    warn("Then run: ISCC.exe installer.iss")
else:
    run([inno_compiler, inno_script])
    installer_path = os.path.join("installer_output", f"{APP_NAME}_v{APP_VERSION}_Setup.exe")
    if os.path.isfile(installer_path):
        ok(f"Installer created: {installer_path}")
        ok(f"Installer size:    {human_size(installer_path)}")
    else:
        warn("Installer file not found — check Inno Setup output directory")

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════
print(f"""
{'='*60}
  BUILD COMPLETE
{'='*60}
  EXE:       {exe_path}
  
  To create installer:
    1. Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    2. Open installer.iss in Inno Setup Compiler
    3. Press F9 or click Build → Compile
    4. Find setup .exe in: installer_output/

  To run directly (no install):
    dist\\BrowserForensicsPro.exe
{'='*60}
""")
