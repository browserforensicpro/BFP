"""
Browser Forensics Pro - Configuration  v1.0
"""
import os, sys, tempfile

APP_NAME    = "Browser Forensics Pro"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Forensic Intelligence Suite"
APP_BUILD   = "2026.02.23"
APP_LICENSE = "MIT"

# ─── Temp / Paths ────────────────────────────────────────────────────
TEMP_DIR = os.path.join(tempfile.gettempdir(), "BrowserForensicsPro")
os.makedirs(TEMP_DIR, exist_ok=True)

# ─── Browser Profile Paths (Windows) ─────────────────────────────────
BROWSER_PATHS = {
    "Chrome":  [os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")],
    "Edge":    [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")],
    "Brave":   [os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data")],
    "Opera":   [os.path.expandvars(r"%APPDATA%\Opera Software\Opera Stable")],
    "Vivaldi": [os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\User Data")],
    "Firefox": [os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")],
}

# ─── URL Category Keywords ────────────────────────────────────────────
URL_CATEGORIES = {
    "Social Media":  ["facebook","twitter","instagram","linkedin","tiktok","reddit",
                      "snapchat","pinterest","discord","telegram","whatsapp","threads"],
    "Webmail":       ["gmail","mail.google","outlook","yahoo.com/mail","protonmail",
                      "hotmail","mail.yahoo","aol.com/mail"],
    "File Hosting":  ["drive.google","dropbox","onedrive","mega.nz","mediafire",
                      "wetransfer","box.com","4shared"],
    "Adult":         ["pornhub","xvideos","xhamster","onlyfans","redtube","youporn"],
    "Malware":       ["malware","phishing","exploit","ransomware","trojan","botnet",
                      "darkweb",".onion"],
    "Local Files":   ["file:///","localhost","127.0.0.1","192.168."],
}

# Legacy compat
COLOR_BG="#0f172a"; COLOR_PANEL="#1e293b"; COLOR_ACCENT="#00bfff"
COLOR_ACCENT2="#0080ff"; COLOR_TEXT="#e2e8f0"; COLOR_SUCCESS="#22c55e"
COLOR_WARNING="#f59e0b"; COLOR_DANGER="#ef4444"; COLOR_BORDER="#334155"
FONT_MAIN=("Segoe UI",10); FONT_MONO=("Consolas",9)
