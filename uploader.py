"""
Fotobox Uploader — Kernlogik
API-Kommunikation, Foto-Tracking, Upload-Funktionen.
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import requests

# ── DB-Pfad (relativ zum Script) ──────────────────────────────────────

_BASE_DIR = Path(__file__).resolve().parent
DB_PATH = _BASE_DIR / "uploads.db"


def _ensure_db():
    """Erstellt die DB und Tabelle sofort beim Import."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_fingerprint TEXT NOT NULL UNIQUE,
            file_path TEXT NOT NULL,
            event_id INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM uploaded_photos").fetchone()[0]
    conn.close()
    print(f"[DB] Datenbank initialisiert: {DB_PATH} ({count} Fotos getrackt)")


# Beim Import sofort aufrufen:
_ensure_db()

# ── Konfiguration ─────────────────────────────────────────────────────


def _default_raw_config():
    """Gibt die Standard-Konfiguration mit Umgebungen zurück."""
    return {
        "environments": {
            "production": {
                "name": "Produktiv",
                "shop_url": "https://rent4events.ch",
                "api_key": "",
            },
            "test": {
                "name": "Q-System",
                "shop_url": "https://hosting217409.ae921.netcup.net",
                "api_key": "",
            },
        },
        "active_environment": "production",
        "photo_path": "/home/patrick/Pictures",
        "template_path": "/home/patrick/.config/pibooth/template.xml",
        "check_interval": 60,
        "supported_extensions": [".jpg", ".jpeg", ".png"],
    }


def _migrate_to_environments(old_config):
    """Migriert alte Flat-Config zur Umgebungs-Struktur."""
    old_url = old_config.get("shop_url", "https://rent4events.ch")
    old_key = old_config.get("api_key", "")

    is_test = "netcup" in old_url or "hosting" in old_url

    new_config = _default_raw_config()
    new_config["photo_path"] = old_config.get("photo_path", "/home/patrick/Pictures")
    new_config["check_interval"] = old_config.get("check_interval", 60)
    new_config["supported_extensions"] = old_config.get(
        "supported_extensions", [".jpg", ".jpeg", ".png"]
    )

    if is_test:
        new_config["active_environment"] = "test"
        new_config["environments"]["test"]["api_key"] = old_key
        new_config["environments"]["test"]["shop_url"] = old_url
    else:
        new_config["active_environment"] = "production"
        new_config["environments"]["production"]["api_key"] = old_key
        new_config["environments"]["production"]["shop_url"] = old_url

    env_label = "Test" if is_test else "Produktiv"
    print(f"[CONFIG] Migration: Alte Config migriert -> Umgebung: {env_label}")
    return new_config


def load_raw_config(config_path):
    """Lädt die config.json als Roh-Struktur (mit Umgebungen)."""
    path = Path(config_path)
    if path.exists():
        raw = json.loads(path.read_text())
    else:
        raw = _default_raw_config()

    # Migration: alte Flat-Struktur → neue Umgebungs-Struktur
    if "environments" not in raw:
        print("[CONFIG] Alte Config-Struktur erkannt, migriere...")
        raw = _migrate_to_environments(raw)
        Path(config_path).write_text(json.dumps(raw, ensure_ascii=False, indent=4))

    return raw


def load_config(config_path):
    """Lädt die config.json und resolved die aktive Umgebung zu einem flachen Dict.
    Alle bestehenden Aufrufer (config.get('shop_url') etc.) funktionieren weiterhin."""
    raw = load_raw_config(config_path)

    active_env = raw.get("active_environment", "production")
    env_data = raw.get("environments", {}).get(active_env, {})

    return {
        "shop_url": env_data.get("shop_url", ""),
        "api_key": env_data.get("api_key", ""),
        "photo_path": raw.get("photo_path", ""),
        "template_path": raw.get("template_path", ""),
        "check_interval": raw.get("check_interval", 60),
        "supported_extensions": raw.get("supported_extensions", [".jpg", ".jpeg", ".png"]),
        "active_environment": active_env,
        "env_name": env_data.get("name", active_env),
        "environments": raw.get("environments", {}),
    }


def save_config(config_path, config):
    """Speichert die config.json (Roh-Struktur mit Umgebungen)."""
    Path(config_path).write_text(json.dumps(config, ensure_ascii=False, indent=4))


# ── SQLite Tracking-DB ────────────────────────────────────────────────


def init_db(db_path):
    """Erstellt die SQLite-Datenbank für Upload-Tracking.
    GLOBALES Tracking: Ein Foto wird nur EIN MAL hochgeladen, egal welches Event."""
    print(f"[DB] Initialisiere Datenbank: {db_path}")
    db = sqlite3.connect(str(db_path))

    # Migration: alte Tabelle mit (file_path, event_id) durch globale ersetzen
    cursor = db.execute("SELECT sql FROM sqlite_master WHERE name='uploaded_photos'")
    row = cursor.fetchone()
    if row and "event_id" in (row[0] or "") and "file_fingerprint" not in (row[0] or ""):
        print("[DB] Migration: Alte Tabelle gefunden, migriere auf globales Tracking...")
        db.execute("ALTER TABLE uploaded_photos RENAME TO uploaded_photos_old")
        db.execute("""
            CREATE TABLE uploaded_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_fingerprint TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            INSERT OR IGNORE INTO uploaded_photos (file_fingerprint, file_path, event_id, uploaded_at)
            SELECT file_path || ':' || event_id, file_path, event_id, uploaded_at
            FROM uploaded_photos_old
        """)
        db.execute("DROP TABLE uploaded_photos_old")
        db.commit()
        print("[DB] Migration abgeschlossen")
    elif row:
        print(f"[DB] Tabelle existiert bereits (globales Schema)")
    else:
        print("[DB] Erstelle neue Tabelle uploaded_photos")

    # Tabelle erstellen falls komplett neu
    db.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_fingerprint TEXT NOT NULL UNIQUE,
            file_path TEXT NOT NULL,
            event_id INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

    count = db.execute("SELECT COUNT(*) FROM uploaded_photos").fetchone()[0]
    print(f"[DB] Bereit. {count} Fotos bereits getrackt.")
    return db


def _file_fingerprint(file_path):
    """Erzeugt einen eindeutigen Fingerprint für eine Datei.
    Basiert auf Dateiname + Grösse + Änderungsdatum.
    Schnell und zuverlässig ohne die ganze Datei zu hashen."""
    try:
        stat = os.stat(file_path)
        name = os.path.basename(file_path)
        raw = f"{name}:{stat.st_size}:{stat.st_mtime}"
        fp = hashlib.sha256(raw.encode()).hexdigest()
        return fp
    except OSError as e:
        print(f"[FINGERPRINT] FEHLER bei {file_path}: {e}")
        return None


def is_uploaded(db, file_path):
    """Prüft ob ein Foto bereits hochgeladen wurde (GLOBAL, event-unabhängig)."""
    fp = _file_fingerprint(file_path)
    if fp is None:
        print(f"[CHECK] {os.path.basename(file_path)}: Fingerprint fehlgeschlagen, gilt als NEU")
        return False
    cursor = db.execute(
        "SELECT 1 FROM uploaded_photos WHERE file_fingerprint = ?", (fp,)
    )
    found = cursor.fetchone() is not None
    return found


def mark_uploaded(db, file_path, event_id):
    """Markiert ein Foto als hochgeladen (GLOBAL gesperrt)."""
    fp = _file_fingerprint(file_path)
    if fp is None:
        print(f"[TRACK] FEHLER: Kann {file_path} nicht tracken (kein Fingerprint)")
        return
    db.execute(
        "INSERT OR IGNORE INTO uploaded_photos (file_fingerprint, file_path, event_id) VALUES (?, ?, ?)",
        (fp, file_path, event_id),
    )
    db.commit()
    print(f"[TRACK] Gespeichert: {os.path.basename(file_path)} -> Event {event_id}, FP {fp[:12]}...")


def get_upload_stats(db_path):
    """Holt Upload-Statistiken."""
    db_file = Path(db_path)
    if not db_file.exists():
        return {"total": 0, "today": 0}

    db = sqlite3.connect(str(db_path))
    total = db.execute("SELECT COUNT(*) FROM uploaded_photos").fetchone()[0]
    today = db.execute(
        "SELECT COUNT(*) FROM uploaded_photos WHERE DATE(uploaded_at) = DATE('now')"
    ).fetchone()[0]
    db.close()
    return {"total": total, "today": today}


# ── Foto-Discovery ────────────────────────────────────────────────────


def get_new_photos(db, config):
    """Findet alle neuen (noch nie hochgeladenen) Fotos im Hauptverzeichnis.
    Nur Dateien direkt in photo_path — keine Unterordner (raw/, forget/ etc.).
    Prüfung ist GLOBAL — einmal hochgeladen = für immer gesperrt."""
    photo_path = config.get("photo_path", "")
    extensions = config.get("supported_extensions", [".jpg", ".jpeg", ".png"])

    print(f"[SCAN] Suche Fotos in: {photo_path} (nur Hauptverzeichnis)")
    print(f"[SCAN] Erlaubte Endungen: {extensions}")

    if not photo_path:
        print("[SCAN] ABBRUCH: Kein photo_path konfiguriert")
        return []

    if not os.path.isdir(photo_path):
        print(f"[SCAN] ABBRUCH: Verzeichnis existiert nicht: {photo_path}")
        return []

    all_photos = []
    new_photos = []
    skipped = 0

    for filename in sorted(os.listdir(photo_path)):
        full_path = os.path.join(photo_path, filename)

        # Nur Dateien, keine Unterordner
        if not os.path.isfile(full_path):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in extensions:
            continue

        all_photos.append(full_path)
        fp = _file_fingerprint(full_path)
        already = is_uploaded(db, full_path)

        if already:
            skipped += 1
            print(f"[SCAN] SKIP (bereits hochgeladen): {filename}  FP={fp[:12] if fp else '???'}...")
        else:
            new_photos.append(full_path)
            stat = os.stat(full_path)
            print(f"[SCAN] NEU:  {filename}  FP={fp[:12] if fp else '???'}...  Size={stat.st_size}  Mtime={stat.st_mtime}")

    print(f"[SCAN] Ergebnis: {len(all_photos)} Fotos total, {len(new_photos)} neu, {skipped} übersprungen")
    return new_photos


# ── API-Kommunikation ─────────────────────────────────────────────────

REQUEST_TIMEOUT = 30
UPLOAD_TIMEOUT = 120


def _api_headers(config):
    """Gibt die Standard-API-Headers zurück."""
    return {
        "X-API-Key": config.get("api_key", ""),
        "User-Agent": "FotoboxUploader/1.0 (RaspberryPi)",
    }


def _api_url(config, path):
    """Baut die vollständige API-URL."""
    base = config.get("shop_url", "").rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def check_internet(shop_url):
    """Prüft ob der Shop erreichbar ist."""
    if not shop_url:
        return False
    try:
        resp = requests.head(shop_url, timeout=5, allow_redirects=True)
        return resp.status_code < 500
    except requests.RequestException:
        return False


def api_get_active_events(config):
    """Holt die Liste der aktiven Events vom Shop."""
    url = _api_url(config, "/api/events/active")
    print(f"[API] GET {url}")
    try:
        resp = requests.get(
            url,
            headers=_api_headers(config),
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()
        print(f"[API] Response: {resp.status_code} — {len(data.get('events', []))} Events")

        if resp.status_code == 200 and data.get("success"):
            return {"success": True, "events": data.get("events", [])}
        else:
            print(f"[API] FEHLER: {data.get('error', resp.status_code)}")
            return {"success": False, "error": data.get("error", f"HTTP {resp.status_code}")}

    except requests.ConnectionError:
        print("[API] FEHLER: Keine Verbindung")
        return {"success": False, "error": "Keine Verbindung zum Shop. Internet prüfen."}
    except requests.Timeout:
        print("[API] FEHLER: Timeout")
        return {"success": False, "error": "Zeitüberschreitung bei der Verbindung."}
    except Exception as e:
        print(f"[API] FEHLER: {e}")
        return {"success": False, "error": str(e)}


def api_get_event_status(config, event_id):
    """Holt den Status eines einzelnen Events."""
    url = _api_url(config, f"/api/events/{event_id}/status")
    print(f"[API] GET {url}")
    try:
        resp = requests.get(
            url,
            headers=_api_headers(config),
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()
        print(f"[API] Response: {resp.status_code}")

        if resp.status_code == 200 and data.get("success"):
            return {"success": True, "event": data.get("event", {})}
        else:
            print(f"[API] FEHLER: {data.get('error', resp.status_code)}")
            return {"success": False, "error": data.get("error", f"HTTP {resp.status_code}")}

    except requests.ConnectionError:
        print("[API] FEHLER: Keine Verbindung")
        return {"success": False, "error": "Keine Verbindung zum Shop."}
    except requests.Timeout:
        print("[API] FEHLER: Timeout")
        return {"success": False, "error": "Zeitüberschreitung."}
    except Exception as e:
        print(f"[API] FEHLER: {e}")
        return {"success": False, "error": str(e)}


def api_upload_photo(config, event_id, photo_path):
    """Lädt ein einzelnes Foto zum Shop hoch."""
    filename = os.path.basename(photo_path)
    url = _api_url(config, f"/api/events/{event_id}/photos")
    filesize = os.path.getsize(photo_path)
    print(f"[UPLOAD] Start: {filename} ({filesize} bytes) -> Event {event_id}")
    print(f"[UPLOAD] URL: POST {url}")

    try:
        with open(photo_path, "rb") as f:
            files = {"photo": (filename, f)}
            resp = requests.post(
                url,
                headers=_api_headers(config),
                files=files,
                timeout=UPLOAD_TIMEOUT,
            )

        data = resp.json()

        if resp.status_code == 200 and data.get("success"):
            print(f"[UPLOAD] OK: {filename}")
            return {"success": True}
        else:
            error = data.get("error", f"HTTP {resp.status_code}")
            print(f"[UPLOAD] FEHLER: {filename} -> {resp.status_code}: {error}")
            return {"success": False, "error": error}

    except requests.ConnectionError:
        print(f"[UPLOAD] FEHLER: {filename} -> Keine Verbindung")
        return {"success": False, "error": "Keine Verbindung."}
    except requests.Timeout:
        print(f"[UPLOAD] FEHLER: {filename} -> Timeout nach {UPLOAD_TIMEOUT}s")
        return {"success": False, "error": "Upload-Zeitüberschreitung."}
    except Exception as e:
        print(f"[UPLOAD] FEHLER: {filename} -> {e}")
        return {"success": False, "error": str(e)}


def api_download_template(config, template_url, save_path):
    """Lädt das Draw.io Template-XML vom Shop herunter und speichert es lokal.

    Wird beim Event-Aktivieren aufgerufen, damit pibooth-picture-template
    das aktuelle Layout für das Event verwendet.

    Args:
        config:       Konfiguration (wird für API-Headers benötigt)
        template_url: Vollständige URL zum Template-XML (aus event.template_url)
        save_path:    Lokaler Dateipfad wo das XML gespeichert werden soll

    Returns:
        dict: {"success": True} oder {"success": False, "error": "..."}
    """
    print(f"[TEMPLATE] Download: {template_url}")
    print(f"[TEMPLATE] Speicherpfad: {save_path}")

    try:
        resp = requests.get(
            template_url,
            headers=_api_headers(config),
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            print(f"[TEMPLATE] FEHLER: HTTP {resp.status_code}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}

        xml_content = resp.text
        if "<mxfile" not in xml_content:
            print("[TEMPLATE] FEHLER: Kein gültiges Draw.io XML empfangen")
            return {"success": False, "error": "Kein gültiges Template-XML empfangen."}

        # Verzeichnis anlegen falls nicht vorhanden
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.isdir(save_dir):
            os.makedirs(save_dir, exist_ok=True)
            print(f"[TEMPLATE] Verzeichnis erstellt: {save_dir}")

        Path(save_path).write_text(xml_content, encoding="utf-8")
        print(f"[TEMPLATE] OK: {len(xml_content)} Zeichen -> {save_path}")
        return {"success": True}

    except requests.ConnectionError:
        print("[TEMPLATE] FEHLER: Keine Verbindung")
        return {"success": False, "error": "Keine Verbindung zum Shop."}
    except requests.Timeout:
        print("[TEMPLATE] FEHLER: Timeout")
        return {"success": False, "error": "Zeitüberschreitung beim Template-Download."}
    except OSError as e:
        print(f"[TEMPLATE] FEHLER beim Speichern: {e}")
        return {"success": False, "error": f"Datei konnte nicht gespeichert werden: {e}"}
    except Exception as e:
        print(f"[TEMPLATE] FEHLER: {e}")
        return {"success": False, "error": str(e)}
