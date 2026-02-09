# PiBooth Setup-Anleitung

Anleitung für die Installation und Konfiguration von [PiBooth](https://github.com/pibooth/pibooth) auf dem Raspberry Pi, inklusive Integration mit dem Fotobox Uploader.

## PiBooth installieren

### Voraussetzungen

- Raspberry Pi 3B+ oder neuer
- Raspberry Pi OS (Bookworm oder Bullseye)
- Kamera (Pi Camera Module oder USB-Kamera)
- Touchscreen oder Monitor + Maus

### Installation

```bash
# System-Pakete
sudo apt update
sudo apt install -y python3-pip python3-venv libsdl2-dev libsdl2-image-dev \
    libsdl2-mixer-dev libsdl2-ttf-dev libcups2-dev

# PiBooth installieren
pip3 install pibooth
```

### Erster Start

```bash
pibooth
```

Beim ersten Start wird `~/.config/pibooth/pibooth.cfg` erstellt.

## Empfohlene PiBooth-Konfiguration

Bearbeite `~/.config/pibooth/pibooth.cfg`:

```ini
[GENERAL]
# Sprache
language = de

# Anzahl Fotos pro Session
captures = (1 2 3 4)

[CAMERA]
# Kamera-Auflösung
resolution = (2592, 1944)

[PICTURE]
# Ausgabe-Verzeichnis (= photo_path im Uploader!)
directory = /home/patrick/pibooth

# Foto-Orientierung
orientation = auto

# Hintergrund-Farbe
bg_color = (255, 255, 255)

[WINDOW]
# Fullscreen auf dem Touchscreen
fullscreen = true
```

### Wichtig: Ausgabe-Verzeichnis

Das `directory` in PiBooth muss dem `photo_path` in der Uploader-Config entsprechen:

```
PiBooth:  directory = /home/patrick/pibooth
Uploader: "photo_path": "/home/patrick/pibooth"
```

## PiBooth-Ordnerstruktur

PiBooth erstellt folgende Unterordner:

```
/home/patrick/pibooth/
├── photo_001.jpg          # Fertige Fotos (werden hochgeladen)
├── photo_002.jpg
├── raw/                   # Original-Aufnahmen (vor Effekten)
│   ├── photo_001.jpg
│   └── ...
└── forget/                # Von Gästen gelöschte Fotos
    ├── photo_005.jpg
    └── ...
```

Der Uploader scannt **nur das Hauptverzeichnis** — `raw/` und `forget/` werden automatisch ignoriert.

## PiBooth als Service einrichten

```bash
# Service-Datei erstellen
sudo nano /etc/systemd/system/pibooth.service
```

```ini
[Unit]
Description=PiBooth Fotobox
After=graphical.target

[Service]
Type=simple
User=patrick
Environment=DISPLAY=:0
ExecStart=/usr/local/bin/pibooth
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pibooth.service
sudo systemctl start pibooth.service
```

## Typischer Workflow am Event

1. Raspberry Pi einschalten (PiBooth + Uploader starten automatisch)
2. Im Browser `http://localhost:5000` öffnen
3. Event auswählen
4. Gäste machen Fotos an der PiBooth
5. Regelmässig "Fotos hochladen" klicken (oder am Ende des Events)
6. Fotos erscheinen in der Event-Galerie im Shop

## Troubleshooting

### Kamera wird nicht erkannt
```bash
# Pi Camera testen
libcamera-hello

# USB-Kamera testen
lsusb
```

### PiBooth startet nicht im Fullscreen
```bash
# X-Server Rechte setzen
xhost +local:
```

### Fotos werden nicht im richtigen Ordner gespeichert
```bash
# PiBooth-Config prüfen
cat ~/.config/pibooth/pibooth.cfg | grep directory
```
