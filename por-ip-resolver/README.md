# Piped bajo IP única con Resolver Adaptativo (`por-ip-resolver`)

## 1. Objetivo

Esta configuración permite ejecutar Piped completamente bajo **una única IP y puerto** (`http://125.125.125.125:18080`), sin necesidad de configurar dominios DNS en el router y solucionando el error de extracción de vídeo:

```text
StreamExtractException: Could not get any stream
```

El error se resuelve delegando la extracción de streams a un microservicio resolver basado en **`yt-dlp`** + **`bgutil` (PoToken provider)**, manteniendo el backend oficial de Piped para búsqueda, comentarios, cuentas y suscripciones.

---

## 2. Arquitectura de red

```text
                                LAN
                                 │
                                 ▼
                       125.125.125.125:18080
                                 │
                              NGINX
                                 │
         ┌───────────────┬───────┴───────────────┬────────────────┐
         │               │                       │                │
         ▼               ▼                       ▼                ▼
         /          /api/streams              /api/            /proxy/
      (Frontend)   & /api/relay           (Backend REST)    (Piped Proxy)
         │               │                       │                │
         ▼               ▼                       ▼                ▼
   piped-frontend  piped-resolver          piped-backend     piped-proxy
        :80         (yt-dlp) :8000             :8080            :8080
                         │                       │                │
                         ▼                       ▼                ▼
                    piped-bgutil             PostgreSQL       YouTube CDN
                    (POT) :4416                :5432         (googlevideo)
```

---

## 3. Servicios en Docker Compose

| Servicio | Imagen | Puerto Interno | Función |
|---|---|---|---|
| `postgres` | `postgres:15-alpine` | `5432` | Base de datos para usuarios/suscripciones |
| `piped-bgutil` | `brainicism/bgutil-ytdlp-pot-provider:1.3.1` | `4416` | Generador de PoTokens antibot para `yt-dlp` |
| `piped-resolver` | `ghcr.io/antonio-bravo/piped-youtube/piped-resolver:latest` | `8000` | Extracción de streams de vídeo/audio con `yt-dlp` |
| `piped-backend` | `1337kavin/piped:latest` | `8080` | API para búsquedas, comentarios, suscripciones |
| `piped-proxy` | `1337kavin/piped-proxy:latest` | `8080` | Proxy TCP para transmisión de vídeo |
| `piped-frontend` | `1337kavin/piped-frontend:latest` | `80` | Interfaz Web SPA |
| `nginx` | `nginx:mainline-alpine` | `80` (Ext: `18080`) | Enrutador principal y proxy inverso |

---

## 4. Estructura de carpetas

```text
/share/Container/piped/
├── docker-compose.yml
├── README.md
├── config/
│   ├── config.properties
│   ├── nginx.conf
│   ├── pipedfrontend.conf
│   ├── pipedproxy.conf
│   └── ytproxy.conf
│
└── data/
    └── postgres/
```

---

## 5. Despliegue en el NAS / Servidor

1. Si tenías corriendo la versión anterior, detén los contenedores:
   ```bash
   cd /share/Container/piped
   docker compose down
   ```

2. Copia los archivos de esta carpeta `por-ip-resolver` a `/share/Container/piped/` (o trabaja dentro de la nueva carpeta).

3. Descarga las imágenes actualizadas:
   ```bash
   docker compose pull
   ```

4. Levanta todos los servicios:
   ```bash
   docker compose up -d
   ```

5. Comprueba el estado de los contenedores:
   ```bash
   docker compose ps
   ```

---

## 6. Pruebas y verificación

### Prueba 1 — API Backend
```bash
curl -I http://125.125.125.125:18080/api/config
```
*Debe responder `HTTP/1.1 200 OK` con el JSON de configuración.*

### Prueba 2 — Healthcheck del Resolver
```bash
curl -s http://125.125.125.125:18080/api/streams/healthcheck
# O internamente en Docker:
# curl -s http://piped-resolver:8000/healthcheck
```
*Debe responder `{"ok":true,"version":"..."}`.*

### Prueba 3 — Extracción de un vídeo
```bash
curl -s http://125.125.125.125:18080/api/streams/fGSvWYw6kik | head -n 30
```
*Debe responder con el JSON que contiene `videoStreams`, `audioStreams` y `proxyUrl: "http://125.125.125.125:18080/proxy"` sin error 500.*

### Prueba 4 — Navegador web
Abre en tu navegador:
```text
http://125.125.125.125:18080/watch?v=fGSvWYw6kik
```
El vídeo ahora se reproducirá directamente sin errores de extracción de stream.
