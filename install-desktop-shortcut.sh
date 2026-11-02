#!/usr/bin/env bash
set -euo pipefail
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.local/share/applications"
FILE="$HOME/.local/share/applications/superior-mi-python-visual-programming-lab.desktop"
cat > "$FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Superior MI Python Visual Programming Lab
Comment=Python source visual programming sandbox in native Qt
Exec=$APP/launch-linux.sh
Path=$APP
Terminal=false
Categories=Development;Graphics;
Icon=applications-development
StartupNotify=true
EOF
chmod +x "$FILE"
echo "Installed application shortcut: $FILE"
