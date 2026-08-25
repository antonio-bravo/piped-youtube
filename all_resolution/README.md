# Piped en QNAP — Arquitectura y despliegue

## 1. Objetivo

Instalación de Piped en un QNAP mediante Docker Compose, con:

- PostgreSQL para persistencia.
- Piped Backend.
- Piped Frontend.
- `piped-proxy` para el proxy de medios.
- Resolver personalizado basado en `yt-dlp`.
- BGUTIL como proveedor de PO Tokens.
- Nginx como punto de entrada y reverse proxy.

La instalación está planteada para una red LAN.

---

## 2. Arquitectura

```text
                         ┌─────────────────────────┐
                         │       Navegador          │
                         │   http://piped.home      │
                         │          :18080          │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │         NGINX           │
                         │     piped-nginx         │
                         │       :80 interno       │
                         │      :18080 externo     │
                         └──────┬──────┬───────┬───┘
                                │      │       │
                ┌───────────────┘      │       └────────────────┐
                ▼                      ▼                        ▼
       ┌─────────────────┐    ┌─────────────────┐     ┌─────────────────┐
       │ Piped Frontend  │    │ Piped Backend   │     │  Piped Proxy    │
       │ piped-frontend  │    │ piped-backend   │     │  piped-proxy    │
       └─────────────────┘    └────────┬────────┘     └────────┬────────┘
                                       │                       │
                                       ▼                       │
                              ┌─────────────────┐              │
                              │   PostgreSQL    │              │
                              │  piped-postgres │              │
                              └─────────────────┘              │
                                                               │
                                                               ▼
                                                         ┌──────────┐
                                                         │ YouTube  │
                                                         │googlevideo│
                                                         └──────────┘

        Extracción:

        Backend
           │
           ▼
      piped-resolver
        │        │
        │        └────────► piped-bgutil ──► PO Tokens
        │
        └────────────────► YouTube / yt-dlp
```

---

## 3. Servicios Docker

| Servicio | Imagen | Función |
|---|---|---|
| `postgres` | `postgres:15-alpine` | Base de datos |
| `piped-bgutil` | `brainicism/bgutil-ytdlp-pot-provider:1.3.1` | PO Tokens |
| `piped-resolver` | `ghcr.io/antonio-bravo/piped-youtube/piped-resolver:latest` | Resolución con yt-dlp |
| `piped-backend` | `1337kavin/piped:latest` | API/backend |
| `piped-proxy` | `1337kavin/piped-proxy:latest` | Proxy de medios |
| `piped-frontend` | `1337kavin/piped-frontend:latest` | Interfaz web |
| `nginx` | `nginx:mainline-alpine` | Reverse proxy y routing |

Todos utilizan la red Docker `piped`.

---

## 4. Flujo de reproducción

```text
Navegador
   │
   ▼
piped.home:18080
   │
   ▼
Nginx
   │
   ▼
Frontend
   │
   ▼
Backend
   │
   ▼
piped-resolver
   ├──► piped-bgutil ──► PO Token
   └──► YouTube / yt-dlp
             │
             ▼
       videoStreams
       audioStreams
             │
             ▼
         Frontend
             │
             ▼
     pipedproxy.home:18080
             │
             ▼
           Nginx
             │
             ▼
       piped-proxy
             │
             ▼
        googlevideo
```

---

## 5. PostgreSQL

Contenedor:

```text
piped-postgres
```

Imagen:

```text
postgres:15-alpine
```

Base de datos:

```text
piped
```

Usuario:

```text
piped
```

Persistencia:

```text
/share/Container/piped/data/postgres
    ↓
/var/lib/postgresql/data
```

Healthcheck:

```bash
pg_isready -U piped -d piped
```

El backend espera a que PostgreSQL esté saludable.

---

## 6. BGUTIL

Imagen:

```text
brainicism/bgutil-ytdlp-pot-provider:1.3.1
```

Contenedor:

```text
piped-bgutil
```

El resolver utiliza:

```text
BGUTIL_BASE_URL=http://piped-bgutil:4416
```

El backend mantiene además:

```properties
yt_dl_pot_provider_url=http://piped-bgutil:8080
```

Estos valores pertenecen a las configuraciones de sus respectivos consumidores.

---

## 7. Piped Resolver

Imagen:

```text
ghcr.io/antonio-bravo/piped-youtube/piped-resolver:latest
```

Contenedor:

```text
piped-resolver
```

Puerto:

```text
8000
```

Variables importantes:

```yaml
RESOLVER_HOST: "0.0.0.0"
RESOLVER_PORT: "8000"

PROXY_URL: "http://pipedproxy.home:18080"

CACHE_TTL: "3600"
CACHE_MAXSIZE: "512"

ALLOWED_ORIGINS: "*"

BGUTIL_BASE_URL: "http://piped-bgutil:4416"
```

### Importante: `PROXY_URL`

El código Python del resolver lee:

```python
os.getenv("PROXY_URL", "")
```

Por tanto, la variable correcta es:

```text
PROXY_URL
```

y no:

```text
PIPED_RESOLVER_PROXY_URL
```

Esto es importante porque `PROXY_URL` determina el campo:

```json
"proxyUrl": "http://pipedproxy.home:18080"
```

de la respuesta `/streams`.

---

## 8. Endpoints del resolver

```text
GET /healthcheck
GET /streams/{video_id}
GET /search
```

Ejemplo:

```bash
curl -s http://piped-resolver:8000/streams/TZuGrNFLyWE
```

La respuesta contiene:

```json
{
  "videoStreams": [],
  "audioStreams": [],
  "proxyUrl": "http://pipedproxy.home:18080"
}
```

---

## 9. yt-dlp

El resolver utiliza `yt-dlp` para obtener información y URLs de medios.

Características:

```python
"skip_download": True
"noplaylist": True
"remote_components": ["ejs:github"]
```

BGUTIL se conecta mediante:

```python
"youtubepot-bgutilhttp": {
    "base_url": [config.bgutil_base_url]
}
```

Los `player_client` no se fuerzan si `YTDLP_PLAYER_CLIENTS` está vacío.

---

## 10. Streams adaptativos

El resolver separa:

```text
videoStreams
audioStreams
```

Los vídeos adaptativos pueden aparecer como:

```text
videoOnly = true
```

Durante las pruebas se obtuvieron, entre otros:

```text
144p   itag 160   video/mp4
144p   itag 278   video/webm
240p   itag 133   video/mp4
360p   itag 134   video/mp4
480p   itag 135   video/mp4
720p   itag 298   video/mp4
1080p  itag 299   video/mp4
```

También se obtuvieron cuatro streams de audio.

Una URL directa de `googlevideo.com` respondió:

```text
HTTP 206 Partial Content
Content-Type: video/mp4
Content-Range: bytes 0-1023/2771561
```

Esto demuestra que la extracción de la URL de vídeo funciona.

---

## 11. SegmentBase y rangos DASH

Cuando `PROXY_URL` está configurado, el resolver intenta obtener rangos de bytes de los formatos adaptativos mediante:

```python
attach_segment_ranges(adaptive)
```

Los formatos sin `_segment_range` pueden descartarse cuando se utiliza el frontend/proxy.

Esto permite generar información compatible con la reproducción adaptativa de Piped.

---

## 12. Piped Backend

Imagen:

```text
1337kavin/piped:latest
```

Contenedor:

```text
piped-backend
```

Puerto interno:

```text
8080
```

Configuración:

```text
/share/Container/piped/config/config.properties
    ↓
/app/config.properties
```

Resolver:

```properties
video_resolver_url=http://piped-resolver:8000
```

Base de datos:

```properties
hibernate.connection.url:jdbc:postgresql://postgres:5432/piped
```

---

## 13. Configuración del backend

```properties
PORT:8080
HTTP_WORKERS:2

PROXY_PART:http://pipedproxy.home:18080
API_URL:http://pipedapi.home:18080
FRONTEND_URL:http://piped.home:18080

BGUTIL_BASE_URL:http://piped-bgutil:4416

COMPATIBLE_VIDEO_LINKS=true

COMPROMISED_PASSWORD_CHECK:true
DISABLE_REGISTRATION:false
FEED_RETENTION:30
DISABLE_TIMERS:true

RYD_PROXY_URL:https://ryd-proxy.kavin.rocks
DISABLE_RYD:false

SPONSORBLOCK_SERVERS:https://sponsor.ajay.app,https://sponsorblock.kavin.rocks

DISABLE_LBRY:false
SUBSCRIPTIONS_EXPIRY:30
CONSENT_COOKIE:true
DISABLE_SERVER:false

hibernate.connection.url:jdbc:postgresql://postgres:5432/piped
hibernate.connection.driver_class:org.postgresql.Driver
hibernate.dialect:org.hibernate.dialect.PostgreSQLDialect
hibernate.connection.username:piped
hibernate.connection.password:Piped-QNAP-xxxx-ChangeMe

video_resolver_url=http://piped-resolver:8000
yt_dl_pot_provider_url=http://piped-bgutil:8080
```

---

## 14. Piped Proxy

Imagen:

```text
1337kavin/piped-proxy:latest
```

Contenedor:

```text
piped-proxy
```

Configuración:

```yaml
UDS: "0"
```

Puerto interno:

```text
8080
```

Nginx lo alcanza mediante:

```text
piped-proxy:8080
```

---

## 15. Frontend

Imagen:

```text
1337kavin/piped-frontend:latest
```

Contenedor:

```text
piped-frontend
```

Configuración:

```yaml
BACKEND_HOSTNAME: "pipedapi.home:18080"
HTTP_MODE: "http"
```

---

## 16. Nginx

Imagen:

```text
nginx:mainline-alpine
```

Contenedor:

```text
piped-nginx
```

Puerto externo:

```text
18080
```

Mapeo:

```text
QNAP:18080 → Nginx:80
```

Archivos montados:

```text
/share/Container/piped/config/nginx.conf
/share/Container/piped/config/pipedfrontend.conf
/share/Container/piped/config/pipedapi.conf
/share/Container/piped/config/pipedproxy.conf
/share/Container/piped/config/ytproxy.conf
```

---

## 17. Virtual hosts

Se utilizan:

```text
piped.home
pipedapi.home
pipedproxy.home
```

Los tres llegan al Nginx del QNAP mediante:

```text
:18080
```

Arquitectura:

```text
piped.home:18080
        ↓
      Nginx
        ↓
    Frontend

pipedapi.home:18080
        ↓
      Nginx
        ↓
     Backend

pipedproxy.home:18080
        ↓
      Nginx
        ↓
    piped-proxy
```

Estos nombres deben resolver hacia la IP del QNAP en la LAN.

---

## 18. Nginx general

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    tcp_nodelay on;
    keepalive_timeout 65;
    include /etc/nginx/conf.d/*.conf;
}
```

---

## 19. Nginx API

Upstream:

```nginx
upstream piped_backend {
    server piped-backend:8080;
}
```

Virtual host:

```text
server_name pipedapi.home;
```

Destino:

```text
http://piped_backend
```

Flujo:

```text
pipedapi.home:18080
        ↓
      Nginx
        ↓
piped-backend:8080
```

---

## 20. Nginx Proxy

Upstream:

```nginx
upstream piped_proxy {
    server piped-proxy:8080;
}
```

Virtual host:

```text
server_name pipedproxy.home;
```

Rutas relacionadas con reproducción:

```text
/videoplayback
/api/v4/
/api/manifest/
```

utilizan:

```nginx
include /etc/nginx/snippets/ytproxy.conf;
```

---

## 21. ytproxy.conf

Incluye CORS:

```nginx
add_header Access-Control-Allow-Origin *;
add_header Access-Control-Allow-Headers *;
```

Utiliza:

```nginx
proxy_set_header Host $arg_host;
```

y:

```nginx
proxy_http_version 1.1;
proxy_set_header Connection keep-alive;
```

Timeouts:

```text
proxy_read_timeout 3600s
proxy_send_timeout 3600s
proxy_connect_timeout 60s
```

También:

```nginx
access_log off;
```

---

## 22. Red Docker

Red:

```text
piped
```

Tipo:

```text
bridge
```

Los servicios pueden resolverse por nombre:

```text
postgres:5432
piped-backend:8080
piped-resolver:8000
piped-proxy:8080
piped-bgutil:4416
```

---

## 23. Puertos

| Servicio | Puerto interno | Publicado |
|---|---:|---:|
| PostgreSQL | 5432 | No |
| Piped Backend | 8080 | No |
| Resolver | 8000 | No |
| BGUTIL | 4416 | No |
| Piped Proxy | 8080 | No |
| Nginx | 80 | QNAP `18080` |

Solamente Nginx queda publicado:

```text
18080:80
```

---

## 24. Persistencia

Estructura:

```text
/share/Container/piped/
├── docker-compose.yml
├── config/
│   ├── config.properties
│   ├── nginx.conf
│   ├── pipedfrontend.conf
│   ├── pipedapi.conf
│   ├── pipedproxy.conf
│   └── ytproxy.conf
└── data/
    └── postgres/
```

Persistencia de PostgreSQL:

```text
/share/Container/piped/data/postgres
```

Las configuraciones se montan como solo lectura (`:ro`).

---

## 25. Docker Compose

```yaml
services:

  postgres:
    image: postgres:15-alpine
    container_name: piped-postgres
    restart: unless-stopped

    environment:
      POSTGRES_DB: piped
      POSTGRES_USER: piped
      POSTGRES_PASSWORD: Piped-QNAP-2026-ChangeMe

    volumes:
      - /share/Container/piped/data/postgres:/var/lib/postgresql/data

    networks:
      - piped

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U piped -d piped"]
      interval: 10s
      timeout: 5s
      retries: 10

  piped-bgutil:
    image: brainicism/bgutil-ytdlp-pot-provider:1.3.1
    container_name: piped-bgutil
    restart: unless-stopped

    networks:
      - piped

  piped-resolver:
    image: ghcr.io/antonio-bravo/piped-youtube/piped-resolver:latest
    container_name: piped-resolver
    restart: unless-stopped

    environment:
      RESOLVER_HOST: "0.0.0.0"
      RESOLVER_PORT: "8000"

      PROXY_URL: "http://pipedproxy.home:18080"

      CACHE_TTL: "3600"
      CACHE_MAXSIZE: "512"
      ALLOWED_ORIGINS: "*"

      BGUTIL_BASE_URL: "http://piped-bgutil:4416"

    depends_on:
      - piped-bgutil
      - piped-proxy

    networks:
      - piped

  piped-backend:
    image: 1337kavin/piped:latest
    container_name: piped-backend
    restart: unless-stopped

    depends_on:
      postgres:
        condition: service_healthy

    volumes:
      - /share/Container/piped/config/config.properties:/app/config.properties:ro

    networks:
      - piped

  piped-proxy:
    image: 1337kavin/piped-proxy:latest
    container_name: piped-proxy
    restart: unless-stopped

    environment:
      UDS: "0"

    networks:
      - piped

  piped-frontend:
    image: 1337kavin/piped-frontend:latest
    container_name: piped-frontend
    restart: unless-stopped

    environment:
      BACKEND_HOSTNAME: "pipedapi.home:18080"
      HTTP_MODE: "http"

    depends_on:
      - piped-backend

    networks:
      - piped

  nginx:
    image: nginx:mainline-alpine
    container_name: piped-nginx
    restart: unless-stopped

    depends_on:
      - piped-backend
      - piped-resolver
      - piped-proxy
      - piped-frontend

    ports:
      - "18080:80"

    volumes:
      - /share/Container/piped/config/nginx.conf:/etc/nginx/nginx.conf:ro
      - /share/Container/piped/config/pipedfrontend.conf:/etc/nginx/conf.d/pipedfrontend.conf:ro
      - /share/Container/piped/config/pipedapi.conf:/etc/nginx/conf.d/pipedapi.conf:ro
      - /share/Container/piped/config/pipedproxy.conf:/etc/nginx/conf.d/pipedproxy.conf:ro
      - /share/Container/piped/config/ytproxy.conf:/etc/nginx/snippets/ytproxy.conf:ro

    networks:
      - piped

networks:
  piped:
    name: piped
    driver: bridge
```

---

## 26. Comprobaciones

### PostgreSQL

```bash
docker exec piped-postgres   pg_isready -U piped -d piped
```

### Resolver

```bash
curl -s http://piped-resolver:8000/healthcheck
```

### Streams

```bash
curl -s   http://pipedapi.home:18080/streams/TZuGrNFLyWE
```

### Comprobar `proxyUrl`

```bash
curl -s   http://pipedapi.home:18080/streams/TZuGrNFLyWE |
python3 -c '
import sys,json
d=json.load(sys.stdin)
print("proxyUrl =", repr(d.get("proxyUrl")))
print("videoStreams =", len(d.get("videoStreams", [])))
print("audioStreams =", len(d.get("audioStreams", [])))
'
```

Resultado esperado:

```text
proxyUrl = 'http://pipedproxy.home:18080'
videoStreams = ...
audioStreams = ...
```

### Variables del resolver

```bash
docker exec piped-resolver sh -c   'env | grep -E "PROXY_URL|BGUTIL_BASE_URL|CACHE_TTL|ALLOWED_ORIGINS"'
```

Esperado:

```text
PROXY_URL=http://pipedproxy.home:18080
BGUTIL_BASE_URL=http://piped-bgutil:4416
CACHE_TTL=3600
ALLOWED_ORIGINS=*
```

---

## 27. Actualización/recreación

Después de modificar variables:

```bash
docker compose down
docker compose pull
docker compose up -d --force-recreate
```

No eliminar:

```text
/share/Container/piped/data/postgres
```

porque contiene los datos persistentes.

---

## 28. Diagnóstico

### `proxyUrl = ''`

Si aparece:

```text
proxyUrl = ''
```

comprobar que el resolver tenga:

```text
PROXY_URL=http://pipedproxy.home:18080
```

El código actual del resolver lee `PROXY_URL`, no `PIPED_RESOLVER_PROXY_URL`.

### Hay streams pero no reproduce

Si existen:

```text
videoStreams > 0
audioStreams > 0
```

pero el navegador no reproduce, revisar en este orden:

1. `proxyUrl`.
2. Resolución DNS de `pipedproxy.home`.
3. Nginx.
4. `piped-proxy`.
5. Peticiones `Range`.
6. CORS.
7. URL de `googlevideo`.
8. Consola de desarrollador del navegador.

---

## 29. Estado conocido durante las pruebas

Se confirmó:

- PostgreSQL conecta correctamente.
- Liquibase completa correctamente.
- El backend queda operativo.
- El resolver arranca.
- `yt-dlp` obtiene formatos adaptativos.
- Se obtienen múltiples `videoStreams`.
- Se obtienen `audioStreams`.
- Una URL directa de `googlevideo.com` devuelve `206 Partial Content`.
- El resolver inicialmente devolvía `proxyUrl = ''` porque se utilizaba `PIPED_RESOLVER_PROXY_URL`, mientras que el código lee `PROXY_URL`.
- El siguiente punto de diagnóstico es la cadena `piped-proxy + Nginx` si la reproducción continúa fallando.

---

## 30. Consideraciones de seguridad

La contraseña de PostgreSQL utilizada en este despliegue aparece en los archivos de configuración:

```text
Piped-QNAP-2026-ChangeMe
```

Debe cambiarse para una instalación real.

No se deberían publicar directamente en Internet los puertos internos de:

```text
PostgreSQL
Resolver
BGUTIL
Piped Backend
Piped Proxy
```

El diseño actual publica únicamente:

```text
QNAP:18080 → Nginx:80
```

---

## 31. Estructura final

```text
/share/Container/piped/
│
├── docker-compose.yml
│
├── config/
│   ├── config.properties
│   ├── nginx.conf
│   ├── pipedfrontend.conf
│   ├── pipedapi.conf
│   ├── pipedproxy.conf
│   └── ytproxy.conf
│
└── data/
    └── postgres/
```

Separación:

```text
docker-compose.yml
    │
    ├── definición de servicios
    ├── red Docker
    ├── volúmenes
    └── puertos

config/
    └── configuración de Piped y Nginx

data/
    └── datos persistentes de PostgreSQL
```

## 32. Imagen de docker para solucionar este problema

El codigo viene de este repositorio https://github.com/captainzonks/spoke-piped
en la subcarpeta /resolver hay un Dockerfile que es el que construimos con el siguiente comando dependiendo de la plataforma donde vaya a ejecutarse

```
docker build --platform linux/amd64 -t ghcr.io/antonio-bravo/piped-youtube/piped-resolver:latest .
```