# Fotobox Uploader

Upload-Tool für den Raspberry Pi: Fotos von der PiBooth-Fotobox automatisch zum [Rent4Events-Shop](https://rent4events.ch) hochladen.

## Features

- Web-Interface auf `http://localhost:5000` (Dark Theme)
- Ein-Klick Umgebungs-Wechsel zwischen Produktiv und Q-System (Test)
- Event-Auswahl aus dem Shop (nur aktive/geplante Events)
- Foto-Upload mit Live-Fortschrittsanzeige
- Globales Tracking: jedes Foto wird nur einmal hochgeladen
- PiBooth-kompatibel: ignoriert `raw/` und `forget/` Unterordner

## Voraussetzungen

- Raspberry Pi (3B+ oder neuer) mit Raspberry Pi OS
- Python 3.7+
- Internet-Verbindung (WLAN oder LAN)
- [PiBooth](https://github.com/pibooth/pibooth) installiert und konfiguriert
- API-Key aus dem Shop (Admin > API / Raspberry Pi)

## Installation

### 1. Repository klonen

```bash
git clone git@github.com:WeeDee40/photobox-uploader.git ~/photobox-uploader
cd ~/photobox-uploader
```

### 2. Konfiguration anlegen

```bash
cp config.json.example config.json
nano config.json
```

API-Keys aus dem Shop-Admin eintragen:
- **Produktiv-Key**: Admin > API / Raspberry Pi > Produktiv API-Key
- **Test-Key**: Admin > API / Raspberry Pi > Test API-Key

`photo_path` auf das PiBooth-Ausgabeverzeichnis setzen (z.B. `/home/patrick/pibooth`).

### 3. Installationsskript ausführen

```bash
bash install.sh
```

Das Skript:
- Erstellt ein Python Virtual Environment
- Installiert alle Dependencies (Flask, requests)
- Richtet einen Systemd-Service ein (Autostart bei Boot)
- Startet das Web-Interface

### 4. Konfiguration im Browser

Öffne **http://localhost:5000/settings** und prüfe die Einstellungen.

## Benutzung

1. Im Browser `http://localhost:5000` öffnen
2. **Event auswählen** aus der Liste aktiver Events
3. **Fotos jetzt hochladen** klicken
4. Fortschritt live verfolgen

### Umgebung wechseln

In der Navbar: `[Prod] [Test]` Toggle-Buttons. Ein Klick wechselt die Umgebung (aktives Event wird dabei deaktiviert).

Oder unter Einstellungen: Umgebungs-Karte anklicken und speichern.

## Deployment (Updates)

```bash
cd ~/photobox-uploader
git pull
sudo systemctl restart photobox-uploader
```

Die `config.json` wird durch `git pull` nicht überschrieben (in `.gitignore`).

## Service-Befehle

```bash
# Status prüfen
sudo systemctl status photobox-uploader

# Neustarten
sudo systemctl restart photobox-uploader

# Logs ansehen (live)
sudo journalctl -u photobox-uploader -f

# Letzte 50 Log-Zeilen
sudo journalctl -u photobox-uploader -n 50

# Service stoppen
sudo systemctl stop photobox-uploader
```

## Dateien

```
photobox-uploader/
├── app.py                     # Flask Web-Interface
├── uploader.py                # API-Kommunikation & Upload-Logik
├── config.json                # Konfiguration (nicht im Git!)
├── config.json.example        # Vorlage für config.json
├── requirements.txt           # Python Dependencies
├── install.sh                 # Installationsskript
├── photobox-uploader.service  # Systemd Service-Definition
├── uploads.db                 # SQLite Tracking-DB (automatisch erstellt)
├── active_event.json          # Aktuell aktiviertes Event (automatisch)
└── templates/
    ├── base.html              # Basis-Template (Dark Theme, Navbar)
    ├── index.html             # Startseite (Event, Upload, Stats)
    ├── events.html            # Event-Auswahl
    └── settings.html          # Einstellungen + Umgebungs-Wechsel
```

## Troubleshooting

### "Keine Verbindung zum Shop"
- Internet prüfen: `ping rent4events.ch`
- Shop-URL in Einstellungen prüfen
- Firewall/Proxy-Einstellungen des Netzwerks

### "Ungültiger API-Key" (403)
- Key im Shop-Admin unter API / Raspberry Pi prüfen
- Key komplett kopieren (64 Zeichen)
- Richtiger Key für die Umgebung? (Prod-Key für Prod, Test-Key für Test)

### "Keine neuen Fotos gefunden"
- Foto-Verzeichnis in Einstellungen prüfen
- Fotos vorhanden? `ls /home/patrick/pibooth/*.jpg`
- Bereits hochgeladen? Tracking zurücksetzen: `rm ~/photobox-uploader/uploads.db`

### Service startet nicht
```bash
# Detaillierte Fehlerausgabe
sudo journalctl -u photobox-uploader -n 50

# Manuell testen
cd ~/photobox-uploader
venv/bin/python app.py
```

### Config-Migration
Alte Flat-Configs (ohne `environments`) werden beim ersten Start automatisch migriert. Der bestehende API-Key wird der passenden Umgebung zugeordnet.
