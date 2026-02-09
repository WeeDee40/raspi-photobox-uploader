#!/usr/bin/env python3
"""
Fotobox Uploader — Flask Webinterface
Läuft auf http://localhost:5000 auf dem Raspberry Pi.
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, jsonify

from uploader import (
    load_config,
    load_raw_config,
    save_config,
    api_get_active_events,
    api_get_event_status,
    api_upload_photo,
    get_new_photos,
    init_db,
    mark_uploaded,
    get_upload_stats,
    check_internet,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "uploads.db"
STATE_PATH = BASE_DIR / "active_event.json"

app = Flask(__name__)

# ── Upload-Status (für Fortschrittsanzeige) ──────────────────────────
upload_status = {
    "running": False,
    "total": 0,
    "done": 0,
    "failed": 0,
    "current_file": "",
    "message": "",
}


def load_active_event():
    """Lädt das aktuell aktivierte Event aus der lokalen Datei."""
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text())
            if data.get("id"):
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def save_active_event(event):
    """Speichert das aktivierte Event lokal."""
    STATE_PATH.write_text(json.dumps(event, ensure_ascii=False, indent=2))


def clear_active_event():
    """Entfernt das aktivierte Event."""
    if STATE_PATH.exists():
        STATE_PATH.unlink()


# ── Routes ────────────────────────────────────────────────────────────


@app.route("/")
def index():
    config = load_config(CONFIG_PATH)
    event = load_active_event()
    stats = get_upload_stats(DB_PATH)
    configured = config.get("api_key", "") != ""
    internet = check_internet(config.get("shop_url", ""))
    return render_template(
        "index.html",
        event=event,
        config=config,
        stats=stats,
        configured=configured,
        internet=internet,
        upload_status=upload_status,
    )


@app.route("/events")
def events():
    config = load_config(CONFIG_PATH)
    error = None
    events_list = []

    if config.get("api_key", "") == "":
        error = "Kein API-Key konfiguriert. Bitte zuerst unter Einstellungen eintragen."
    else:
        result = api_get_active_events(config)
        if result["success"]:
            events_list = result["events"]
        else:
            error = result["error"]

    return render_template("events.html", events=events_list, error=error, config=config)


@app.route("/activate/<int:event_id>")
def activate(event_id):
    config = load_config(CONFIG_PATH)
    result = api_get_event_status(config, event_id)

    if result["success"]:
        save_active_event(result["event"])
    return redirect(url_for("index"))


@app.route("/deactivate")
def deactivate():
    clear_active_event()
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload():
    """Startet den Upload-Prozess in einem Hintergrund-Thread."""
    if upload_status["running"]:
        return redirect(url_for("index"))

    config = load_config(CONFIG_PATH)
    event = load_active_event()

    if not event:
        return redirect(url_for("index"))

    # Upload in Background-Thread starten
    thread = threading.Thread(
        target=run_upload, args=(config, event), daemon=True
    )
    thread.start()
    return redirect(url_for("index"))


@app.route("/api/upload-status")
def api_upload_status():
    """AJAX-Endpoint für Live-Fortschritt."""
    return jsonify(upload_status)


@app.route("/switch-env/<env_name>")
def switch_env(env_name):
    """Schneller Umgebungs-Wechsel (Navbar-Toggle)."""
    raw_config = load_raw_config(CONFIG_PATH)
    if env_name in raw_config.get("environments", {}):
        raw_config["active_environment"] = env_name
        save_config(CONFIG_PATH, raw_config)
        clear_active_event()
        print(f"[CONFIG] Umgebung gewechselt -> {env_name}")
    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        raw_config = load_raw_config(CONFIG_PATH)

        # Aktive Umgebung
        raw_config["active_environment"] = request.form.get(
            "active_environment", "production"
        )

        # Per-Umgebung API-Keys
        for env_key in raw_config.get("environments", {}):
            key_field = f"api_key_{env_key}"
            if key_field in request.form:
                raw_config["environments"][env_key]["api_key"] = request.form.get(
                    key_field, ""
                )

        # Gemeinsame Einstellungen
        raw_config["photo_path"] = request.form.get("photo_path", "")
        raw_config["check_interval"] = int(
            request.form.get("check_interval", 60)
        )

        save_config(CONFIG_PATH, raw_config)
        return redirect(url_for("settings"))

    config = load_config(CONFIG_PATH)
    return render_template("settings.html", config=config)


# ── Upload-Logik ─────────────────────────────────────────────────────


def run_upload(config, event):
    """Führt den Upload aller neuen Fotos durch."""
    global upload_status

    event_id = event["id"]
    event_name = event.get("event_name", "?")
    print(f"\n{'='*60}")
    print(f"[UPLOAD-JOB] Start für Event {event_id}: {event_name}")
    print(f"[UPLOAD-JOB] Shop: {config.get('shop_url')}")
    print(f"[UPLOAD-JOB] Foto-Pfad: {config.get('photo_path')}")
    print(f"{'='*60}")

    upload_status["running"] = True
    upload_status["done"] = 0
    upload_status["failed"] = 0
    upload_status["message"] = "Suche neue Fotos..."
    upload_status["current_file"] = ""

    try:
        db = init_db(DB_PATH)
        new_photos = get_new_photos(db, config)
        upload_status["total"] = len(new_photos)

        if not new_photos:
            print("[UPLOAD-JOB] Keine neuen Fotos gefunden. Fertig.")
            upload_status["message"] = "Keine neuen Fotos gefunden."
            time.sleep(2)
            return

        print(f"[UPLOAD-JOB] Starte Upload von {len(new_photos)} Fotos...")
        upload_status["message"] = f"{len(new_photos)} neue Fotos gefunden."

        for i, photo_path in enumerate(new_photos, 1):
            filename = os.path.basename(photo_path)
            upload_status["current_file"] = filename
            upload_status["message"] = f"Lade hoch: {filename} ({i}/{len(new_photos)})"
            print(f"\n[UPLOAD-JOB] --- Foto {i}/{len(new_photos)} ---")

            result = api_upload_photo(config, event_id, photo_path)

            if result["success"]:
                mark_uploaded(db, photo_path, event_id)
                upload_status["done"] += 1
            else:
                upload_status["failed"] += 1
                print(f"[UPLOAD-JOB] FEHLGESCHLAGEN: {filename} -> {result.get('error')}")

        done = upload_status["done"]
        failed = upload_status["failed"]
        upload_status["message"] = f"Fertig! {done} hochgeladen, {failed} fehlgeschlagen."
        upload_status["current_file"] = ""
        db.close()

        print(f"\n{'='*60}")
        print(f"[UPLOAD-JOB] FERTIG: {done} OK, {failed} fehlgeschlagen")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"[UPLOAD-JOB] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        upload_status["message"] = f"Fehler: {str(e)}"
    finally:
        upload_status["running"] = False


# ── Start ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db(DB_PATH)
    app.run(host="0.0.0.0", port=5000, debug=False)
