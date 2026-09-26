#!/usr/bin/env bash
# Instala hermes-hudui desde el paquete offline (sin internet).
# Ejecutar como root dentro del CT/VM destino, desde el directorio extraído.
set -euo pipefail
# El venv lo ejecuta el usuario del servicio: no heredar un umask restrictivo del llamador.
umask 022

PREFIX="${PREFIX:-/opt/hermes-hudui}"
SVC_USER="${SVC_USER:-hermes}"
PYTHON="${PYTHON:-python3}"
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "✗ Ejecutar como root"; exit 1; }
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "✗ Se requiere Python 3.11+"; exit 1; }

echo "→ Verificando integridad de wheels"
( cd "$HERE/wheels" && sha256sum -c --quiet ../SHA256SUMS )

id "$SVC_USER" &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin \
  $(getent group "$SVC_USER" >/dev/null && echo "-g $SVC_USER") "$SVC_USER"
SVC_HOME="$(getent passwd "$SVC_USER" | cut -d: -f6)"
# Directorio de datos del agente: ~/.hermes o uno personalizado (p. ej. /srv/<agente>).
DATA_DIR="${HERMES_HOME:-$SVC_HOME/.hermes}"
# systemd exige que ReadWritePaths exista antes de arrancar.
install -d -m 0750 -o "$SVC_USER" -g "$SVC_USER" "$DATA_DIR" "$SVC_HOME/.hermes-hud"

echo "→ Instalando en $PREFIX (sin índice remoto)"
"$PYTHON" -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --no-index --no-cache-dir --find-links "$HERE/wheels" hermes-hudui

install -d -m 0750 -o root -g "$SVC_USER" /etc/hermes-hudui
if [ ! -f /etc/hermes-hudui/hermes-hudui.env ]; then
  install -m 0640 -o root -g "$SVC_USER" "$HERE/hermes-hudui.env.example" /etc/hermes-hudui/hermes-hudui.env
  sed -i "s|^HERMES_HOME=.*|HERMES_HOME=$DATA_DIR|" /etc/hermes-hudui/hermes-hudui.env
fi
install -m 0644 "$HERE/hermes-hudui.service" /etc/systemd/system/hermes-hudui.service
sed -i "s|^User=.*|User=$SVC_USER|;s|^Group=.*|Group=$SVC_USER|" /etc/systemd/system/hermes-hudui.service
sed -i "s|^ReadWritePaths=.*|ReadWritePaths=$DATA_DIR $SVC_HOME/.hermes-hud|" /etc/systemd/system/hermes-hudui.service

systemctl daemon-reload
systemctl enable --now hermes-hudui
sleep 2
systemctl --no-pager --lines=5 status hermes-hudui || true
echo "✔ Instalado. Revisa /etc/hermes-hudui/hermes-hudui.env y publica detrás de nginx."
