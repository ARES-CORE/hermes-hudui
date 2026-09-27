#!/usr/bin/env bash
# Driver de hermes-hudui para agentes. Ejecutar desde la raíz del repo.
#   setup            venv .venv + frontend compilado a backend/static
#   start [port]     arranca en segundo plano con datos de prueba y modo offline
#   smoke            comprueba API, perfil, skills y bloqueo offline (403)
#   shot <png> [tab] captura la UI con Chromium (tab: dashboard|memory|skills|profiles)
#   stop             para el servidor
#   logs             últimas líneas del log
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
RUN=.hud-run; mkdir -p "$RUN"
PORT="$(cat "$RUN/port" 2>/dev/null || echo "${2:-3099}")"
BASE="http://127.0.0.1:$PORT"

fixture() {  # HERMES_HOME mínimo y sin secretos
  local h="$RUN/hermes"; mkdir -p "$h/memories" "$h/skills/devops/demo-skill"
  printf '# Agente de prueba\n\nSoy el agente de prueba del driver.\n' > "$h/SOUL.md"
  printf 'Entrada de memoria uno.\n§\nEntrada de memoria dos.\n' > "$h/memories/MEMORY.md"
  printf 'Preferencia del operador.\n' > "$h/memories/USER.md"
  printf -- '---\nname: demo-skill\ndescription: Skill de prueba del driver.\n---\n# demo\n' > "$h/skills/devops/demo-skill/SKILL.md"
  printf 'model:\n  provider: anthropic\n  default: test-model\ntoolsets:\n  - terminal\n  - file\n' > "$h/config.yaml"
  echo "$PWD/$h"
}

case "${1:-}" in
  setup)
    python3 -m venv .venv
    .venv/bin/pip install -q -e . httpx pytest
    (cd frontend && npm ci --no-audit --no-fund --silent && npm run build --silent)
    rm -rf backend/static && mkdir -p backend/static && cp -r frontend/dist/. backend/static/
    echo "setup ok" ;;
  start)
    PORT="${2:-3099}"; echo "$PORT" > "$RUN/port"
    HOME_DIR="${HERMES_HOME:-$(fixture)}"
    HERMES_HOME="$HOME_DIR" HERMES_HUD_OFFLINE=1 setsid nohup .venv/bin/hermes-hudui \
      --host 127.0.0.1 --port "$PORT" > "$RUN/server.log" 2>&1 < /dev/null &
    echo $! > "$RUN/pid"
    for _ in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.5; done
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/health" && echo "up: http://127.0.0.1:$PORT (HERMES_HOME=$HOME_DIR)" \
      || { echo "no arrancó"; tail -20 "$RUN/server.log"; exit 1; } ;;
  smoke)
    fail=0
    chk() { local want="$1" method="$2" path="$3" got
      got=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" "$BASE$path")
      if [ "$got" = "$want" ]; then echo "ok   $method $path -> $got"; else echo "FAIL $method $path -> $got (esperado $want)"; fail=1; fi; }
    chk 200 GET /
    chk 200 GET /api/health
    chk 200 GET /api/profiles
    chk 200 GET /api/skills
    chk 200 GET /api/memory
    chk 403 POST /api/hermes/update
    chk 403 POST /api/plugins/install
    chk 403 POST /api/chat/sessions/x/send
    curl -s "$BASE/api/profiles" | python3 -c "import sys,json;p=json.load(sys.stdin)['profiles'][0];print('perfil:',p['model'],p['toolsets'],'|',p['soul_summary'][:40])"
    exit $fail ;;
  shot)
    OUT="${2:?uso: shot <archivo.png> [tab]}"; TAB="${3:-dashboard}"
    node "$(dirname "$0")/shot.mjs" "$BASE" "$OUT" "$TAB" ;;
  stop)
    [ -f "$RUN/pid" ] && kill "$(cat "$RUN/pid")" 2>/dev/null || true; rm -f "$RUN/pid"; echo "stopped" ;;
  logs) tail -n 40 "$RUN/server.log" ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
