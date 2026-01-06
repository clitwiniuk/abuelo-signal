#!/bin/bash
# Double-clickable macOS launcher – starts local TradeTally stack
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/tradetally/manage_tradetally.sh" start

# Keep Terminal window open so you can read output
read -n 1 -s -r -p "TradeTally iniciado. Pulsa cualquier tecla para cerrar la ventana…"
