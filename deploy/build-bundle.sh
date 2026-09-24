#!/usr/bin/env bash
# Construye un paquete OFFLINE de hermes-hudui para el clúster.
# Se ejecuta en una máquina de build con internet (Python 3.11+, Node 18+).
# El destino (CT/VM) NO necesita Node, npm ni acceso a PyPI.
#
# Uso: deploy/build-bundle.sh [salida.tar.gz]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml")"
OUT="${1:-$ROOT/hermes-hudui-$VERSION-bundle.tar.gz}"
PYTHON="${PYTHON:-python3}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "→ Compilando frontend (solo en la máquina de build)"
( cd "$ROOT/frontend" && npm ci --no-audit --no-fund && npm run build )
rm -rf "$ROOT/backend/static"
mkdir -p "$ROOT/backend/static"
cp -r "$ROOT/frontend/dist/." "$ROOT/backend/static/"

echo "→ Construyendo wheel + dependencias de ejecución"
STAGE="$WORK/hermes-hudui-$VERSION"
mkdir -p "$STAGE/wheels"
"$PYTHON" -m pip wheel --no-cache-dir -w "$STAGE/wheels" "$ROOT"

cp "$ROOT/deploy/install-offline.sh" \
   "$ROOT/deploy/hermes-hudui.service" \
   "$ROOT/deploy/hermes-hudui.env.example" \
   "$ROOT/deploy/nginx-hermes-hudui.conf.example" "$STAGE/"
( cd "$STAGE/wheels" && sha256sum ./*.whl > ../SHA256SUMS )

tar -C "$WORK" -czf "$OUT" "hermes-hudui-$VERSION"
echo "✔ Paquete: $OUT"
echo "  Nota: los wheels nativos (pillow, cryptography, watchfiles) son para"
echo "  $("$PYTHON" -c 'import platform,sys;print(platform.machine(),"py%d.%d"%sys.version_info[:2])')."
echo "  Construye con la misma arquitectura y versión de Python que el destino."
