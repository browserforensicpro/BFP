"""
logins.py - Extract saved login data from browsers.
On Windows: attempts DPAPI decryption of Chrome/Edge/Brave passwords.
Chrome 80+: AES-256-GCM with key from Local State file.
"""

import os
import json
import logging
import base64
import sys
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_s_to_str

logger = logging.getLogger(__name__)


def _get_chrome_encryption_key(profile_root: str) -> bytes | None:
    """
    Read Chrome's AES key from Local State file.
    Chrome 80+: key is stored as base64-encoded, DPAPI-encrypted blob.
    Returns raw 32-byte AES key on success, None otherwise.
    """
    try:
        local_state_path = os.path.join(profile_root, "Local State")
        if not os.path.isfile(local_state_path):
            # Try one level up
            local_state_path = os.path.join(os.path.dirname(profile_root), "Local State")
        if not os.path.isfile(local_state_path):
            return None

        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        enc_key_b64 = (local_state.get("os_crypt", {}) or {}).get("encrypted_key", "")
        if not enc_key_b64:
            return None

        enc_key = base64.b64decode(enc_key_b64)
        # Remove "DPAPI" prefix (first 5 bytes)
        if enc_key[:5] == b"DPAPI":
            enc_key = enc_key[5:]

        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD),
                             ("pbData", ctypes.POINTER(ctypes.c_char))]

            p = ctypes.create_string_buffer(enc_key, len(enc_key))
            blobin  = DATA_BLOB(ctypes.sizeof(p), p)
            blobout = DATA_BLOB()
            retval  = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
            if retval:
                key = ctypes.string_at(blobout.pbData, blobout.cbData)
                ctypes.windll.kernel32.LocalFree(blobout.pbData)
                return key
    except Exception as e:
        logger.debug(f"Chrome key extraction: {e}")
    return None


def _decrypt_chrome_password(encrypted_value: bytes, aes_key: bytes | None) -> str:
    """
    Decrypt a Chrome password blob.
    Chrome 80+: b'v10' prefix + 12-byte nonce + ciphertext + 16-byte tag
    Older Chrome: raw DPAPI blob (Windows only)
    """
    if not encrypted_value:
        return ""
    try:
        # Chrome 80+ AES-256-GCM
        if encrypted_value[:3] in (b"v10", b"v11") and aes_key:
            try:
                from Crypto.Cipher import AES
                nonce      = encrypted_value[3:15]
                ciphertext = encrypted_value[15:-16]
                tag        = encrypted_value[-16:]
                cipher     = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
                return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="replace")
            except Exception as e:
                logger.debug(f"AES-GCM decrypt failed: {e}")
                return "[ENCRYPTED — install pycryptodome]"

        # Legacy DPAPI (Windows, Chrome < 80)
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD),
                             ("pbData", ctypes.POINTER(ctypes.c_char))]

            p = ctypes.create_string_buffer(encrypted_value, len(encrypted_value))
            blobin  = DATA_BLOB(ctypes.sizeof(p), p)
            blobout = DATA_BLOB()
            retval  = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
            if retval:
                pwd = ctypes.string_at(blobout.pbData, blobout.cbData)
                ctypes.windll.kernel32.LocalFree(blobout.pbData)
                return pwd.decode("utf-8", errors="replace")

    except Exception as e:
        logger.debug(f"Password decrypt error: {e}")

    return "[ENCRYPTED]"


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("LoginData", "")
    if not db_path:
        return results

    # Try to get decryption key
    profile_root = dbs.get("_profile_path", os.path.dirname(db_path))
    aes_key = _get_chrome_encryption_key(profile_root)
    can_decrypt = aes_key is not None
    logger.info(f"Login decryption: {'key obtained' if can_decrypt else 'no key — showing encrypted'}")

    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "logins"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT origin_url, action_url, username_element,
                   username_value, password_value,
                   date_created, date_last_used, date_password_modified,
                   times_used, blacklisted_by_user
            FROM logins
            ORDER BY date_last_used DESC
        """)
        for row in rows:
            raw_pwd = row[4]
            if raw_pwd and can_decrypt:
                password = _decrypt_chrome_password(bytes(raw_pwd), aes_key)
            elif raw_pwd:
                password = f"[ENCRYPTED — {len(raw_pwd)} bytes]"
            else:
                password = ""

            results.append({
                "origin_url":        row[0] or "",
                "action_url":        row[1] or "",
                "username_element":  row[2] or "",
                "username":          row[3] or "",
                "password":          password,
                "password_len":      len(raw_pwd) if raw_pwd else 0,
                "date_created":      webkit_to_str(row[5]) if row[5] else "N/A",
                "date_last_used":    webkit_to_str(row[6]) if row[6] else "N/A",
                "date_pwd_modified": webkit_to_str(row[7]) if row[7] else "N/A",
                "times_used":        row[8] or 0,
                "blacklisted":       "Yes" if row[9] else "No",
            })
        conn.close()
    except Exception as e:
        logger.error(f"Chromium logins error: {e}", exc_info=True)
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    logins_path = dbs.get("Logins", "")
    if not logins_path or not os.path.isfile(logins_path):
        return results
    try:
        with open(logins_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        for login in data.get("logins", []):
            results.append({
                "origin_url":       login.get("hostname", ""),
                "action_url":       login.get("formSubmitURL", ""),
                "username_element": login.get("usernameField", ""),
                "username":         login.get("encryptedUsername", "[ENCRYPTED]"),
                "password":         "[ENCRYPTED — Firefox uses NSS/key4.db]",
                "password_len":     len(login.get("encryptedPassword", "")),
                "date_created":     unix_s_to_str(int(login["timeCreated"]) // 1000)
                                    if login.get("timeCreated") else "N/A",
                "date_last_used":   unix_s_to_str(int(login["timeLastUsed"]) // 1000)
                                    if login.get("timeLastUsed") else "N/A",
                "date_pwd_modified": "N/A",
                "times_used":       login.get("timesUsed", 0),
                "blacklisted":      "No",
            })
    except Exception as e:
        logger.error(f"Firefox logins error: {e}")
    return results
