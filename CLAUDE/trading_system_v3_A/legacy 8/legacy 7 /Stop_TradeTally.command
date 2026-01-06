#!/bin/bash
# Double-clickable macOS stopper – stops local TradeTally stack
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/tradetally/manage_tradetally.sh" stop
read -n 1 -s -r -p "TradeTally detenido. Pulsa cualquier tecla para cerrar la ventana…"
