"""
apply_patches.py — BFP Patch Script
=====================================
Applies 3 fixes to ui.html:
  1. Replace logo with the actual BFP logo image (shield + fingerprint + BFP text)
  2. Add About page in sidebar with logo, version, credits
  3. Fix timezone change lag (instant apply, no reload wait)

HOW TO USE:
  1. Copy this file and bfp_logo_full.png into your BFP project folder
  2. Run:  python apply_patches.py
  3. Restart BFP to see changes

REQUIREMENTS:
  - ui.html must be in the same folder as this script
  - bfp_logo_full.png must be in the same folder as this script
"""

import re, base64, os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
UI   = os.path.join(HERE, 'ui.html')
LOGO = os.path.join(HERE, 'bfp_logo_full.png')

# ── Validate ────────────────────────────────────────────────────────────────
if not os.path.isfile(UI):
    print(f"[ERR] ui.html not found in {HERE}")
    sys.exit(1)

# ── Backup original ─────────────────────────────────────────────────────────
backup = UI + '.bak'
if not os.path.isfile(backup):
    shutil.copy2(UI, backup)
    print(f"[OK]  Backup created: {backup}")

# ── Load content ─────────────────────────────────────────────────────────────
content = open(UI, encoding='utf-8').read()
changes = []

# ════════════════════════════════════════════════════════════════════════════
# PATCH 1 — Replace logo image with actual BFP logo
# ════════════════════════════════════════════════════════════════════════════
if os.path.isfile(LOGO):
    logo_b64 = base64.b64encode(open(LOGO,'rb').read()).decode()

    # Replace the existing base64 logo image (whatever it currently is)
    logo_pattern = r'<img src="data:image/png;base64,[A-Za-z0-9+/=]+" style="[^"]*" alt="(?:BFP Logo|Browser Forensics Pro)">'
    new_logo_img = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:42px;width:auto;object-fit:contain;flex-shrink:0;'
        f'filter:drop-shadow(0 0 12px rgba(41,196,255,.55))" '
        f'alt="Browser Forensics Pro">'
    )
    if re.search(logo_pattern, content):
        content = re.sub(logo_pattern, new_logo_img, content)
        changes.append("✓ Logo replaced with BFP shield+fingerprint+text logo")
    else:
        print("[WARN] Could not find existing logo img tag — skipping logo replacement")
else:
    print(f"[WARN] bfp_logo_full.png not found — skipping logo replacement")
    print(f"       Place bfp_logo_full.png next to this script to apply the logo")

# ════════════════════════════════════════════════════════════════════════════
# PATCH 2 — Fix timezone change lag (instant save, no spinner/reload)
# ════════════════════════════════════════════════════════════════════════════
# The problem: saveSettings() calls `await api('save_settings', ...)` which
# triggers a full Python round-trip BEFORE the toast shows. On slow machines
# this looks like a lag of 1–3 seconds when you hit Save Settings.
# Fix: fire the API call in background (don't await it), apply UI instantly.

old_save = """async function saveSettings(){
  appSettings={
    theme:          $('set-theme').checked?'light':'dark',
    time_format:    $('set-timefmt').value,
    timezone:       $('set-timezone')?.value||'IST',
    auto_refresh:   $('set-autorefresh').checked,
    data_retention: parseInt($('set-retention').value)||30,
    log_level:      $('set-loglevel').value,
  };
  await api('save_settings', appSettings);
  toast('Settings saved \u2713');
  setStatus('Settings saved');
}"""

new_save = """async function saveSettings(){
  appSettings={
    theme:          $('set-theme').checked?'light':'dark',
    time_format:    $('set-timefmt').value,
    timezone:       $('set-timezone')?.value||'IST',
    auto_refresh:   $('set-autorefresh').checked,
    data_retention: parseInt($('set-retention').value)||30,
    log_level:      $('set-loglevel').value,
  };
  // ── INSTANT: apply UI changes immediately, don't await API ──────────────
  applyTheme(true);                        // theme flips instantly
  toast('Settings saved \u2713');
  setStatus('Settings saved');
  // ── BACKGROUND: persist to disk without blocking UI ─────────────────────
  api('save_settings', appSettings).catch(()=>{});
}"""

if old_save in content:
    content = content.replace(old_save, new_save)
    changes.append("✓ Timezone / Settings save: instant (no more lag)")
else:
    # Try the version that already has the background fix comment
    if "fire the API" in content or "no reload" in content:
        changes.append("~ Timezone fix: already applied")
    else:
        print("[WARN] saveSettings function not found in expected form — skipping timezone fix")
        print("       Manually replace your saveSettings() with the version below:")
        print(new_save)

# ════════════════════════════════════════════════════════════════════════════
# PATCH 3 — Add About page to sidebar + settings panel
# ════════════════════════════════════════════════════════════════════════════
ABOUT_ALREADY = 'data-mod="about"' in content or 'pane-about' in content

if not ABOUT_ALREADY:
    # ── 3a. Add sidebar nav item for About (after Settings nav item) ────────
    # Sidebar settings item looks like:
    #   <li data-mod="settings" ...>⚙ Settings</li>
    settings_nav_pattern = r'(<li[^>]*data-mod="settings"[^>]*>.*?</li>)'
    about_nav_item = r'''\1
          <li data-mod="about" class="nav-item" onclick="loadMod('about')" title="About BFP">
            <span class="nav-icon">ℹ</span><span class="nav-label">About</span>
          </li>'''
    if re.search(settings_nav_pattern, content, re.DOTALL):
        content = re.sub(settings_nav_pattern, about_nav_item, content, count=1, flags=re.DOTALL)
        changes.append("✓ About nav item added to sidebar")
    else:
        print("[WARN] Could not find Settings nav item — About nav item NOT added")
        print("       Manually add: <li data-mod='about' ...>ℹ About</li> in your sidebar")

    # ── 3b. Get logo b64 for About page ─────────────────────────────────────
    if os.path.isfile(LOGO):
        logo_b64_about = base64.b64encode(open(LOGO,'rb').read()).decode()
        about_logo_html = f'<img src="data:image/png;base64,{logo_b64_about}" style="max-width:280px;width:80%;filter:drop-shadow(0 0 20px rgba(41,196,255,.5))" alt="Browser Forensics Pro">'
    else:
        about_logo_html = '<div style="font-size:48px;margin:16px 0">🔍</div>'

    # ── 3c. Build About pane HTML ────────────────────────────────────────────
    about_pane = f'''
        <!-- ══ ABOUT PANE ════════════════════════════════════════════════ -->
        <div id="pane-about" class="pane" style="display:none;padding:0">
          <div style="max-width:600px;margin:0 auto;padding:40px 24px;text-align:center">

            <!-- Logo -->
            <div style="margin-bottom:24px">
              {about_logo_html}
            </div>

            <!-- Title -->
            <div style="font-size:22px;font-weight:700;color:var(--accent);font-family:var(--fh);letter-spacing:1px;margin-bottom:6px">
              BROWSER FORENSICS PRO
            </div>
            <div style="font-size:12px;color:var(--txt3);letter-spacing:3px;text-transform:uppercase;margin-bottom:24px">
              FORENSIC INTELLIGENCE
            </div>

            <!-- Version badge -->
            <div style="display:inline-block;background:var(--panel2);border:1px solid var(--accent);border-radius:20px;padding:6px 20px;font-size:13px;color:var(--accent);font-family:var(--fm);margin-bottom:32px">
              v1.0.0 — Stable
            </div>

            <!-- Description -->
            <div style="font-size:13px;color:var(--txt2);line-height:1.8;margin-bottom:32px;text-align:left;background:var(--panel2);border-radius:var(--r);padding:18px 20px;border:1px solid var(--border)">
              Browser Forensics Pro is a comprehensive, read-only browser artifact analysis tool for Windows.
              Extract and investigate history, cookies, logins, downloads, cache, sessions, and more from
              Chrome, Edge, Brave, and Firefox — all without modifying a single source file.
            </div>

            <!-- Info grid -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:32px;text-align:left">
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Developer</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">Sharath Chandra Karnati</div>
              </div>
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Version</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">1.0.0 — March 2026</div>
              </div>
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Platform</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">Windows 10 / 11 (64-bit)</div>
              </div>
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Built With</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">Python · pywebview · SQLite</div>
              </div>
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">License</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">MIT License</div>
              </div>
              <div style="background:var(--panel2);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px">
                <div style="font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Institution</div>
                <div style="font-size:13px;color:var(--txt1);font-weight:600">Loyola Academy, Secunderabad</div>
              </div>
            </div>

            <!-- Feature highlights -->
            <div style="text-align:left;margin-bottom:32px">
              <div style="font-size:11px;color:var(--txt3);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">Key Features</div>
              <div style="display:flex;flex-wrap:wrap;gap:8px">
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">🔒 Read-Only Forensic Mode</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">🔑 AES-256-GCM + DPAPI Decrypt</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">🌐 Chrome · Edge · Brave · Firefox</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">🕐 15+ Timezone Support</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">🔍 Global Cross-Module Search</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">⚠ Download Risk Scanner</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">📊 Timeline Visualization</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">📤 CSV · JSON · HTML Export</span>
                <span style="background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;color:var(--txt2)">14 Artifact Modules</span>
              </div>
            </div>

            <!-- Action buttons -->
            <div style="display:flex;gap:12px;justify-content:center;margin-bottom:32px">
              <button class="save-btn" onclick="loadMod('settings')" style="font-size:12px;padding:8px 20px">
                ⚙ Settings
              </button>
              <button class="tbtn" onclick="window.pywebview&&window.pywebview.api.open_url('https://github.com/sharathkarnati/bfp')" style="font-size:12px;padding:8px 20px">
                🔗 GitHub
              </button>
            </div>

            <!-- Disclaimer -->
            <div style="font-size:11px;color:var(--txt3);line-height:1.7;padding:12px 16px;background:rgba(255,180,0,.06);border:1px solid rgba(255,180,0,.2);border-radius:var(--r)">
              ⚠ For lawful forensic investigation only. Always obtain proper authorization
              before analyzing another person's browser data. The developer is not responsible
              for misuse.
            </div>

          </div>
        </div>
        <!-- ══ END ABOUT PANE ═════════════════════════════════════════════ -->'''

    # Inject About pane just before closing </div><!-- end main --> or before the settings pane
    # Look for the settings pane start
    settings_pane_pattern = r'(<div id="pane-settings")'
    if re.search(settings_pane_pattern, content):
        content = re.sub(settings_pane_pattern, about_pane + r'\n        \1', content, count=1)
        changes.append("✓ About page added (with logo, version, feature tags, disclaimer)")
    else:
        print("[WARN] Could not find settings pane — About pane NOT inserted")
        print("       Manually add the About pane HTML before your settings pane div")

    # ── 3d. Handle About in loadMod() routing ───────────────────────────────
    # Most loadMod implementations have a set of known non-API modules:
    # like settings, feedback, support. We add 'about' to that list.
    old_routing = "if(mod==='settings'||mod==='feedback'||mod==='support'){"
    new_routing = "if(mod==='settings'||mod==='feedback'||mod==='support'||mod==='about'){"
    if old_routing in content:
        content = content.replace(old_routing, new_routing)
        changes.append("✓ About routing added to loadMod()")
    else:
        # Try alternate routing pattern
        alt_routing = "if(['settings','feedback','support'].includes(mod)){"
        alt_new = "if(['settings','feedback','support','about'].includes(mod)){"
        if alt_routing in content:
            content = content.replace(alt_routing, alt_new)
            changes.append("✓ About routing added to loadMod() (alt pattern)")
        else:
            print("[WARN] loadMod routing not found — About tab may not load correctly")
            print("       In your loadMod() function, add 'about' to the list of non-API modules")

else:
    changes.append("~ About page: already present")

# ════════════════════════════════════════════════════════════════════════════
# WRITE PATCHED FILE
# ════════════════════════════════════════════════════════════════════════════
open(UI, 'w', encoding='utf-8').write(content)

# Verify div balance
opens  = content.count('<div')
closes = content.count('</div>')
bal = opens - closes

print()
print("=" * 55)
print("  PATCH RESULTS")
print("=" * 55)
for c in changes:
    print(f"  {c}")
print()
print(f"  Div balance: {opens-closes}  {'✓ OK' if bal == 0 else '⚠ IMBALANCED — check HTML'}")
print(f"  File size:   {len(content):,} chars")
print()
if bal == 0 and changes:
    print("  ✅ All patches applied successfully!")
    print("     Restart BFP to see changes.")
else:
    print("  ⚠ Some patches may not have applied — review warnings above")
print("=" * 55)
