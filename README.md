# Browser Forensics Pro (BFP)

<p align="center">
  <img src="assets/logo.png" alt="Browser Forensics Pro" width="400"/>
</p>

<p align="center">
  <b>A powerful, read-only browser artifact forensic analysis tool for Windows</b><br/>
  Extract · Analyze · Investigate browser history, cookies, logins, cache, and more
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-blue?style=flat-square"/>
  <img src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows"/>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square"/>
  <img src="https://img.shields.io/badge/Mode-Read--Only-red?style=flat-square"/>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Supported Browsers](#supported-browsers)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Module Reference](#module-reference)
  - [Artifacts](#artifacts)
  - [Analysis](#analysis)
  - [Advanced](#advanced)
  - [Forensic Tools](#forensic-tools)
- [Settings](#settings)
- [Password Decryption](#password-decryption)
- [Exporting Data](#exporting-data)
- [Timezone Configuration](#timezone-configuration)
- [FAQ](#faq)
- [Building the Executable](#building-the-executable)
- [Project Structure](#project-structure)
- [License](#license)

---

## Overview

**Browser Forensics Pro (BFP)** is a Windows desktop application for forensic investigation of web browsers. It reads browser data files directly — never modifying them — and presents the data in a clean, searchable interface.

> ⚠️ **For lawful forensic investigation only.** You are solely responsible for compliance with all applicable laws when using this tool. Always obtain proper authorization before analyzing another person's browser data.

---

## Features

| Feature | Description |
|---------|-------------|
| 🔒 **Read-Only** | Never writes to browser files — forensic integrity guaranteed |
| 🌐 **Multi-Browser** | Chrome, Edge, Brave, Firefox — all profiles |
| 🕒 **Timezone Control** | View all timestamps in IST, UTC, PST, or any supported timezone |
| 🔑 **Password Recovery** | Decrypts Chrome/Edge/Brave passwords using Windows DPAPI + AES-256-GCM |
| 🔍 **Global Search** | Search a keyword across all modules simultaneously |
| ⚠️ **Download Risk Scanner** | Flags suspicious downloads by file type and keyword patterns |
| 🍪 **Active Sessions** | Shows active, expiring, and expired session cookies |
| 🕵️ **Incognito Detection** | Detects artifact-based evidence of private browsing |
| 📊 **Timeline** | Visual hourly/daily browsing activity charts |
| 🖼️ **Cache Images** | Browse and view cached images from the browser |
| 🗑️ **Cache Clearing** | Optional cache clearing with 3 modes (least used / old / all) |
| 📤 **Export** | Export any module data to CSV, JSON, or HTML report |

---

## Supported Browsers

| Browser | History | Cookies | Logins | Downloads | Cache | Sessions |
|---------|---------|---------|--------|-----------|-------|----------|
| Google Chrome | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Microsoft Edge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Brave Browser | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mozilla Firefox | ✅ | ✅ | ⚠️* | ✅ | ✅ | ✅ |

> *Firefox passwords are encrypted with NSS/key4.db (requires `nss3.dll` — not currently decrypted)

---

## Installation

### Requirements

- Windows 10 or 11 (64-bit)
- Python 3.9 or higher
- pip

### Step 1 — Clone the repository

```bash
git clone https://github.com/sharathkarnati/bfp.git
cd bfp
```

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

Core dependencies:
```
pywebview>=4.4
pycryptodome>=3.18
Pillow>=10.0
```

### Step 3 — Run

```bash
python main.py
```

---

## Running the App

1. Launch `main.py` (or the `.exe` if built)
2. Select a **Browser** from the top-left dropdown (Chrome, Edge, Brave, Firefox)
3. Select a **Profile** (e.g., "Default", "Person 1")
4. Click any module in the left sidebar to load its data
5. Use the **Search** bar in any module to filter results
6. Use **Export** tab to save data to CSV / JSON / HTML

---

## Module Reference

### Artifacts

#### 🌐 History
Displays the complete browser history — every URL visited with title, visit count, and timestamps.

- **Columns:** URL · Title · Visit Count · Last Visit (IST) · Last Visit Raw · Typed Count · Hidden
- **Tabs:** Data Table · Timeline · Session · Summary · Export
- **Features:** Paginated (300 rows/page) · Search · Click URL/Title to copy · Timeline charts

#### ⬇ Downloads
All files downloaded through the browser.

- **Columns:** Filename · URL · State · Size · Start Time · End Time · MIME Type · Danger Type
- **Features:** Double-click filename to open folder location

#### 🍪 Cookies
All stored browser cookies.

- **Columns:** Name · Host · Path · Value · Created · Expires · Secure · HttpOnly · SameSite
- **Note:** Cookie values are shown as-is; encrypted values show `[ENCRYPTED]`

#### 🔖 Bookmarks
Saved bookmarks / favorites (Chromium only — Firefox reading not supported).

- **Columns:** Name · URL · Date Added · Folder · Type

#### 🔑 Saved Logins
Usernames and passwords saved by the browser.

- **Columns:** Origin URL · Username · Password · Date Created · Date Last Used · Times Used
- **Chrome/Edge/Brave:** Passwords are **decrypted** using Windows DPAPI + AES-256-GCM (requires `pycryptodome`)
- **Firefox:** Shows `[ENCRYPTED — Firefox uses NSS/key4.db]`
- See [Password Decryption](#password-decryption) for details

#### 📝 Form History
Autofill data — text fields and address profiles.

- **Columns:** Field Name · Value · Use Count · Date Created · Date Last Used · Type

---

### Analysis

#### 🔍 Search Terms
Extracted search queries from history URLs (Google, Bing, YouTube, etc.)

- **Columns:** Query · Engine · URL · Date

#### 🖼️ Thumbnails
Session thumbnail files stored by the browser.

#### 📋 Sessions
Browser session files (open tabs/windows at time of last close).

- **Columns:** File · Size · Modified · Windows · Tabs · Format · Note
- **Features:** Chromium SNSS binary parsing · Firefox LZ4 JSON parsing

#### 🗄️ Cache Files
List of all browser cache files with sizes and timestamps.

- **Columns:** Filename · Size · Last Modified · Path
- **Clear Cache:** Three modes available:
  - *Least Used* — removes smallest/lowest-priority files
  - *Older Than 30 Days* — removes files not accessed recently
  - *⚠ Delete All* — wipes entire cache (irreversible)

---

### Advanced

#### ⚙ Site Settings
Stored browser permissions per origin (notifications, camera, location, etc.)

#### 💾 Site Storage
Local Storage and IndexedDB origins and sizes.

- **Columns:** Type · Origin · Key · Value · Size (KB/MB)

#### 🗑️ Deleted / WAL
SQLite WAL (Write-Ahead Log) analysis — may contain recently deleted rows from browser databases.

#### 📅 Timeline
Visual browsing activity charts.

- **Hourly chart:** Bar chart of visits per hour across the day
- **Daily chart:** Trend line of visits per day over past 30 days
- **Top Domains:** Most-visited domains by total visit count
- **Top Pages:** Most-visited individual pages

#### 🕵️ Incognito Detect
Artifact-based detection of private/incognito browsing evidence.

- Checks for: DNS pre-fetch anomalies, thumbnail gaps, session file patterns, cache inconsistencies
- **Note:** Cannot recover incognito history (Chrome/Edge delete it on window close)

#### 🖼️ Cache Images
Browseable gallery of images extracted from the browser cache.

- Click any thumbnail to view the full-size cached image

---

### Forensic Tools

#### 🔎 Global Search
Search a single keyword across **all modules** simultaneously.

- Searches: History · Downloads · Cookies · Logins · Bookmarks · Search Terms · Form History · Site Storage
- Results color-coded by module
- Max 500 results displayed

**How to use:**
1. Click *Forensic Tools → Global Search* in the sidebar
2. Type a keyword (e.g., `gmail`, `paypal`, `192.168`)
3. Click *🔎 Search All*

#### ⚠️ Download Risk Scanner
Analyzes download history for potentially malicious or suspicious files.

| Risk Level | Triggers |
|------------|----------|
| **HIGH** | Executable types: `.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.scr`, `.com`, `.dll` |
| **MEDIUM** | Suspicious names: `crack`, `keygen`, `hack`, `patch`, `serial`, `bypass`, `exploit` |
| **LOW** | Script types: `.js`, `.wsf`, `.jar`, `.apk`, `.sh`; interrupted downloads |

**How to use:**
1. Click *Forensic Tools → Download Risk Scan*
2. Click *🔍 Scan Downloads*

#### 🔐 Active Sessions
Shows session and authentication cookies grouped by expiry status.

| Status | Meaning |
|--------|---------|
| **Active** | Expires more than 7 days from now — valid session |
| **Expiring Soon** | Expires within 7 days — session still live but ending |
| **Expired** | Expiry date has passed |
| **Permanent** | No expiry set (session cookies — live until browser closes) |

**How to use:**
1. Click *Forensic Tools → Active Sessions*
2. Click *🔍 Scan Sessions*

---

## Settings

Access via: Sidebar → ⚙ Settings

| Setting | Description |
|---------|-------------|
| **Theme** | Dark (default) or Light mode |
| **Time Format** | 12-hour AM/PM or 24-hour |
| **Timezone** | IST (default), UTC, EST, PST, JST, and more |
| **Auto-Refresh** | Auto-load History when profile changes |
| **Data Retention** | Max days of history to load (0 = all) |
| **Log Level** | Python logging verbosity (INFO/DEBUG/WARNING/ERROR) |

> Settings are saved to `%APPDATA%\BFP\settings.json` and persist across sessions.

---

## Password Decryption

BFP can decrypt **Chrome, Edge, and Brave** saved passwords on Windows.

### How it works

Chrome 80+ encrypts passwords with **AES-256-GCM**. The encryption key is stored in the browser's `Local State` file, protected by Windows **DPAPI** (Data Protection API — tied to your Windows user account).

BFP:
1. Reads `Local State` → extracts the DPAPI-encrypted AES key
2. Calls `CryptUnprotectData` (Windows API) to decrypt the AES key
3. Uses the AES key to decrypt each password via AES-256-GCM

### Requirements

```bash
pip install pycryptodome
```

If `pycryptodome` is not installed, passwords show as `[ENCRYPTED — install pycryptodome]`.

### Limitations

- Only works on the **same Windows user account** that created the passwords
- Firefox uses NSS/key4.db (not currently supported)
- Older Chrome (< 80) uses raw DPAPI — also decrypted automatically

---

## Exporting Data

Any module's data can be exported using the **Export** tab:

1. Load any module (e.g., History, Cookies)
2. Click the **Export** tab
3. Choose format:
   - **CSV** — spreadsheet-compatible, all rows
   - **JSON** — machine-readable, all rows
   - **HTML Report** — formatted, printable report with BFP branding
4. Click Export — file saves to your Downloads folder

---

## Timezone Configuration

By default all timestamps are shown in **IST (UTC+5:30)**.

To change:
1. Go to **Settings → Time & Format → Timezone**
2. Select your timezone from the dropdown
3. Click **✓ Save Settings**

Changes apply instantly — no module reload needed.

Supported timezones: `IST` · `UTC` · `GMT` · `EST` · `EDT` · `CST` · `CDT` · `MST` · `MDT` · `PST` · `PDT` · `CET` · `EET` · `JST` · `AEST`

---

## FAQ

**Q: Why does BFP show READ-ONLY?**  
A: BFP opens all browser database files in read-only mode (via a temporary copy). This is intentional — forensic best practice requires never modifying original evidence.

**Q: Can I recover incognito/private browsing history?**  
A: No. Chrome and Edge permanently delete incognito session data when the private window closes. BFP's *Incognito Detect* module can find artifact-based *indicators* that private browsing occurred, but cannot recover the URLs.

**Q: Why are some passwords showing [ENCRYPTED]?**  
A: Install `pycryptodome` (`pip install pycryptodome`). Also, decryption only works for the same Windows user account that saved the passwords.

**Q: The app is slow when loading History — why?**  
A: Chrome history can contain 10,000+ URLs. BFP reads them all and sorts/deduplicates. On large profiles this takes 2–5 seconds.

**Q: Can I use BFP on someone else's computer?**  
A: Only with their explicit consent or proper legal authorization. Unauthorized access to another person's browser data may be illegal in your jurisdiction.

**Q: Does BFP send any data to the internet?**  
A: No. BFP is 100% offline. All analysis happens locally on your machine. The only internet access is when you click Email Support or Documentation links.

**Q: How do I analyze a browser from another Windows user account?**  
A: Copy the browser profile folder to your own machine under your user account, then point BFP to it. Note: password decryption will fail for profiles from other user accounts (DPAPI is account-specific).

---

## Building the Executable

To create a standalone `.exe` (no Python required on target machine):

```bash
pip install pyinstaller
python build_exe.py
```

The output will be in `dist/BrowserForensicsPro/`. To distribute, zip the entire `dist/BrowserForensicsPro/` folder.

---

## Project Structure

```
BFP_WEB/
├── main.py                  # Application entry point + API backend
├── ui.html                  # Single-file frontend (HTML + CSS + JS)
├── config.py                # App constants (name, version, paths)
├── requirements.txt         # Python dependencies
├── build_exe.py             # PyInstaller build script
│
├── modules/                 # Data extraction modules
│   ├── history.py           # Browser history (deduped, with visit timestamps)
│   ├── downloads.py         # Download history
│   ├── cookies.py           # Cookie extraction
│   ├── bookmarks.py         # Bookmark/favorites extraction
│   ├── logins.py            # Saved logins + password decryption
│   ├── formhistory.py       # Autofill form data
│   ├── searches.py          # Search query extraction
│   ├── sessions.py          # Session file parsing (SNSS + LZ4)
│   ├── cache.py             # Cache file listing + clearing
│   ├── sitestorage.py       # LocalStorage + IndexedDB
│   ├── sitesettings.py      # Browser permissions
│   ├── timeline.py          # Timeline/activity chart data
│   ├── incognito.py         # Incognito artifact detection
│   └── thumbnails.py        # Session thumbnail files
│
└── utils/
    ├── timeutils.py         # Timezone-aware timestamp conversion
    ├── forensiccopy.py      # Read-only DB copy + safe query helpers
    └── browserdetect.py     # Browser/profile auto-detection
```

---

## License

```
MIT License

Copyright (c) 2026 Sharath Chandra Karnati

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

DISCLAIMER: This tool is provided for lawful forensic investigation only.
The user is solely responsible for compliance with all applicable laws.
```

---

<p align="center">Made with ❤️ by <a href="https://github.com/sharathkarnati">Sharath Chandra Karnati</a></p>
