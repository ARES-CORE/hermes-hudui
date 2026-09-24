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

## 3. Publicar

El HUD **no tiene autenticación propia** y escucha en `127.0.0.1:3001`.
Publícalo solo detrás de nginx con TLS y autenticación
(`nginx-hermes-hudui.conf.example`). El archivo `htpasswd` y los certificados se
crean en el host y nunca se versionan.

Opciones de instalación: `PREFIX`, `SVC_USER`, `PYTHON`.
