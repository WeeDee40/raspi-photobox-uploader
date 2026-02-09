#!/bin/bash
#
# Fotobox Uploader — Installationsskript für Raspberry Pi
# Nutzung: bash install.sh
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_DIR="/home/patrick/photobox-uploader"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Fotobox Uploader — Installation         ${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 1. Python prüfen
echo -e "${BLUE}1. Python prüfen...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 nicht gefunden. Installiere mit: sudo apt install python3 python3-pip python3-venv${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}   $PYTHON_VERSION gefunden${NC}"

# 2. Verzeichnis einrichten
echo -e "${BLUE}2. Installationsverzeichnis: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"

# Dateien kopieren (falls nicht schon dort)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    echo "   Kopiere Dateien..."
    cp "$SCRIPT_DIR/app.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/uploader.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/templates" "$INSTALL_DIR/"
    # config.json nur kopieren wenn noch nicht vorhanden
    if [ ! -f "$INSTALL_DIR/config.json" ]; then
        cp "$SCRIPT_DIR/config.json" "$INSTALL_DIR/"
    else
        echo "   config.json existiert bereits, wird nicht überschrieben"
    fi
fi
echo -e "${GREEN}   Dateien installiert${NC}"

# 3. Virtual Environment
echo -e "${BLUE}3. Python Virtual Environment...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    echo -e "${GREEN}   venv erstellt${NC}"
else
    echo "   venv existiert bereits"
fi

# 4. Dependencies installieren
echo -e "${BLUE}4. Python-Pakete installieren...${NC}"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo -e "${GREEN}   Pakete installiert${NC}"

# 5. Systemd Service
echo -e "${BLUE}5. Systemd Service einrichten...${NC}"
sudo cp "$SCRIPT_DIR/photobox-uploader.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable photobox-uploader.service
echo -e "${GREEN}   Service aktiviert (startet bei Boot)${NC}"

# 6. Service starten
echo -e "${BLUE}6. Service starten...${NC}"
sudo systemctl restart photobox-uploader.service
sleep 2

if systemctl is-active --quiet photobox-uploader.service; then
    echo -e "${GREEN}   Service läuft!${NC}"
else
    echo -e "${RED}   Service konnte nicht gestartet werden.${NC}"
    echo "   Prüfe mit: sudo journalctl -u photobox-uploader.service -f"
fi

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}  Installation abgeschlossen!${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo -e "  Webinterface: ${GREEN}http://localhost:5000${NC}"
echo -e "  Oder im Netzwerk: ${GREEN}http://$(hostname -I | awk '{print $1}'):5000${NC}"
echo ""
echo -e "  Nächste Schritte:"
echo -e "  1. Öffne http://localhost:5000/settings"
echo -e "  2. Trage Shop-URL und API-Key ein"
echo -e "  3. Wähle ein Event aus und starte den Upload"
echo ""
echo -e "  Service-Befehle:"
echo -e "    sudo systemctl status photobox-uploader"
echo -e "    sudo systemctl restart photobox-uploader"
echo -e "    sudo journalctl -u photobox-uploader -f"
echo ""
