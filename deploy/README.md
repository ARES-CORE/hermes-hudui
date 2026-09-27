# Despliegue offline en clúster

Paquete autocontenido: el destino **no necesita Node.js, npm ni acceso a PyPI**.
El frontend se compila una vez en la máquina de build y viaja como estáticos
dentro del wheel; todas las dependencias Python viajan como wheels verificados
por SHA-256.

## 1. Construir (máquina con internet, Python 3.11+ y Node 18+)

Usa la misma arquitectura y versión de Python que el destino (hay wheels nativos).

```bash
deploy/build-bundle.sh               # → hermes-hudui-<ver>-bundle.tar.gz
```

## 2. Instalar (en el CT/VM destino, como root)

Requisito del destino: Python 3.11+ con `venv`.

```bash
tar -xzf hermes-hudui-*-bundle.tar.gz
cd hermes-hudui-*/ && ./install-offline.sh
```

Resultado:

- `/opt/hermes-hudui/venv` — aplicación instalada con `pip --no-index`
- `/etc/hermes-hudui/hermes-hudui.env` — configuración (sin secretos)
- `hermes-hudui.service` — systemd endurecido, usuario sin privilegios `hermes`

## Sin salidas a externos

Dos capas, activas por defecto:

- `HERMES_HUD_OFFLINE=1` (en el `.env` del servicio): la API responde 403 a las
  acciones que abrirían conexiones externas (actualizar hermes, instalar/actualizar
  plugins, gateway, chat y cron contra proveedores LLM).
- systemd `IPAddressDeny=any` + `IPAddressAllow=localhost`: el kernel bloquea
  cualquier conexión del servicio (y de sus procesos hijos) fuera de localhost.

## 3. Publicar

El HUD **no tiene autenticación propia** y escucha en `127.0.0.1:3001`.
Publícalo solo detrás de nginx con TLS y autenticación
(`nginx-hermes-hudui.conf.example`). El archivo `htpasswd` y los certificados se
crean en el host y nunca se versionan.

Opciones de instalación: `PREFIX`, `SVC_USER`, `PYTHON` y `HERMES_HOME`.

### Directorio de datos personalizado

Por defecto el HUD lee `~hermes/.hermes`. Para que el agente viva en un directorio
propio (más fácil de respaldar y fuera de `/home`):

```bash
HERMES_HOME=/srv/<agente> ./install-offline.sh
```

El servicio queda con `HERMES_HOME` apuntando ahí y con permiso de escritura solo
sobre ese directorio y `~/.hermes-hud`.
