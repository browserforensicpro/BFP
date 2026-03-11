"""
Build script — packages BFP into a standalone EXE using PyInstaller.
Run:  python build_exe.py
"""
import os, sys, subprocess

app_name   = "BrowserForensicsPro"
main_file  = "main.py"
ui_file    = "ui.html"
icon_file  = "icon.ico"      # optional — skip if missing

base_dir   = os.path.dirname(os.path.abspath(__file__))
ui_path    = os.path.join(base_dir, ui_file)
icon_path  = os.path.join(base_dir, icon_file)

hidden_imports = [
    "webview", "webview.platforms.winforms", "webview.platforms.gtk",
    "webview.platforms.cocoa", "webview.platforms.edgechromium",
    "modules.history", "modules.downloads", "modules.cookies",
    "modules.bookmarks", "modules.logins", "modules.formhistory",
    "modules.searches", "modules.cache", "modules.thumbnails",
    "modules.sitesettings", "modules.sitestorage", "modules.sessions",
    "modules.timeline", "modules.categorizer", "modules.vssrecovery",
    "modules.reportbuilder",
    "utils.browserdetector", "utils.cacherebuilder",
    "utils.forensiccopy", "utils.sessionanalyzer", "utils.timeutils",
    "acquisition.livecapture", "acquisition.mountedimage",
    "reportlab", "reportlab.lib", "reportlab.platypus",
    "openpyxl", "PIL", "PIL.Image",
]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    f"--name={app_name}",
    f"--add-data={ui_path}{os.pathsep}.",
    "--collect-all=webview",
    "--noconfirm",
]
if os.path.isfile(icon_path):
    cmd += [f"--icon={icon_path}"]
for h in hidden_imports:
    cmd += [f"--hidden-import={h}"]
cmd.append(main_file)

print(f"Building {app_name}…")
subprocess.run(cmd, check=True)
print(f"\n✓ Done. Output: dist/{app_name}.exe")
