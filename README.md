# Piped en QNAP TS-451 — Documentación de instalación y arquitectura

## 1. Descripción

Esta documentación describe la instalación de **Piped** en un **QNAP TS-451** utilizando **Container Station / Docker Compose**.

La instalación está diseñada para funcionar **exclusivamente dentro de la LAN**, sin exposición directa a Internet.

La arquitectura utiliza:

* Piped Backend
* Piped Frontend
* Piped Proxy
* PostgreSQL
* NGINX como reverse proxy
* Una red Docker interna
* Tres nombres DNS internos
* HTTP/TCP, sin HTTPS
* Sin Unix Domain Sockets
* Puerto externo `18080`

---

# 2. Arquitectura general

La arquitectura final es:

```text
                              LAN
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       piped.home       pipedapi.home     pipedproxy.home
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                         125.125.125.125
                               │
                         TCP / HTTP :18080
                               │
                        ┌──────▼──────┐
                        │    NGINX    │
                        │    :80      │
                        └──────┬──────┘
                               │
                        Docker network
                             "piped"
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
  piped-frontend        piped-backend         piped-proxy
       :80                  :8080                 :8080
          │                    │
          │                    │ TCP
          │                    ▼
          │                postgres
          │                   :5432
          │
          └─────────────────────────────────────────
```

---

# 3. Ubicación de los archivos

La estructura utilizada en el QNAP es:

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

## Directorios

### Configuración

```text
/share/Container/piped/config/
```

Contiene toda la configuración de Piped y NGINX.

### PostgreSQL

```text
/share/Container/piped/data/postgres/
```

Contiene los datos persistentes de PostgreSQL.

**Este directorio no debe borrarse** si se quieren conservar usuarios, suscripciones y demás información almacenada por Piped.

---

# 4. DNS interno

Se han configurado tres registros DNS internos.

| DNS               | IP                |
| ----------------- | ----------------- |
| `piped.home`      | `125.125.125.125` |
| `pipedapi.home`   | `125.125.125.125` |
| `pipedproxy.home` | `125.125.125.125` |

Los tres nombres apuntan a la misma IP del NAS.

El puerto utilizado desde la LAN es:

```text
18080
```

Por tanto:

```text
http://piped.home:18080
http://pipedapi.home:18080
http://pipedproxy.home:18080
```

---

# 5. Acceso principal

La interfaz web de Piped se abre mediante:

```text
http://piped.home:18080
```

La API:

```text
http://pipedapi.home:18080
```

El proxy:

```text
http://pipedproxy.home:18080
```

---

# 6. Motivo del puerto 18080

El QNAP ya utiliza el puerto `8080`.

Por ese motivo no se publica ningún servicio Piped directamente en el puerto `8080` del NAS.

Únicamente NGINX publica:

```text
18080:80
```

Es decir:

```text
NAS TCP 18080
       │
       ▼
NGINX TCP 80
```

Los puertos `8080` utilizados por Piped existen únicamente dentro de la red Docker.

---

# 7. Puertos

## Puertos publicados en el NAS

Solo existe:

```text
TCP 18080
```

Correspondencia:

```text
125.125.125.125:18080
            │
            ▼
       piped-nginx:80
```

## Puertos internos Docker

| Servicio   | Puerto | Protocolo | Accesible desde    |
| ---------- | -----: | --------- | ------------------ |
| NGINX      |     80 | TCP       | LAN / puerto 18080 |
| Frontend   |     80 | TCP       | Docker             |
| Backend    |   8080 | TCP       | Docker             |
| Proxy      |   8080 | TCP       | Docker             |
| PostgreSQL |   5432 | TCP       | Docker             |

No se publica ninguno de estos puertos directamente en el NAS:

```text
80
5432
8080
```

---

# 8. Red Docker

Todos los contenedores utilizan una red Docker llamada:

```text
piped
```

Tipo:

```text
bridge
```

La red permite que los contenedores se comuniquen directamente mediante sus nombres de servicio.

Por ejemplo:

```text
piped-backend → postgres:5432
```

o:

```text
nginx → piped-backend:8080
```

No es necesario utilizar la IP del NAS para las comunicaciones internas.

---

# 9. Comunicación interna

## NGINX → Frontend

```text
piped-nginx
      │
      │ TCP
      ▼
piped-frontend:80
```

## NGINX → Backend

```text
piped-nginx
      │
      │ TCP
      ▼
piped-backend:8080
```

## NGINX → Proxy

```text
piped-nginx
      │
      │ TCP
      ▼
piped-proxy:8080
```

## Backend → PostgreSQL

```text
piped-backend
      │
      │ TCP
      ▼
postgres:5432
```

---

# 10. No se utilizan Unix Sockets

Toda la comunicación entre servicios está configurada mediante TCP.

No se utiliza:

```text
/var/run/ytproxy/http-proxy.sock
```

El proxy utiliza TCP:

```text
piped-proxy:8080
```

Esto permite mantener una arquitectura homogénea y sencilla de diagnosticar.

---

# 11. PostgreSQL

## Base de datos

```text
POSTGRES_DB=piped
```

## Usuario

```text
POSTGRES_USER=piped
```

## Contraseña

```text
Piped-QNAP-xxxx-ChangeMe
```

## Puerto interno

```text
5432/TCP
```

## Host utilizado por Piped

El backend no utiliza:

```text
125.125.125.125
```

ni:

```text
postgres.home
```

Utiliza el nombre del servicio Docker:

```text
postgres
```

Por tanto la conexión es:

```text
postgresql://postgres:5432/piped
```

---

# 12. Persistencia PostgreSQL

Los datos de PostgreSQL están almacenados en:

```text
/share/Container/piped/data/postgres/
```

Mapeo:

```text
/share/Container/piped/data/postgres/
        │
        ▼
/var/lib/postgresql/data
```

Esto permite que los datos sobrevivan a:

* reinicios del contenedor
* recreación del contenedor
* actualización de la imagen

No se debe eliminar el directorio si se quieren conservar los datos.

---

# 13. Piped Backend

Contenedor:

```text
piped-backend
```

Imagen:

```text
1337kavin/piped:latest
```

Puerto interno:

```text
8080/TCP
```

No se publica directamente.

El backend se alcanza desde NGINX mediante:

```text
piped-backend:8080
```

---

# 14. Configuración pública del Backend

El backend utiliza:

```properties
API_URL:http://pipedapi.home:18080
```

La URL pública de frontend:

```properties
FRONTEND_URL:http://piped.home:18080
```

La URL pública del proxy:

```properties
PROXY_PART:http://pipedproxy.home:18080
```

Estas URLs son las que utiliza Piped para informar al frontend de dónde están disponibles los distintos componentes.

---

# 15. PostgreSQL desde el Backend

El Backend utiliza:

```properties
hibernate.connection.url:jdbc:postgresql://postgres:5432/piped
```

Usuario:

```properties
hibernate.connection.username:piped
```

Contraseña:

```properties
hibernate.connection.password:Piped-QNAP-xxxx-ChangeMe
```

La comunicación es:

```text
Backend
   │
   │ TCP 5432
   ▼
postgres
```

---

# 16. Piped Frontend

Contenedor:

```text
piped-frontend
```

Imagen:

```text
1337kavin/piped-frontend:latest
```

Puerto interno:

```text
80/TCP
```

La configuración importante es:

```yaml
environment:
  BACKEND_HOSTNAME: pipedapi.home:18080
  HTTP_MODE: http
```

## `BACKEND_HOSTNAME`

El navegador necesita acceder a la API mediante el DNS de la LAN:

```text
pipedapi.home:18080
```

No debe utilizar:

```text
piped-backend:8080
```

porque ese nombre solo existe dentro de Docker.

---

# 17. HTTP_MODE

Esta opción es especialmente importante.

Se utiliza:

```yaml
HTTP_MODE: http
```

La razón es que la instalación funciona mediante:

```text
HTTP
```

y no mediante:

```text
HTTPS
```

El frontend actual puede utilizar HTTPS por defecto si no se especifica `HTTP_MODE`.

Eso provocó inicialmente que el navegador intentara acceder a:

```text
https://pipedapi.home:18080
```

cuando NGINX estaba configurado para:

```text
http://pipedapi.home:18080
```

El resultado era:

```text
TypeError: Failed to fetch
```

y Piped permanecía en el spinner de carga.

La configuración correcta es:

```yaml
HTTP_MODE: http
```

---

# 18. Piped Proxy

Contenedor:

```text
piped-proxy
```

Imagen:

```text
1337kavin/piped-proxy:latest
```

Puerto:

```text
8080/TCP
```

Se utiliza:

```yaml
environment:
  UDS: "0"
```

Esto desactiva el uso del Unix Domain Socket y permite que el proxy escuche mediante TCP.

La comunicación interna es:

```text
NGINX
 │
 │ TCP
 ▼
piped-proxy:8080
```

---

# 19. NGINX

Contenedor:

```text
piped-nginx
```

Imagen:

```text
nginx:mainline-alpine
```

Puerto interno:

```text
80/TCP
```

Puerto publicado:

```text
18080:80
```

Por tanto:

```text
NAS:18080
    │
    ▼
NGINX:80
```

---

# 20. Enrutamiento NGINX

NGINX utiliza el hostname recibido mediante HTTP para decidir a qué contenedor enviar la petición.

## `piped.home`

```text
http://piped.home:18080
```

se dirige a:

```text
piped-frontend:80
```

Flujo:

```text
Cliente LAN
    │
    ▼
piped.home:18080
    │
    ▼
NGINX
    │
    ▼
piped-frontend:80
```

---

# 21. `pipedapi.home`

```text
http://pipedapi.home:18080
```

se dirige a:

```text
piped-backend:8080
```

Flujo:

```text
Cliente LAN
    │
    ▼
pipedapi.home:18080
    │
    ▼
NGINX
    │
    ▼
piped-backend:8080
```

---

# 22. `pipedproxy.home`

```text
http://pipedproxy.home:18080
```

se dirige a:

```text
piped-proxy:8080
```

Flujo:

```text
Cliente LAN
    │
    ▼
pipedproxy.home:18080
    │
    ▼
NGINX
    │
    ▼
piped-proxy:8080
```

---

# 23. NGINX y CORS

No se ha añadido una política CORS personalizada específica para Piped en NGINX.

Esto es intencionado.

Durante las pruebas se comprobó que el backend responde correctamente a las peticiones desde el frontend.

No se debe añadir arbitrariamente otra cabecera:

```text
Access-Control-Allow-Origin
```

si el backend ya la proporciona, porque se puede acabar generando una respuesta con múltiples valores de dicha cabecera.

---

# 24. CAPTCHA

Se ha decidido no utilizar CAPTCHA.

No se ha configurado:

```properties
CAPTCHA_BASE_URL
CAPTCHA_API_KEY
```

Esto significa que la instalación no utiliza un servicio CAPTCHA externo.

Si en el futuro Piped/YouTube requiere CAPTCHA para determinadas operaciones, será necesario revisar esta configuración.

---

# 25. Registro de usuarios

El registro está activado.

Configuración:

```properties
DISABLE_REGISTRATION:false
```

Por tanto, los usuarios de la LAN pueden acceder al sistema de registro.

Como la instalación está diseñada únicamente para la LAN, no se pretende que el registro esté disponible públicamente desde Internet.

---

# 26. Timers

Se ha configurado:

```properties
DISABLE_TIMERS:true
```

La decisión se toma pensando en el QNAP TS-451 y en reducir tareas periódicas innecesarias.

Esto no impide el uso normal de Piped.

---

# 27. URLs finales

## Frontend

```text
http://piped.home:18080
```

## API

```text
http://pipedapi.home:18080
```

## Proxy

```text
http://pipedproxy.home:18080
```

---

# 28. Diagrama completo de conexiones

```text
                              INTERNET
                                  │
                                  │
                                  ▼
                               YouTube
                                  ▲
                                  │
                                  │
                            piped-proxy
                              :8080
                                  ▲
                                  │
                                  │ TCP
                                  │
                            ┌─────┴─────┐
                            │   NGINX   │
                            │    :80    │
                            └─────┬─────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             │                    │                    │
             ▼                    ▼                    ▼
      piped-frontend       piped-backend         piped-proxy
           :80                  :8080                 :8080
                                  │
                                  │ TCP
                                  ▼
                              PostgreSQL
                                :5432
```

Desde la LAN:

```text
                           LAN
                            │
                            ▼
                   125.125.125.125
                            │
                         :18080
                            │
                            ▼
                          NGINX
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    piped.home       pipedapi.home     pipedproxy.home
```

---

# 29. Flujo de una página de Piped

Cuando el usuario abre:

```text
http://piped.home:18080
```

ocurre lo siguiente:

```text
1. El ordenador consulta piped.home
2. DNS devuelve 125.125.125.125
3. El navegador conecta con TCP 18080
4. QNAP recibe la conexión
5. Docker publica 18080 hacia NGINX:80
6. NGINX identifica Host: piped.home
7. NGINX envía la petición a piped-frontend:80
8. Frontend devuelve la aplicación web
```

Posteriormente el navegador necesita datos:

```text
9. Frontend solicita:
   http://pipedapi.home:18080/config

10. DNS devuelve 125.125.125.125

11. La petición llega a NGINX

12. NGINX identifica:
    Host: pipedapi.home

13. NGINX envía:
    piped-backend:8080

14. Backend consulta PostgreSQL cuando es necesario

15. Backend devuelve la respuesta al navegador
```

Para contenido de vídeo:

```text
16. Frontend utiliza:
    http://pipedproxy.home:18080

17. NGINX envía la petición:
    piped-proxy:8080

18. Piped Proxy obtiene el contenido correspondiente
```

---

# 30. Diagnóstico de la instalación

## Comprobar contenedores

```bash
docker compose ps
```

Deberían aparecer:

```text
piped-postgres
piped-backend
piped-proxy
piped-frontend
piped-nginx
```

---

# 31. Logs

## Backend

```bash
docker logs piped-backend --tail 100
```

Una señal positiva es:

```text
Database connection is ready!
```

Esto indica que el backend ha conseguido conectarse a PostgreSQL.

---

# 32. PostgreSQL

```bash
docker logs piped-postgres --tail 100
```

Durante el primer arranque es normal encontrar mensajes de inicialización de PostgreSQL.

---

# 33. Frontend

```bash
docker logs piped-frontend --tail 100
```

---

# 34. Proxy

```bash
docker logs piped-proxy --tail 100
```

---

# 35. NGINX

```bash
docker logs piped-nginx --tail 100
```

---

# 36. Comprobar la API

Desde un ordenador de la LAN:

```text
http://pipedapi.home:18080/config
```

Debe devolver JSON.

Un resultado válido incluye información como:

```json
{
  "imageProxyUrl": "http://pipedproxy.home:18080",
  "registrationDisabled": false
}
```

Esto confirma que:

```text
LAN
 ↓
DNS
 ↓
NAS:18080
 ↓
NGINX
 ↓
piped-backend
```

funciona correctamente.

---

# 37. Comprobar Trending

Desde un ordenador de la LAN:

```text
http://pipedapi.home:18080/trending?region=US
```

Debe devolver JSON con los contenidos de Trending.

---

# 38. Comprobar resolución Docker

Desde el backend:

```bash
docker exec piped-backend getent hosts postgres
```

Debe resolver:

```text
postgres
```

También:

```bash
docker exec piped-backend getent hosts piped-proxy
```

Debe resolver:

```text
piped-proxy
```

Esto demuestra que la resolución de nombres interna de Docker funciona.

---

# 39. Comprobar red Docker

```bash
docker network inspect piped
```

Deberían aparecer los cinco contenedores conectados a la red:

```text
piped-postgres
piped-backend
piped-proxy
piped-frontend
piped-nginx
```

---

# 40. Reiniciar la instalación

Para reiniciar los servicios:

```bash
cd /share/Container/piped
docker compose restart
```

---

# 41. Detener la instalación

```bash
cd /share/Container/piped
docker compose down
```

Esto elimina los contenedores pero no debería eliminar los datos almacenados en:

```text
/share/Container/piped/data/postgres/
```

---

# 42. Volver a arrancar

```bash
cd /share/Container/piped
docker compose up -d
```

---

# 43. Actualizar las imágenes

Antes de actualizar conviene realizar una copia de seguridad de:

```text
/share/Container/piped/data/postgres/
```

Después:

```bash
cd /share/Container/piped
docker compose pull
docker compose up -d
```

Para forzar la recreación del frontend después de modificar variables de entorno:

```bash
docker compose up -d --force-recreate piped-frontend
```

---

# 44. Punto importante sobre `HTTP_MODE`

El frontend utiliza:

```yaml
HTTP_MODE: http
```

No eliminar esta variable mientras la instalación continúe utilizando HTTP.

Si se elimina, una versión del frontend puede utilizar HTTPS por defecto y generar URLs como:

```text
https://pipedapi.home:18080
```

cuando el servicio realmente está disponible mediante:

```text
http://pipedapi.home:18080
```

Esto puede producir en el navegador:

```text
TypeError: Failed to fetch
```

y dejar Piped en el spinner de carga.

---

# 45. Seguridad

Esta instalación está diseñada para:

```text
LAN ONLY
```

No se pretende publicar Piped directamente en Internet.

El puerto:

```text
18080/TCP
```

debe permanecer accesible únicamente desde la LAN.

No se deben crear reglas de port forwarding WAN → `18080` en el router.

---

# 46. Resumen de seguridad de puertos

### NAS

```text
TCP 18080
```

debe estar disponible desde la LAN.

### No publicar

```text
TCP 80
TCP 8080
TCP 5432
```

directamente en la interfaz del NAS.

### PostgreSQL

PostgreSQL no debe exponerse a la LAN ni a Internet.

Solo debe ser accesible mediante:

```text
piped-backend → postgres:5432
```

---

# 47. Credenciales

Base de datos:

```text
Base de datos: piped
Usuario: piped
Contraseña: Piped-QNAP-xxxx-ChangeMe
```

## Recomendación

La contraseña proporcionada actualmente es funcional, pero debe considerarse una credencial conocida.

Si la instalación se mantiene a largo plazo, conviene sustituirla por una contraseña aleatoria y actualizar simultáneamente:

```yaml
POSTGRES_PASSWORD
```

y:

```properties
hibernate.connection.password
```

---

# 48. Backup

Como mínimo se debe realizar una copia de:

```text
/share/Container/piped/data/postgres/
```

También conviene conservar:

```text
/share/Container/piped/docker-compose.yml
/share/Container/piped/config/
```

Una copia completa de:

```text
/share/Container/piped/
```

permite reconstruir la instalación con mayor facilidad.

---

# 49. Checklist de funcionamiento

```text
[ ] DNS piped.home funciona
[ ] DNS pipedapi.home funciona
[ ] DNS pipedproxy.home funciona

[ ] TCP 18080 accesible desde LAN

[ ] piped-nginx está funcionando
[ ] piped-frontend está funcionando
[ ] piped-backend está funcionando
[ ] piped-proxy está funcionando
[ ] piped-postgres está funcionando

[ ] Backend conecta con PostgreSQL
[ ] /config devuelve JSON
[ ] /trending devuelve JSON

[ ] Frontend utiliza HTTP
[ ] BACKEND_HOSTNAME apunta a pipedapi.home:18080

[ ] Registro activado
[ ] CAPTCHA no configurado

[ ] PostgreSQL no está publicado
[ ] Backend no está publicado
[ ] Proxy no está publicado
[ ] Frontend no está publicado

[ ] No existe port forwarding desde Internet
```

---

# 50. Estado final de la instalación

La instalación queda conceptualmente así:

```text
                       ┌─────────────────────┐
                       │       INTERNET      │
                       └──────────┬──────────┘
                                  │
                                  │
                                  ▼
                             YouTube/etc.
                                  ▲
                                  │
                                  │
                         ┌────────┴────────┐
                         │  piped-proxy    │
                         │    TCP :8080    │
                         └────────▲────────┘
                                  │
                                  │
LAN                               │
 │                                │
 │ TCP :18080                     │
 ▼                                │
┌─────────────────────────────────────────────┐
│                    QNAP                     │
│                                             │
│  ┌───────────────┐                          │
│  │     NGINX     │                          │
│  │    TCP :80    │                          │
│  └───────┬───────┘                          │
│          │                                  │
│          │ Docker network: piped            │
│          │                                  │
│   ┌──────┼───────────┬─────────────┐        │
│   │      │           │             │        │
│   ▼      ▼           ▼             │        │
│ Front   Backend     Proxy           │        │
│ :80     :8080       :8080           │        │
│            │                        │        │
│            │ TCP :5432             │        │
│            ▼                        │        │
│       PostgreSQL                    │        │
│          :5432                      │        │
│                                     │        │
└─────────────────────────────────────────────┘
```

## URLs de usuario

```text
Frontend:
http://piped.home:18080

API:
http://pipedapi.home:18080

Proxy:
http://pipedproxy.home:18080
```

## Red Docker

```text
piped
```

## Puerto publicado

```text
18080/TCP
```

## Base de datos

```text
postgres:5432
```

## Persistencia

```text
/share/Container/piped/data/postgres/
```

## Acceso

```text
LAN solamente
```

## Transporte

```text
TCP / HTTP
```

## Unix sockets

```text
No utilizados
```

## HTTPS

```text
No utilizado
```

## CAPTCHA

```text
No configurado
```

## Registro

```text
Activado
```
