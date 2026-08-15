# Objectivo

Piped configurarlo accediendo por IP y puerto **manteniendo todo en TCP**, sin socket Unix y sin depender de los tres nombres DNS para acceder a Piped.

# La arquitectura será:

```text
                         LAN
                          │
                          ▼
                125.125.125.125:18080
                          │
                       nginx
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
            /           /api/        /proxy/
             │            │            │
             ▼            ▼            ▼
        frontend      backend       piped-proxy
          :80           :8080          :8080
```

Esto es compatible con el enfoque que ya se utiliza en despliegues de Piped con `/api` y `/proxy`; hay incluso configuraciones publicadas que usan `BASE_URL/api` para el frontend, `BASE_URL/api` para `API_URL` y `BASE_URL/proxy` para `PROXY_PART`. ([Gist][1])

Además, vamos a poner `UDS=0` en `piped-proxy`, de manera que **el proxy hable TCP por `8080` dentro de Docker**, que es precisamente lo que quieres. ([Gist][1])

## Estructura final

Mantendremos exactamente:

```text
/share/Container/piped/
├── docker-compose.yml
├── config/
│   ├── config.properties
│   ├── nginx.conf
│   ├── pipedfrontend.conf
│   ├── pipedapi.conf
│   └── pipedproxy.conf
│
└── data/
    └── postgres/
```

`ytproxy.conf` no se utiliza para un socket Unix en esta configuración. Se conserva porque contiene los ajustes de buffering, cabeceras y timeouts del proxy TCP.

---

# 1. `docker-compose.yml`

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
      - ./data/postgres:/var/lib/postgresql/data

    networks:
      - piped


  piped-backend:
    image: 1337kavin/piped:latest
    container_name: piped-backend
    restart: unless-stopped

    depends_on:
      - postgres

    volumes:
      - ./config/config.properties:/app/config.properties:ro

    expose:
      - "8080"

    networks:
      - piped


  piped-proxy:
    image: 1337kavin/piped-proxy:latest
    container_name: piped-proxy
    restart: unless-stopped

    environment:
      UDS: "0"

    expose:
      - "8080"

    networks:
      - piped


  piped-frontend:
    image: 1337kavin/piped-frontend:latest
    container_name: piped-frontend
    restart: unless-stopped

    depends_on:
      - piped-backend

    environment:
      BACKEND_HOSTNAME: 125.125.125.125:18080/api
      HTTP_MODE: http

    expose:
      - "80"

    networks:
      - piped


  nginx:
    image: nginx:mainline-alpine
    container_name: piped-nginx
    restart: unless-stopped

    depends_on:
      - piped-backend
      - piped-proxy
      - piped-frontend

    ports:
      - "18080:80"

    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/pipedfrontend.conf:/etc/nginx/conf.d/pipedfrontend.conf:ro
      - ./config/pipedapi.conf:/etc/nginx/conf.d/pipedapi.conf:ro
      - ./config/pipedproxy.conf:/etc/nginx/conf.d/pipedproxy.conf:ro
      - ./config/ytproxy.conf:/etc/nginx/snippets/ytproxy.conf:ro

    networks:
      - piped


networks:
  piped:
    name: piped
    driver: bridge
```

### Una cosa importante

Fíjate en que **solo NGINX publica un puerto al NAS**:

```yaml
ports:
  - "18080:80"
```

El backend:

```yaml
expose:
  - "8080"
```

y el proxy:

```yaml
expose:
  - "8080"
```

**no publican ningún puerto al NAS**.

Por tanto:

```text
NAS:18080
   ↓
NGINX
   ↓
red Docker "piped"
   ├── piped-frontend:80
   ├── piped-backend:8080
   └── piped-proxy:8080
```

Todo el tráfico entre contenedores es TCP.

---

# 2. `config/config.properties`

Aquí está el cambio fundamental respecto a tu configuración anterior.

```properties
# ============================================================
# PIPED BACKEND
# ============================================================

PORT:8080
HTTP_WORKERS:2


# ============================================================
# URLs PUBLICAS DE ESTA INSTANCIA
# ============================================================

# Proxy de vídeo
PROXY_PART:http://125.125.125.125:18080/proxy

# API pública
API_URL:http://125.125.125.125:18080/api

# Frontend
FRONTEND_URL:http://125.125.125.125:18080


# ============================================================
# CAPTCHA
# ============================================================

# CAPTCHA desactivado/no configurado
# CAPTCHA_BASE_URL:https://api.capmonster.cloud/
# CAPTCHA_API_KEY:INSERT_HERE


# ============================================================
# REGISTRO
# ============================================================

# false = registro ACTIVADO
DISABLE_REGISTRATION:false


# ============================================================
# CUENTAS / FEEDS
# ============================================================

FEED_RETENTION:30

SUBSCRIPTIONS_EXPIRY:30


# ============================================================
# RENDIMIENTO
# ============================================================

DISABLE_TIMERS:false


# ============================================================
# COMPROMISED PASSWORD CHECK
# ============================================================

COMPROMISED_PASSWORD_CHECK:true


# ============================================================
# RYD - RETURN YOUTUBE DISLIKE
# ============================================================

RYD_PROXY_URL:https://ryd-proxy.kavin.rocks

DISABLE_RYD:false


# ============================================================
# SPONSORBLOCK
# ============================================================

SPONSORBLOCK_SERVERS:https://sponsor.ajay.app,https://sponsorblock.kavin.rocks


# ============================================================
# LBRY
# ============================================================

DISABLE_LBRY:false


# ============================================================
# CONSENT COOKIE
# ============================================================

CONSENT_COOKIE:true


# ============================================================
# MATRIX
# ============================================================

MATRIX_SERVER:https://matrix-client.matrix.org


# ============================================================
# BG HELPER
# ============================================================

# No se utiliza en esta configuración
# BG_HELPER_URL:http://bg-helper:3000


# ============================================================
# S3
# ============================================================

#S3_ENDPOINT:INSERT_HERE
#S3_ACCESS_KEY:INSERT_HERE
#S3_SECRET_KEY:INSERT_HERE
#S3_BUCKET:INSERT_HERE


# ============================================================
# HIBERNATE / POSTGRESQL
# ============================================================

hibernate.connection.url:jdbc:postgresql://postgres:5432/piped
hibernate.connection.driver_class:org.postgresql.Driver
hibernate.dialect:org.hibernate.dialect.PostgreSQLDialect
hibernate.connection.username:piped
hibernate.connection.password:Piped-QNAP-2026-ChangeMe


# ============================================================
# FRONTEND
# ============================================================

#frontend.statusPageUrl:
#frontend.donationUrl:
```

La configuración oficial actual de Piped utiliza precisamente `API_URL`, `FRONTEND_URL`, `PROXY_PART` y la conexión PostgreSQL mediante `hibernate.connection.url`; además, `DISABLE_REGISTRATION:false` mantiene el registro habilitado. ([GitHub][2])

---

# 3. `config/nginx.conf`

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {

    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;

    keepalive_timeout 65;

    client_max_body_size 20m;

    # Logs
    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log warn;

    # DNS interno de Docker
    resolver 127.0.0.11 valid=30s;

    include /etc/nginx/conf.d/*.conf;
}
```

---

# 4. `config/pipedfrontend.conf`

Aquí está el frontend.

```nginx
server {

    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    location / {

        proxy_pass http://piped-frontend:80;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Connection "";

        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

Este es el `default_server`, por lo que:

```text
http://125.125.125.125:18080/
```

entra aquí.

---

# 5. `config/pipedapi.conf`

Ahora viene `/api/`.

```nginx
server {

    listen 80;

    server_name _;

    location ^~ /api/ {

        proxy_pass http://piped-backend:8080/;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Connection "";

        proxy_read_timeout 120s;
        proxy_send_timeout 120s;

        proxy_buffering off;

        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "*" always;

        if ($request_method = OPTIONS) {
            return 204;
        }
    }
}
```

### Importante

Esta línea:

```nginx
proxy_pass http://piped-backend:8080/;
```

tiene la `/` final.

Eso hace:

```text
/api/config
      ↓
piped-backend:8080/config
```

Es exactamente lo que queremos.

El backend sigue funcionando internamente como siempre:

```text
piped-backend:8080/config
```

pero externamente lo presentamos como:

```text
125.125.125.125:18080/api/config
```

---

# 6. `config/pipedproxy.conf`

Para el proxy:

```nginx
server {

    listen 80;

    server_name _;

    location ^~ /proxy/ {

        proxy_pass http://piped-proxy:8080/;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Connection "keep-alive";

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        proxy_buffering off;

        # Cabeceras necesarias para el proxy de vídeo
        proxy_set_header X-Forwarded-For "";
        proxy_set_header CF-Connecting-IP "";

        add_header Alt-Svc "" always;
        add_header Cache-Control "" always;
        add_header ETag "" always;
    }
}
```

---

# 7. `ytproxy.conf` y comunicación TCP

En tu configuración anterior sí tenía sentido porque el diseño oficial de `Piped-Docker` utiliza un volumen para comunicar NGINX con `piped-proxy` mediante socket Unix. El propio proyecto muestra esa configuración con `ytproxy.conf` y el volumen `piped-proxy`. ([GitHub][3])

Pero nosotros estamos haciendo deliberadamente:

```text
piped-nginx
      │
      │ TCP
      ▼
piped-proxy:8080
```

porque hemos configurado:

```yaml
environment:
  UDS: "0"
```

El uso de TCP en `piped-proxy:8080` está documentado en configuraciones de Piped que emplean `UDS=0`. ([Gist][1])

El archivo se incluye desde la `location /proxy/` y su `proxy_pass` se define allí con una barra final para eliminar el prefijo `/proxy/`. No contiene ni configura un socket Unix.

---

# 8. Así quedará toda la red

## Desde el dispositivo

### Frontend

```text
http://125.125.125.125:18080/
```

NGINX:

```text
→ piped-frontend:80
```

---

### API

```text
http://125.125.125.125:18080/api/config
```

NGINX elimina `/api/`:

```text
→ piped-backend:8080/config
```

Por tanto esta URL debería devolver el JSON:

```text
http://125.125.125.125:18080/api/config
```

---

### Proxy

Por ejemplo:

```text
http://125.125.125.125:18080/proxy/...
```

NGINX:

```text
→ piped-proxy:8080/...
```

---

# 9. Hay un detalle MUY importante con el frontend

He puesto:

```yaml
BACKEND_HOSTNAME: 125.125.125.125:18080/api
HTTP_MODE: http
```

Esto es deliberado.

La imagen oficial de frontend utiliza `BACKEND_HOSTNAME` para sustituir la URL de la API en los assets JavaScript durante el arranque. ([readmex.com][4])

Por eso queremos que el JavaScript generado termine utilizando:

```text
http://125.125.125.125:18080/api
```

y no:

```text
http://125.125.125.125:18080/api/config
```

Esto elimina la dependencia del DNS para la API.

Y en el backend:

```properties
API_URL:http://125.125.125.125:18080/api
```

mientras que:

```properties
PROXY_PART:http://125.125.125.125:18080/proxy
```

hace que las URLs que genere Piped apunten a nuestra nueva estructura.

---

# 10. Pero hay una cosa que quiero que hagamos al cambiarlo

Como anteriormente tenías:

```text
BACKEND_HOSTNAME=125.125.125.125:18080/api
```

el frontend ya fue generado con esa dirección dentro del JavaScript.

**No basta con hacer `restart` del frontend.**

Hay que **recrear** el contenedor para que el `entrypoint.sh` vuelva a modificar los assets con:

```text
125.125.125.125:18080/api
```

La documentación/implementaciones actuales también advierten de que `BACKEND_HOSTNAME` se aplica durante la creación/inicialización del frontend; al cambiarlo hay que recrear el contenedor. ([readmex.com][4])

Por eso después de guardar los archivos ejecutaremos:

```bash
cd /share/Container/piped

docker compose down

docker compose up -d
```

No hagas todavía:

```bash
docker compose down -v
```

porque **no queremos borrar PostgreSQL**.

---

# 11. Comprobaciones antes de levantarlo

Yo haría primero:

```bash
cd /share/Container/piped

docker compose config
```

Si no muestra errores:

```bash
docker compose up -d
```

Después:

```bash
docker compose ps
```

Deberías tener aproximadamente:

```text
piped-postgres
piped-backend
piped-proxy
piped-frontend
piped-nginx
```

todos funcionando.

---

## 12. Pruebas en este orden

No empezaría directamente con la página.

### Prueba 1 — backend

Desde el navegador:

```text
http://125.125.125.125:18080/api/config
```

Tiene que aparecer el JSON.

### Prueba 2 — frontend

```text
http://125.125.125.125:18080/
```

### Prueba 3 — navegador

Abre las herramientas de desarrollador y comprueba que las llamadas sean:

```text
http://125.125.125.125:18080/api/...
```

y **no** el hostname antiguo.

### Prueba 4 — proxy

La haremos después con un vídeo, porque aquí es donde podremos comprobar que:

```text
frontend
   ↓
/api
   ↓
backend
   ↓
/proxy
   ↓
piped-proxy
```

está funcionando correctamente.

---

## Una última consideración

Esta configuración está pensada para **HTTP dentro de tu LAN**, tal como veníamos hablando:

```text
http://125.125.125.125:18080
```

No HTTPS.

Por tanto **no abras el puerto 18080 hacia Internet**. Déjalo accesible únicamente desde tu LAN/firewall.

Los DNS antiguos pueden seguir existiendo en el ZTE, pero con esta nueva configuración **ya no son necesarios para que Piped funcione por IP**.

La ventaja es exactamente la que buscabas:

```text
┌───────────────────────────────────────────────┐
│               125.125.125.125:18080           │
├───────────────────────────────────────────────┤
│ /                                             │
│       → Piped Frontend                        │
│                                               │
│ /api/*                                        │
│       → Piped Backend                         │
│                                               │
│ /proxy/*                                      │
│       → Piped Proxy                           │
└───────────────────────────────────────────────┘
```

**Esta sería la configuración que probaría antes de tocar de nuevo DNS.**

[1]: https://gist.github.com/nonsleepr/cf6c65837fec534ad6302ea06b7d37fa?utm_source=chatgpt.com "Piped on Tailscale · GitHub"
[2]: https://github.com/TeamPiped/Piped-Backend/blob/master/config.properties?utm_source=chatgpt.com "Piped-Backend/config.properties at master · TeamPiped/Piped-Backend · GitHub"
[3]: https://github.com/TeamPiped/Piped/issues/3233?utm_source=chatgpt.com "fix self-host documents script generated docker-compose.yaml file content. · Issue #35 · TeamPiped/Piped-Docker"
[4]: https://readmex.com/en-US/TeamPiped/Piped/page-1008be8f0f-2310-4974-8cb0-76b600f0566e?utm_source=chatgpt.com "爱獭知识社区"
