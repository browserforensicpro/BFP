"""
Browser Forensics Pro v1.0 — pywebview Desktop App
====================================================
Run:   python main.py
Build: python build_exe.py

pywebview opens a native OS window. JS calls Python via window.pywebview.api.*
No HTTP server, no browser tabs, no ports — pure native desktop app.
"""

import os, sys, json, logging, datetime, shutil, re
import webview

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("BFP")

from config import *
from utils.browserdetector import detect_browsers, get_chromium_dbs, get_firefox_dbs
from utils.sessionanalyzer  import detect_browser_times, validate_session_tokens, analyze_sessions
from utils.cacherebuilder   import extract_cached_images, clear_least_used_cache, clear_old_cache, clear_all_cache
import modules.history       as mod_history
import modules.downloads     as mod_downloads
import modules.cookies       as mod_cookies
import modules.bookmarks     as mod_bookmarks
import modules.logins        as mod_logins
import modules.formhistory   as mod_formhistory
import modules.searches      as mod_searches
import modules.cache         as mod_cache
import modules.thumbnails    as mod_thumbnails
import modules.sitesettings  as mod_sitesettings
import modules.sitestorage   as mod_sitestorage
import modules.sessions      as mod_sessions
import modules.timeline      as mod_timeline
import modules.categorizer   as mod_categorizer
import modules.vssrecovery   as mod_vss
import modules.reportbuilder as mod_report

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html")

# Default user settings
DEFAULT_SETTINGS = {
    "theme":          "dark",
    "time_format":    "12",        # "12" or "24"
    "export_format":  "pdf",
    "auto_refresh":   False,
    "data_retention": 30,          # days
    "log_level":      "INFO",
}
SETTINGS_FILE = os.path.join(TEMP_DIR, "bfp_settings.json")


class ForensicsAPI:
    """Python API exposed to JavaScript. All methods callable as window.pywebview.api.X()"""

    def __init__(self):
        self._browsers = {}
        self._profile  = {}
        self._dbs      = {}
        self._cache    = {}
        self._window   = None
        self._settings = self._load_settings()
        self._img_cache_dir = os.path.join(TEMP_DIR, "cached_images")

    # ════════════════════════════════════════════════════════
    # SETTINGS
    # ════════════════════════════════════════════════════════
    def _load_settings(self) -> dict:
        try:
            if os.path.isfile(SETTINGS_FILE):
                with open(SETTINGS_FILE) as f:
                    s = json.load(f)
                    return {**DEFAULT_SETTINGS, **s}
        except Exception: pass
        return dict(DEFAULT_SETTINGS)

    def get_settings(self) -> dict:
        from utils.timeutils import get_timezone_label, KNOWN_TZ
        s = dict(self._settings)
        s.setdefault("timezone", "IST")
        return {"ok": True, "settings": s, "known_timezones": sorted(KNOWN_TZ.keys())}

    def save_settings(self, settings: dict) -> dict:
        from utils.timeutils import set_timezone
        tz = settings.get("timezone", "IST")
        set_timezone(tz)
        try:
            self._settings = {**DEFAULT_SETTINGS, **settings}
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._settings, f, indent=2)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def reset_settings(self) -> dict:
        self._settings = dict(DEFAULT_SETTINGS)
        try:
            if os.path.isfile(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
        except Exception: pass
        return {"ok": True, "settings": self._settings}

    # ════════════════════════════════════════════════════════
    # BROWSER / PROFILE
    # ════════════════════════════════════════════════════════
    def scan_browsers(self) -> dict:
        try:
            found = detect_browsers()
            self._browsers = found
            result = {}
            for br, profiles in found.items():
                result[br] = [{"name": p["name"], "path": p["path"], "idx": i}
                               for i, p in enumerate(profiles)]
            return {"ok": True, "browsers": result}
        except Exception as e:
            logger.error(f"scan_browsers: {e}", exc_info=True)
            return {"ok": False, "error": str(e), "browsers": {}}

    def load_profile(self, browser: str, idx: int) -> dict:
        try:
            profiles = self._browsers.get(browser, [])
            if idx >= len(profiles):
                return {"ok": False, "error": "Profile index out of range"}
            prof = profiles[idx]
            self._profile = prof
            self._cache   = {}
            ff = prof.get("browser") == "Firefox"
            self._dbs = get_firefox_dbs(prof) if ff else get_chromium_dbs(prof)
            logger.info(f"Loaded: {browser} / {prof['name']}")
            return {"ok": True, "browser": browser,
                    "profile": prof["name"], "path": prof.get("path", "")}
        except Exception as e:
            logger.error(f"load_profile: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # MODULE DATA
    # ════════════════════════════════════════════════════════
    def get_data(self, module: str, page: int = 1,
                 per: int = 300, search: str = "") -> dict:
        if not self._profile:
            return {"ok": False, "error": "No profile loaded",
                    "rows": [], "cols": [], "total": 0, "pages": 0}
        try:
            data = self._cache.get(module)
            if data is None:
                data = self._fetch(module)
                self._cache[module] = data

            if search:
                s = search.lower()
                data = [r for r in data if any(s in str(v).lower() for v in r.values())]

            total = len(data)
            start = (page - 1) * per
            page_data = data[start: start + per]
            cols = [c for c in (page_data[0].keys() if page_data else [])
                    if not c.startswith("_")]
            rows = [{c: str(r.get(c, "")) for c in cols} for r in page_data]

            return {"ok": True, "rows": rows, "cols": cols, "total": total,
                    "page": page, "pages": max(1, (total + per - 1) // per)}
        except Exception as e:
            logger.error(f"get_data [{module}]: {e}", exc_info=True)
            return {"ok": False, "error": str(e),
                    "rows": [], "cols": [], "total": 0, "pages": 0}

    def _fetch(self, key: str) -> list:
        dbs = self._dbs
        ff  = self._profile.get("browser") == "Firefox"
        pp  = self._profile.get("path", "")
        dispatch = {
            "history":     lambda: mod_categorizer.categorize_history(
                               mod_history.extract_firefox(dbs) if ff
                               else mod_history.extract_chromium(dbs)),
            "downloads":   lambda: mod_downloads.extract_firefox(dbs) if ff
                               else mod_downloads.extract_chromium(dbs),
            "cookies":     lambda: mod_cookies.extract_firefox(dbs) if ff
                               else mod_cookies.extract_chromium(dbs, pp),
            "bookmarks":   lambda: mod_bookmarks.extract_firefox(dbs) if ff
                               else mod_bookmarks.extract_chromium(dbs),
            "logins":      lambda: mod_logins.extract_firefox(dbs) if ff
                               else mod_logins.extract_chromium(dbs),
            "formhistory": lambda: mod_formhistory.extract_firefox(dbs) if ff
                               else mod_formhistory.extract_chromium(dbs),
            "searches":    lambda: self._get_searches(ff, dbs),
            "thumbnails":  lambda: mod_thumbnails.extract_chromium(dbs),
            "sessions":    lambda: mod_sessions.extract_firefox(dbs) if ff
                               else mod_sessions.extract_chromium(dbs),
            "cache":       lambda: mod_cache.get_cache_list(dbs),
            "sitesettings":lambda: mod_sitesettings.extract_firefox(dbs) if ff
                               else mod_sitesettings.extract_chromium(dbs),
            "sitestorage": lambda: mod_sitestorage.extract_firefox(dbs) if ff
                               else mod_sitestorage.extract_chromium(dbs),
            "deleted":     lambda: mod_vss.extract_all_deleted(dbs),
            "timeline":    lambda: self._get_timeline(ff, dbs),
        }
        fn = dispatch.get(key)
        return fn() if fn else []

    def _get_searches(self, ff, dbs):
        if "history" not in self._cache:
            h = mod_history.extract_firefox(dbs) if ff else mod_history.extract_chromium(dbs)
            self._cache["history"] = h
        return mod_searches.extract_from_history(self._cache["history"])

    def _get_timeline(self, ff, dbs):
        """Returns flat rows for the generic data table (legacy)."""
        if "history" not in self._cache:
            h = mod_history.extract_firefox(dbs) if ff else mod_history.extract_chromium(dbs)
            self._cache["history"] = h
        tl = mod_timeline.build_timeline(self._cache["history"],
                                          self._profile.get("browser","chromium"))
        rows = []
        for h, v in sorted(tl.get("hourly",{}).items()):
            rows.append({"type":"hourly","hour":str(h),"visits":str(v)})
        for d, v in sorted(tl.get("daily",{}).items()):
            rows.append({"type":"daily","date":d,"visits":str(v)})
        for i, dom in enumerate(tl.get("top_domains",[])[:60]):
            rows.append({"type":"top_domain","rank":str(i+1),
                          "domain":dom["domain"],"visits":str(dom["count"])})
        for i, pg in enumerate(tl.get("top_pages",[])[:60]):
            rows.append({"type":"top_page","rank":str(i+1),
                          "title":(pg.get("title") or pg.get("url",""))[:80],
                          "visits":str(pg["count"])})
        for e in tl.get("entries",[])[:300]:
            rows.append({"type":"entry", **e})
        return rows

    def get_timeline_data(self) -> dict:
        """
        Dedicated timeline API — returns fully structured data so JS never
        has to guess column order from mixed-type flat rows.
        """
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            ff  = self._profile.get("browser") == "Firefox"
            dbs = self._dbs
            if "history" not in self._cache:
                h = mod_history.extract_firefox(dbs) if ff else mod_history.extract_chromium(dbs)
                self._cache["history"] = h
            tl = mod_timeline.build_timeline(
                self._cache["history"], self._profile.get("browser","chromium"))

            return {
                "ok":         True,
                "hourly":     dict(tl.get("hourly",{})),       # {0:n, 1:n … 23:n}
                "daily":      dict(tl.get("daily",{})),        # {"YYYY-MM-DD": n}
                "top_domains":[
                    {"domain": d["domain"], "visits": d["count"]}
                    for d in tl.get("top_domains",[])[:40]
                ],
                "top_pages":  [
                    {"title": (pg.get("title") or pg.get("url",""))[:100],
                     "url":   pg.get("url","")[:200],
                     "visits": pg["count"]}
                    for pg in tl.get("top_pages",[])[:40]
                ],
                "total_visits": tl.get("total_visits", 0),
            }
        except Exception as e:
            logger.error(f"get_timeline_data: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════════
    def get_summary(self) -> dict:
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            from collections import Counter
            from urllib.parse import urlparse
            from utils.timeutils import webkit_to_datetime, unix_us_to_datetime
            import datetime as dt

            ff = self._profile.get("browser") == "Firefox"
            IST = dt.timedelta(hours=5, minutes=30)

            def load(k):
                if k not in self._cache:
                    self._cache[k] = self._fetch(k)
                return self._cache[k]

            hist      = load("history")
            cookies   = load("cookies")
            logins    = load("logins")
            downloads = load("downloads")
            searches  = load("searches")
            deleted   = load("deleted")

            domains    = Counter()
            categories = Counter()
            dates_seen = set()
            for row in hist:
                try:
                    d = urlparse(row.get("url","")).netloc.replace("www.","")
                    if d: domains[d] += 1
                except: pass
                cat = row.get("category","")
                if cat: categories[cat] += 1
                ts = row.get("visit_time_raw", 0)
                if ts:
                    try:
                        utc = unix_us_to_datetime(int(ts)) if ff else webkit_to_datetime(int(ts))
                        ist = utc + IST
                        dates_seen.add(ist.strftime("%Y-%m-%d"))
                    except: pass

            top_domains = [{"domain":d,"visits":c} for d,c in domains.most_common(10)]
            activity    = detect_browser_times(hist)
            sess_ana    = analyze_sessions([], hist)
            tokens      = validate_session_tokens(cookies)

            SENSITIVE_KW = ["bank","paypal","pay","wallet","crypto","porn","adult",
                             "torrent","vpn","darkweb","onion","hacking","exploit"]
            sensitive_doms = list({d for d,_ in domains.most_common(100)
                                   if any(kw in d for kw in SENSITIVE_KW)})
            risky_dl  = [r for r in downloads if str(r.get("state","")) in
                         ["1","interrupted","dangerous"]]
            cred_sites = list({r.get("origin_url","")[:80] for r in logins
                                if r.get("origin_url")})[:10]
            del_by_type = Counter(r.get("_artifact_type","?") for r in deleted)
            del_urls    = [r.get("url","") or r.get("value","") for r in deleted
                           if r.get("url") or r.get("value")][:8]

            return {
                "ok": True,
                "meta": {
                    "browser":   self._profile.get("browser","?"),
                    "profile":   self._profile.get("name","?"),
                    "path":      self._profile.get("path","?"),
                    "generated": (dt.datetime.utcnow()+IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
                },
                "overview": {
                    "total_history":           len(hist),
                    "total_cookies":           len(cookies),
                    "total_logins":            len(logins),
                    "total_downloads":         len(downloads),
                    "total_searches":          len(searches),
                    "total_deleted_recovered": len(deleted),
                    "active_days":             len(dates_seen),
                    "session_tokens":          len(tokens),
                },
                "top_domains":  top_domains,
                "categories":   [{"category":k,"count":v} for k,v in categories.most_common()],
                "activity_days": activity[:14],
                "session_analysis": {
                    "incognito_suspected": sess_ana.get("incognito_suspected", False),
                    "gaps_found":          len(sess_ana.get("gaps_detected",[])),
                    "total_gaps_hours":    round(sum(
                        g.get("gap_hours",0) for g in sess_ana.get("gaps_detected",[])),1),
                },
                "sensitive_findings": {
                    "sensitive_domains": sensitive_doms,
                    "risky_downloads":   len(risky_dl),
                    "credential_sites":  cred_sites,
                    "session_tokens":    [{"name":t["name"],"host":t["host"]}
                                           for t in tokens[:10]],
                },
                "deleted_recovery": {
                    "by_type":    dict(del_by_type),
                    "sample_urls": del_urls,
                },
                "top_searches": [r.get("query","") for r in searches[:20] if r.get("query")],
            }
        except Exception as e:
            logger.error(f"get_summary: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # EXPORT + REPORT (merged)
    # ════════════════════════════════════════════════════════
    def export_report(self, modules: list, fmt: str, save_path: str,
                      include_summary: bool = True) -> dict:
        """
        Unified export: collects data from selected modules,
        prepends a Summary section matching the Summary Report UI,
        exports to PDF / HTML / JSON.
        """
        try:
            summary = self.get_summary() if include_summary else {}
            all_data = []
            log = []
            for key in modules:
                try:
                    rows = self._cache.get(key) or self._fetch(key)
                    for r in rows:
                        r2 = dict(r); r2["_module"] = key
                        all_data.append(r2)
                    log.append({"mod": key, "status": "ok", "count": len(rows)})
                except Exception as e:
                    log.append({"mod": key, "status": "error", "msg": str(e)})

            meta = {
                "Browser":   self._profile.get("browser","?"),
                "Profile":   self._profile.get("name","?"),
                "Modules":   ", ".join(modules),
                "Records":   str(len(all_data)),
                "Generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            if fmt == "pdf":
                ok = self._export_summary_pdf(summary, all_data, save_path, meta)
            elif fmt == "html":
                ok = self._export_summary_html(summary, all_data, save_path, meta)
            elif fmt == "json":
                ok = self._export_json(summary, all_data, save_path)
            elif fmt == "xlsx":
                ok = mod_report.export_excel(all_data, save_path, "Forensic Report")
            elif fmt == "xml":
                ok = mod_report.export_xml(all_data, save_path)
            else:
                ok = mod_report.export_csv(all_data, save_path)

            # Guard: ok may be None if export fn returns nothing
            if ok is None:
                ok = os.path.isfile(save_path)

            return {"ok": bool(ok), "path": save_path, "log": log, "total": len(all_data)}
        except Exception as e:
            logger.error(f"export_report: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    def export_module(self, module: str, fmt: str, save_path: str) -> dict:
        """Quick single-module export from toolbar."""
        try:
            data = self._cache.get(module) or self._fetch(module)
            meta = {"Browser": self._profile.get("browser","?"),
                    "Profile": self._profile.get("name","?"), "Module": module}
            fns = {
                "pdf":  lambda: mod_report.export_pdf(data, save_path, f"BFP — {module.title()}", meta),
                "html": lambda: mod_report.export_html(data, save_path, f"BFP — {module.title()}", meta),
                "csv":  lambda: mod_report.export_csv(data, save_path),
                "xlsx": lambda: mod_report.export_excel(data, save_path, module),
                "xml":  lambda: mod_report.export_xml(data, save_path),
                "json": lambda: self._export_json({}, data, save_path),
            }
            ok = fns.get(fmt, fns["csv"])()
            return {"ok": ok, "path": save_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _export_json(self, summary: dict, data: list, path: str) -> bool:
        try:
            out = {"summary": summary, "records": data,
                   "generated": datetime.datetime.now().isoformat()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"JSON export: {e}"); return False

    def _export_summary_pdf(self, summary: dict, data: list, path: str, meta: dict) -> bool:
        """PDF with summary section + data tables."""
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                             Paragraph, Spacer, HRFlowable)
            from reportlab.lib.units import inch, cm

            C_DARK   = colors.HexColor("#050d1a")
            C_PANEL  = colors.HexColor("#0c1e32")
            C_ACCENT = colors.HexColor("#00c8f0")
            C_BLUE   = colors.HexColor("#0077cc")
            C_GREEN  = colors.HexColor("#00e87a")
            C_RED    = colors.HexColor("#ff4060")
            C_YELLOW = colors.HexColor("#ffc200")
            C_TXT    = colors.HexColor("#e0f0ff")
            C_DIM    = colors.HexColor("#7ab0d0")

            doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                leftMargin=0.6*inch, rightMargin=0.6*inch,
                topMargin=0.5*inch, bottomMargin=0.5*inch)

            s = getSampleStyleSheet()
            def sty(name, **kw):
                return ParagraphStyle(name, parent=s["Normal"], **kw)

            title_s = sty("T", fontSize=20, textColor=C_ACCENT,
                           fontName="Helvetica-Bold", spaceAfter=4)
            sub_s   = sty("S", fontSize=9,  textColor=C_DIM, spaceAfter=12)
            sec_s   = sty("H", fontSize=13, textColor=C_ACCENT,
                           fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6)
            cell_s  = sty("C", fontSize=7.5, textColor=C_TXT)
            hdr_s   = sty("Hd", fontSize=8, textColor=C_ACCENT, fontName="Helvetica-Bold")
            kv_s    = sty("KV", fontSize=9, textColor=C_DIM)
            alert_s = sty("AL", fontSize=9, textColor=C_YELLOW, fontName="Helvetica-Bold")

            story = []

            # ── TITLE ────────────────────────────────────────────────
            story.append(Paragraph("BROWSER FORENSICS PRO - Forensic Intelligence Report", title_s))
            m = summary.get("meta", meta)
            story.append(Paragraph(
                f"Forensic Intelligence Report  ·  {m.get('browser','?')} / "
                f"{m.get('profile','?')}  ·  {m.get('generated','')}", sub_s))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=C_BLUE, spaceAfter=12))

            # ── OVERVIEW CARDS as table ───────────────────────────────
            ov = summary.get("overview", {})
            if ov:
                story.append(Paragraph("OVERVIEW", sec_s))
                card_data = [
                    [Paragraph("METRIC", hdr_s), Paragraph("VALUE", hdr_s)],
                    *[[Paragraph(k.replace("_"," ").title(), cell_s),
                       Paragraph(f"{v:,}" if isinstance(v,int) else str(v), cell_s)]
                      for k,v in ov.items()]
                ]
                ct = Table(card_data, colWidths=[3*inch, 2*inch])
                ct.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), C_PANEL),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1),
                     [colors.HexColor("#0c1e32"), colors.HexColor("#091523")]),
                    ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#1a3a5c")),
                    ("TOPPADDING", (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ]))
                story.append(ct)

            # ── KEY FINDINGS ──────────────────────────────────────────
            sa = summary.get("session_analysis", {})
            sf = summary.get("sensitive_findings", {})
            story.append(Paragraph("KEY FINDINGS", sec_s))
            if sa.get("incognito_suspected"):
                story.append(Paragraph(
                    f"[!] INCOGNITO SUSPECTED - {sa['gaps_found']} history gap(s), "
                    f"{sa['total_gaps_hours']}h missing", alert_s))
            else:
                story.append(Paragraph("[OK] No significant history gaps detected", alert_s))
            if sf.get("sensitive_domains"):
                story.append(Paragraph(
                    f"[!] Sensitive domains: {', '.join(sf['sensitive_domains'][:5])}", alert_s))
            if sf.get("risky_downloads", 0) > 0:
                story.append(Paragraph(f"[!] {sf['risky_downloads']} risky download(s)", alert_s))
            story.append(Spacer(1, 8))

            # ── TOP DOMAINS ───────────────────────────────────────────
            tdoms = summary.get("top_domains", [])
            if tdoms:
                story.append(Paragraph("TOP VISITED DOMAINS", sec_s))
                dom_data = [[Paragraph("#", hdr_s), Paragraph("Domain", hdr_s),
                              Paragraph("Visits", hdr_s)]]
                for i, d in enumerate(tdoms[:10], 1):
                    dom_data.append([Paragraph(str(i), cell_s),
                                     Paragraph(d["domain"], cell_s),
                                     Paragraph(str(d["visits"]), cell_s)])
                dt2 = Table(dom_data, colWidths=[0.4*inch, 3.5*inch, 1*inch])
                dt2.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), C_PANEL),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1),
                     [colors.HexColor("#0c1e32"), colors.HexColor("#091523")]),
                    ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#1a3a5c")),
                    ("TOPPADDING", (0,0), (-1,-1), 3),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ]))
                story.append(dt2)

            # ── DATA TABLES ───────────────────────────────────────────
            if data:
                story.append(HRFlowable(width="100%", thickness=1,
                                        color=C_BLUE, spaceBefore=16, spaceAfter=8))
                story.append(Paragraph("EXTRACTED DATA", sec_s))
                cols_raw = [c for c in data[0].keys() if not c.startswith("_")][:8]
                cols = cols_raw[:8]
                tbl_data = [[Paragraph(c.replace("_"," ").upper(), hdr_s) for c in cols]]
                for row in data[:1500]:
                    tbl_data.append([Paragraph(str(row.get(c,""))[:70], cell_s)
                                     for c in cols])
                cw = (landscape(A4)[0] - 1.2*inch) / len(cols)
                t = Table(tbl_data, colWidths=[cw]*len(cols), repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), C_PANEL),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1),
                     [colors.HexColor("#0c1e32"), colors.HexColor("#091523")]),
                    ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#1a3a5c")),
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("TOPPADDING", (0,0), (-1,-1), 2),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ]))
                story.append(t)

            # Background
            def bg(canvas, doc):
                canvas.saveState()
                canvas.setFillColor(C_DARK)
                canvas.rect(0, 0, landscape(A4)[0], landscape(A4)[1], fill=1, stroke=0)
                canvas.restoreState()

            doc.build(story, onFirstPage=bg, onLaterPages=bg)
            return True
        except ImportError as e:
            logger.warning(f"reportlab not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"PDF export: {e}", exc_info=True)
            return False

    def _export_summary_html(self, summary: dict, data: list, path: str, meta: dict) -> bool:
        """HTML report matching the Summary Report UI exactly."""
        try:
            ov = summary.get("overview", {})
            sa = summary.get("session_analysis", {})
            sf = summary.get("sensitive_findings", {})
            dr = summary.get("deleted_recovery", {})
            m  = summary.get("meta", meta)
            tdoms = summary.get("top_domains", [])
            cats  = summary.get("categories", [])
            srch  = summary.get("top_searches", [])

            def ov_card(label, val, color="#00c8f0"):
                return f'<div class="scard"><div class="sn" style="color:{color}">{val:,}' \
                       f'</div><div class="sl">{label}</div></div>'

            cards_html = "".join([
                ov_card("History Entries", ov.get("total_history",0), "#55aaff"),
                ov_card("Cookies",         ov.get("total_cookies",0)),
                ov_card("Active Days",     ov.get("active_days",0), "#00e87a"),
                ov_card("Search Terms",    ov.get("total_searches",0), "#ffc200"),
                ov_card("Downloads",       ov.get("total_downloads",0), "#ff8c00"),
                ov_card("Saved Logins",    ov.get("total_logins",0),
                        "#ff4060" if ov.get("total_logins",0) else "#00c8f0"),
                ov_card("Session Tokens",  ov.get("session_tokens",0),
                        "#ffc200" if ov.get("session_tokens",0) else "#00c8f0"),
                ov_card("Deleted Recovered", ov.get("total_deleted_recovered",0),
                        "#ff8c00" if ov.get("total_deleted_recovered",0) else "#00c8f0"),
            ])

            alerts_html = ""
            if sa.get("incognito_suspected"):
                alerts_html += f'<div class="alert d">⚠ INCOGNITO / HISTORY DELETION SUSPECTED — ' \
                               f'{sa["gaps_found"]} gap(s), {sa["total_gaps_hours"]}h missing</div>'
            else:
                alerts_html += '<div class="alert ok">✓ No significant history gaps detected</div>'
            for sd in (sf.get("sensitive_domains") or []):
                alerts_html += f'<div class="alert w">⚠ Sensitive domain: {sd}</div>'
            if sf.get("risky_downloads", 0) > 0:
                alerts_html += f'<div class="alert w">⚠ {sf["risky_downloads"]} risky download(s)</div>'
            if ov.get("total_logins", 0) > 0:
                alerts_html += f'<div class="alert w">🔑 {ov["total_logins"]} credential record(s) stored</div>'

            dom_mx = tdoms[0]["visits"] if tdoms else 1
            doms_html = "".join(
                f'<div class="dom-row"><span class="di">{i+1}</span>'
                f'<span class="dn">{d["domain"]}</span>'
                f'<span class="dc">{d["visits"]}</span>'
                f'<div class="db" style="width:{round(d["visits"]/dom_mx*80)}px"></div></div>'
                for i, d in enumerate(tdoms)
            )
            _cc = {"Adult":"#ff4060","Malware":"#ff8c00","Social Media":"#55aaff","Webmail":"#aa77ff"}
            cats_html = "".join(
                '<div class="kv-row"><span style="color:' + _cc.get(c["category"],"#7ab0d0") + ';font-weight:600">' + c["category"] + '</span><span style="font-family:monospace">' + f'{c["count"]:,}' + '</span></div>'
                for c in cats
            )
            srch_html = "".join(f'<span class="tag">{q}</span>' for q in srch)
            cred_html = "".join(
                f'<div class="kv-row mono">{s}</div>'
                for s in (sf.get("credential_sites") or [])
            ) or '<div style="color:#3a6080">No saved credentials</div>'
            del_html = "".join(
                f'<div class="kv-row"><span style="color:#e0f0ff">{k}</span><span style="color:#00c8f0;font-family:monospace">{v} records</span></div>'
                for k, v in (dr.get("by_type") or {}).items()
            ) or '<div style="color:#3a6080">No deleted data recovered</div>'

            # Data table
            if data:
                dcols = [c for c in data[0].keys() if not c.startswith("_")][:10]
                dt_head = "".join(f"<th>{c.replace('_',' ').upper()}</th>" for c in dcols)
                dt_rows_list = []
                for r in data[:2000]:
                    cells = "".join(f"<td>{str(r.get(c,''))[:80]}</td>" for c in dcols)
                    dt_rows_list.append(f"<tr>{cells}</tr>")
                dt_rows = "".join(dt_rows_list)
            else:
                dt_head = "<th>No data</th>"
                dt_rows = ""

            html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Browser Forensics Pro — Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#050d1a;color:#e0f0ff;font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;padding:24px}}
h1{{font-size:24px;color:#00c8f0;letter-spacing:.5px;margin-bottom:4px}}
.meta{{font-size:11px;color:#7ab0d0;font-family:monospace;margin-bottom:20px}}
.sum-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:24px}}
.scard{{background:#0c1e32;border:1px solid #1a3a5c;border-radius:6px;padding:14px;border-top:2px solid #0077cc}}
.sn{{font-family:monospace;font-size:26px;font-weight:600;line-height:1}}
.sl{{font-size:11px;color:#7ab0d0;margin-top:4px}}
.sum-2col{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
.sec{{background:#0c1e32;border:1px solid #1a3a5c;border-radius:6px;padding:16px}}
.sec-title{{font-size:14px;font-weight:600;color:#e0f0ff;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #1a3a5c}}
.alert{{padding:10px 14px;border-radius:4px;font-size:12px;margin:4px 0}}
.alert.w{{background:#1a1100;border:1px solid #332200;color:#ffc200}}
.alert.d{{background:#1a0608;border:1px solid #380e16;color:#ff4060}}
.alert.ok{{background:#001208;border:1px solid #002e10;color:#00e87a}}
.dom-row{{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px;background:#102540;margin-bottom:3px}}
.di{{color:#3a6080;font-size:10px;width:16px;text-align:right}}
.dn{{flex:1;font-family:monospace;font-size:11px;color:#7ab0d0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.dc{{font-family:monospace;font-size:11px;color:#00c8f0;min-width:36px;text-align:right}}
.db{{height:5px;background:#0077cc;border-radius:2px;opacity:.7}}
.kv-row{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #0d1e2c}}
.mono{{font-family:monospace;font-size:11px;color:#7ab0d0}}
.tag{{display:inline-block;padding:3px 9px;background:#102540;border:1px solid #1a3a5c;border-radius:10px;font-size:10px;color:#7ab0d0;font-family:monospace;margin:2px}}
.tag-cloud{{display:flex;flex-wrap:wrap;gap:4px}}
hr{{border:none;border-top:1px solid #1a3a5c;margin:20px 0}}
h2{{font-size:16px;color:#00c8f0;margin:16px 0 10px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{background:#071525;color:#00c8f0;padding:8px 10px;text-align:left;position:sticky;top:0;font-family:monospace}}
td{{padding:6px 10px;border-bottom:1px solid #0d1e2c;color:#7ab0d0}}
tr:nth-child(even) td{{background:#091523}}
tr:hover td{{background:#0d3050}}
.footer{{color:#3a6080;font-size:10px;text-align:center;margin-top:24px;padding-top:12px;border-top:1px solid #0d1e2c}}
</style></head><body>
<h1>⬡ BROWSER FORENSICS PRO — FORENSIC INTELLIGENCE REPORT</h1>
<div class="meta">Browser: {m.get('browser','?')} &nbsp;·&nbsp; Profile: {m.get('profile','?')} &nbsp;·&nbsp; Generated: {m.get('generated','')}</div>

<div class="sum-grid">{cards_html}</div>

<div class="sum-2col">
  <div style="display:flex;flex-direction:column;gap:12px">
    <div class="sec">
      <div class="sec-title">🔍 KEY FINDINGS</div>
      {alerts_html}
    </div>
    <div class="sec">
      <div class="sec-title">🌐 TOP VISITED DOMAINS</div>
      {doms_html}
    </div>
    <div class="sec">
      <div class="sec-title">🔎 TOP SEARCH TERMS</div>
      <div class="tag-cloud">{srch_html}</div>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:12px">
    <div class="sec">
      <div class="sec-title">📊 URL CATEGORIES</div>
      {cats_html}
    </div>
    <div class="sec">
      <div class="sec-title">🔐 SAVED CREDENTIALS</div>
      {cred_html}
    </div>
    <div class="sec">
      <div class="sec-title">🕵 DELETED DATA RECOVERED</div>
      {del_html}
    </div>
  </div>
</div>

<hr>
<h2>📋 EXTRACTED DATA ({len(data):,} records)</h2>
<div style="overflow-x:auto">
<table><thead><tr>{dt_head}</tr></thead><tbody>{dt_rows}</tbody></table>
</div>
<div class="footer">Browser Forensics Pro — Read-Only Forensic Analysis — {m.get('generated','')}</div>
</body></html>"""

            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            return True
        except Exception as e:
            logger.error(f"HTML summary export: {e}", exc_info=True)
            return False

    # ════════════════════════════════════════════════════════
    # CACHE IMAGES
    # ════════════════════════════════════════════════════════
    def get_cached_images(self) -> dict:
        """Extract cached images and return base64-encoded list for gallery."""
        if not self._profile:
            return {"ok": False, "error": "No profile loaded", "images": []}
        try:
            import base64, mimetypes
            cache_dir = self._dbs.get("Cache", "")
            if not cache_dir or not os.path.isdir(cache_dir):
                return {"ok": False, "error": f"Cache directory not found: {cache_dir}", "images": []}

            shutil.rmtree(self._img_cache_dir, ignore_errors=True)
            os.makedirs(self._img_cache_dir, exist_ok=True)

            paths = extract_cached_images(cache_dir, self._img_cache_dir)
            images = []
            for p in paths[:100]:   # max 100 in gallery
                try:
                    ext  = os.path.splitext(p)[1].lower()
                    mime = {"jpg":".jpg","jpeg":".jpg","png":".png",
                            "gif":".gif","webp":".webp","bmp":".bmp"}.get(ext.lstrip("."), "image/jpeg")
                    with open(p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    images.append({
                        "name":   os.path.basename(p),
                        "mime":   f"image/{ext.lstrip('.')}",
                        "data":   b64,
                        "size":   os.path.getsize(p),
                    })
                except Exception: pass

            return {"ok": True, "images": images, "total": len(paths)}
        except Exception as e:
            logger.error(f"get_cached_images: {e}", exc_info=True)
            return {"ok": False, "error": str(e), "images": []}

    # ════════════════════════════════════════════════════════
    # CLEAR CACHE (manual only)
    # ════════════════════════════════════════════════════════
    def clear_browser_cache(self, mode: str = "least_used", days: int = 30) -> dict:
        """
        Clear browser cache files.
        mode: "least_used"  — delete smallest files (keep top 30% by size)
              "old"         — delete files older than `days` days
              "all"         — delete ALL cache files
        NEVER runs automatically — always requires explicit user confirmation.
        """
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            cache_dir = self._dbs.get("Cache", "")
            if not cache_dir or not os.path.isdir(cache_dir):
                return {"ok": False, "error": "Cache directory not found"}

            if mode == "all":
                result = clear_all_cache(cache_dir)
            elif mode == "old":
                result = clear_old_cache(cache_dir, days=days)
            else:
                result = clear_least_used_cache(cache_dir, keep_pct=0.3)

            # Also clear our temp extracted images
            shutil.rmtree(self._img_cache_dir, ignore_errors=True)
            # Invalidate cache module cache
            self._cache.pop("cache", None)
            return {"ok": True, **result}
        except Exception as e:
            logger.error(f"clear_browser_cache: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # INCOGNITO DETECTION
    # ════════════════════════════════════════════════════════
    def detect_incognito_artifacts(self) -> dict:
        """
        Incognito/private browsing artifact detection.
        Full history recovery isn't possible (Chrome deletes on close),
        but we can find artifacts: DNS cache refs, recent files, prefetch,
        Windows jump lists, WAL remnants, and gap analysis.
        """
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            from utils.sessionanalyzer import analyze_sessions
            from utils.timeutils import webkit_to_datetime

            findings = []
            ff = self._profile.get("browser") == "Firefox"

            # 1. History gap analysis
            hist = self._cache.get("history") or self._fetch("history")
            sess = analyze_sessions([], hist)
            gaps = sess.get("gaps_detected", [])
            if gaps:
                findings.append({
                    "type":   "history_gaps",
                    "title":  "History Gaps Detected",
                    "detail": f"{len(gaps)} gap(s) in browsing history suggest private browsing or deliberate deletion.",
                    "items":  [f"{g['gap_hours']:.1f}h gap" for g in gaps[:8]],
                    "severity": "high" if len(gaps) > 5 else "medium",
                })

            # 2. WAL scan for deleted URLs
            deleted = self._cache.get("deleted") or self._fetch("deleted")
            wal_urls = [r for r in deleted if "RAW WAL" in str(r.get("recovery_source",""))]
            if wal_urls:
                findings.append({
                    "type":   "wal_deleted_urls",
                    "title":  "Deleted URLs in WAL",
                    "detail": f"{len(wal_urls)} URL(s) found in SQLite WAL files that were deleted from history.",
                    "items":  [r.get("url","") or r.get("value","") for r in wal_urls[:10]],
                    "severity": "high",
                })

            # 3. Windows prefetch / recent files (Windows only)
            prefetch_hits = []
            if os.name == "nt":
                prefetch_dir = r"C:\Windows\Prefetch"
                if os.path.isdir(prefetch_dir):
                    try:
                        for f in os.listdir(prefetch_dir):
                            if any(br in f.upper() for br in
                                   ["CHROME","MSEDGE","BRAVE","FIREFOX","OPERA"]):
                                prefetch_hits.append(f)
                    except Exception:
                        pass
                if prefetch_hits:
                    findings.append({
                        "type":   "prefetch",
                        "title":  "Browser Prefetch Files",
                        "detail": f"{len(prefetch_hits)} browser execution traces in Windows Prefetch.",
                        "items":  prefetch_hits[:10],
                        "severity": "low",
                    })

                # Recent files / jump lists
                recent_dir = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Recent")
                if os.path.isdir(recent_dir):
                    recent_browser = []
                    try:
                        for f in os.listdir(recent_dir):
                            if any(br in f.lower() for br in
                                   ["chrome","edge","brave","firefox"]):
                                recent_browser.append(f)
                    except Exception:
                        pass
                    if recent_browser:
                        findings.append({
                            "type":   "jump_list",
                            "title":  "Windows Recent Files",
                            "detail": f"{len(recent_browser)} browser shortcut(s) in Recent Files.",
                            "items":  recent_browser[:10],
                            "severity": "low",
                        })

            # 4. Crash / session recovery files hint
            prof_path = self._profile.get("path", "")
            recovery_hints = []
            for fname in ["Last Session", "Last Tabs", "Current Session", "Current Tabs"]:
                fp = os.path.join(prof_path, fname)
                if os.path.isfile(fp):
                    sz = os.path.getsize(fp)
                    recovery_hints.append(f"{fname} ({sz:,} bytes)")
            if recovery_hints:
                findings.append({
                    "type":   "session_files",
                    "title":  "Session Recovery Files",
                    "detail": "Session files may contain tab references from last session (including possible incognito tabs).",
                    "items":  recovery_hints,
                    "severity": "medium",
                })

            summary_text = (
                "⚠ INCOGNITO ACTIVITY STRONGLY SUSPECTED — multiple indicators found."
                if len(findings) >= 3 else
                "⚠ Some incognito indicators found — review findings below."
                if findings else
                "✓ No significant incognito indicators detected."
            )

            return {
                "ok": True,
                "suspected": len(findings) >= 2,
                "summary": summary_text,
                "findings": findings,
                "note": (
                    "Chrome/Edge delete incognito history on window close — direct recovery "
                    "is not possible. The above are artifact-based indicators only."
                ),
            }
        except Exception as e:
            logger.error(f"detect_incognito: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # FILE DIALOG
    # ════════════════════════════════════════════════════════
    def open_save_dialog(self, default_name: str, ext: str) -> str:
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.expanduser("~/Desktop"),
                save_filename=default_name,
                file_types=(f'{ext.upper()} Files (*.{ext})', 'All files (*.*)')
            )
            return result[0] if result else ""
        except Exception as e:
            logger.warning(f"save_dialog: {e}"); return ""


    # ════════════════════════════════════════════════════════
    # GLOBAL SEARCH — search keyword across all loaded modules
    # ════════════════════════════════════════════════════════
    def global_search(self, keyword: str) -> dict:
        """Search keyword across history, downloads, cookies, logins, searches, bookmarks."""
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        if not keyword or len(keyword.strip()) < 2:
            return {"ok": False, "error": "Keyword too short (min 2 chars)"}
        try:
            kw = keyword.strip().lower()
            SEARCH_MODS = ["history","downloads","cookies","logins","bookmarks",
                           "searches","formhistory","sitestorage"]
            results = []
            for mod in SEARCH_MODS:
                try:
                    data = self._cache.get(mod)
                    if data is None:
                        data = self._fetch(mod)
                        self._cache[mod] = data
                    for row in data:
                        if any(kw in str(v).lower() for v in row.values()):
                            r2 = {k: v for k, v in row.items() if not k.startswith("_")}
                            r2["_source_module"] = mod
                            results.append(r2)
                except Exception:
                    pass
            # Build unified columns (most common across results)
            from collections import Counter
            col_counts = Counter()
            for r in results:
                for k in r:
                    if not k.startswith("_"):
                        col_counts[k] += 1
            priority = ["url","title","name","query","host_key","target_path",
                        "value","last_visit","visit_time","start_time"]
            cols = [c for c in priority if c in col_counts]
            cols += [c for c, _ in col_counts.most_common(12) if c not in cols]
            cols = ["_source_module"] + cols[:8]

            rows_out = [{c: str(r.get(c,"")) for c in cols} for r in results[:500]]
            return {
                "ok": True,
                "keyword": keyword,
                "total": len(results),
                "cols": cols,
                "rows": rows_out,
                "by_module": {
                    mod: sum(1 for r in results if r.get("_source_module")==mod)
                    for mod in SEARCH_MODS
                }
            }
        except Exception as e:
            logger.error(f"global_search: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # DOWNLOAD RISK SCANNER
    # ════════════════════════════════════════════════════════
    def scan_download_risks(self) -> dict:
        """Scan downloads for risky file types, suspicious sources, large files."""
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            RISKY_EXT = {".exe",".bat",".cmd",".ps1",".vbs",".js",".wsf",".msi",
                         ".scr",".pif",".com",".dll",".jar",".apk",".dmg",".sh",".run"}
            SUSP_KW   = ["crack","keygen","hack","patch","serial","license","free",
                         "setup","install","loader","bypass","cheat","exploit","payload"]
            data = self._cache.get("downloads")
            if data is None:
                data = self._fetch("downloads")
                self._cache["downloads"] = data

            risks = []
            for row in data:
                path = str(row.get("target_path","") or row.get("url","")).lower()
                url  = str(row.get("url","")).lower()
                danger = str(row.get("danger_type",""))
                state  = str(row.get("state",""))
                ext = os.path.splitext(path)[1] if path else ""

                level = None; reason = []
                if ext in RISKY_EXT:
                    level = "HIGH"; reason.append(f"Executable file type: {ext}")
                if any(kw in path or kw in url for kw in SUSP_KW):
                    level = level or "MEDIUM"; reason.append("Suspicious keywords in filename/URL")
                if danger not in ("","Safe","0","Allowlisted"):
                    level = "HIGH"; reason.append(f"Chrome flagged as: {danger}")
                if state in ("Interrupted","Cancelled"):
                    level = level or "LOW"; reason.append(f"Download {state.lower()}")

                if level:
                    risks.append({
                        "risk_level":  level,
                        "reason":      ", ".join(reason),
                        "file":        os.path.basename(path) or path[:60],
                        "url":         row.get("url","")[:100],
                        "state":       row.get("state",""),
                        "size":        row.get("total_size",""),
                        "start_time":  row.get("start_time",""),
                    })

            risks.sort(key=lambda x: {"HIGH":0,"MEDIUM":1,"LOW":2}.get(x["risk_level"],3))
            return {"ok": True, "total": len(risks), "risks": risks,
                    "high": sum(1 for r in risks if r["risk_level"]=="HIGH"),
                    "medium": sum(1 for r in risks if r["risk_level"]=="MEDIUM"),
                    "low": sum(1 for r in risks if r["risk_level"]=="LOW")}
        except Exception as e:
            logger.error(f"scan_download_risks: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ════════════════════════════════════════════════════════
    # COOKIE / SESSION TOKEN EXPIRY TRACKER
    # ════════════════════════════════════════════════════════
    def get_active_sessions(self) -> dict:
        """Return session cookies grouped by: still active, expiring soon, expired."""
        if not self._profile:
            return {"ok": False, "error": "No profile loaded"}
        try:
            from utils.timeutils import webkit_to_datetime
            import datetime as dt
            now  = dt.datetime.utcnow()
            IST  = dt.timedelta(hours=5, minutes=30)
            soon = now + dt.timedelta(days=7)

            cookies = self._cache.get("cookies")
            if cookies is None:
                cookies = self._fetch("cookies")
                self._cache["cookies"] = cookies

            TOKEN_KW = ["session","token","auth","jwt","access","refresh",
                        "phpsessid","jsessionid","csrf","login","bearer","sid"]

            active=[]; expiring=[]; expired=[]; permanent=[]
            for c in cookies:
                name = (c.get("name","") or "").lower()
                if not any(kw in name for kw in TOKEN_KW):
                    continue
                raw_exp = c.get("expires_utc") or c.get("expires") or 0
                exp_dt  = None
                try:
                    exp_raw = int(str(raw_exp).replace(".0","") or 0)
                    if exp_raw > 0:
                        exp_dt = webkit_to_datetime(exp_raw)
                except Exception:
                    pass

                rec = {
                    "name":    c.get("name",""),
                    "host":    c.get("host_key","") or c.get("host",""),
                    "expires": (exp_dt + IST).strftime("%Y-%m-%d %I:%M %p IST") if exp_dt else "Session",
                    "status":  "",
                }
                if exp_dt is None:
                    rec["status"] = "Session (no expiry)"
                    permanent.append(rec)
                elif exp_dt < now:
                    rec["status"] = "Expired"
                    expired.append(rec)
                elif exp_dt < soon:
                    rec["status"] = "Expires soon"
                    expiring.append(rec)
                else:
                    rec["status"] = "Active"
                    active.append(rec)

            return {
                "ok": True,
                "active":    active[:60],
                "expiring":  expiring[:60],
                "expired":   expired[:60],
                "permanent": permanent[:60],
                "counts": {
                    "active": len(active),
                    "expiring_soon": len(expiring),
                    "expired": len(expired),
                    "permanent": len(permanent),
                }
            }
        except Exception as e:
            logger.error(f"get_active_sessions: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    def open_url(self, url: str) -> dict:
        """Open a URL or mailto link in the system default app."""
        import subprocess, sys
        try:
            if sys.platform == "win32":
                import os; os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_feedback(self, text: str) -> dict:
        """Save feedback to a local file in the app temp directory."""
        try:
            import datetime as dt
            fpath = os.path.join(TEMP_DIR, "feedback.txt")
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(fpath, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n{ts}\n{text}\n")
            return {"ok": True, "path": fpath}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_app_info(self) -> dict:
        """Return app metadata for About/Settings pages."""
        import platform
        return {
            "name":       APP_NAME,
            "version":    APP_VERSION,
            "author":     APP_AUTHOR,
            "python":     sys.version.split()[0],
            "platform":   platform.system(),
            "platform_v": platform.version(),
            "arch":       platform.machine(),
            "temp_dir":   TEMP_DIR,
        }


# ════════════════════════════════════════════════════════════════════
def main():
    api = ForensicsAPI()
    window = webview.create_window(
        title         = f"Browser Forensics Pro  ·  v{APP_VERSION}",
        url           = HTML_PATH,
        js_api        = api,
        width         = 1760,
        height        = 1000,
        min_size      = (1300, 760),
        resizable     = True,
        text_select   = True,
        confirm_close = False,
    )
    api._window = window
    webview.start(debug=False)

if __name__ == "__main__":
    main()
