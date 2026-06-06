# Guía de despliegue seguro — Backend

Esta guía te lleva de desarrollo a un despliegue de producción razonablemente
seguro. Sigue los pasos en orden.

## 1. Generar secretos fuertes

Genera dos claves aleatorias distintas (una para JWT, otra para el catálogo):

```bash
openssl rand -hex 32   # úsala en SECRET_KEY
openssl rand -hex 32   # úsala en CATALOG_API_KEY
```

## 2. Crear el archivo `.env` de producción

Copia `.env.example` a `.env` y completa con valores reales. Lo mínimo que
DEBES cambiar para producción:

```env
ENVIRONMENT=production
DATABASE_URL=''
SECRET_KEY=<clave de 64 caracteres del paso 1>
CATALOG_API_KEY=<otra clave del paso 1>
ALLOWED_ORIGINS=
ALLOWED_HOSTS=api.tudominio.com
DOCS_ENABLED=false
```

> El backend **se niega a arrancar en producción** si la SECRET_KEY o la
> CATALOG_API_KEY son débiles/de ejemplo, o si ALLOWED_ORIGINS contiene `*`.
> Es una protección intencional para que no se despliegue inseguro por descuido.

## 3. Base de datos

- Crea un usuario MySQL **dedicado** para la app (no uses `root`), con permisos
  solo sobre la base `inventario`.
- Aplica el esquema con migraciones (no se crean tablas solas en producción):

```bash
pip install -r requirements.txt
alembic upgrade head
```

## 4. Ejecutar la app

En producción usa varios workers detrás de un servidor ASGI. Con uvicorn:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
```

O con gunicorn gestionando workers uvicorn:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
  --workers 4 --bind 127.0.0.1:8000
```

> Nota: el limitador de login es en memoria por proceso. Con varios workers,
> el límite se cuenta por worker. Para un límite global estricto, respáldalo
> en Redis (la interfaz en `app/core/rate_limit.py` está pensada para
> sustituirse sin tocar el resto del código).

## 5. Reverse proxy + HTTPS (obligatorio)

Nunca expongas la app directo a internet por HTTP. Ponla detrás de Nginx (o
Caddy) que termine TLS. Ejemplo con Nginx:

```nginx
server {
    listen 443 ssl;
    server_name api.tudominio.com;

    ssl_certificate     /ruta/fullchain.pem;
    ssl_certificate_key /ruta/privkey.pem;

    # Tamaño máximo de subida (las imágenes son <= 5 MB).
    client_max_body_size 6m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Usa Let's Encrypt (certbot) para el certificado. El backend ya envía la
cabecera HSTS en producción para forzar HTTPS en el navegador.

## 6. Archivos subidos

- Las imágenes se guardan en el directorio `UPLOADS_DIR` (por defecto
  `uploads/`). Asegúrate de que persista entre reinicios (volumen/disco) y
  que tenga copia de seguridad.
- El `.gitignore` ya excluye `uploads/` para no versionar imágenes.

## 7. Copias de seguridad

- Programa un respaldo periódico de la base de datos MySQL.
- Respalda también la carpeta `uploads/`.

---

## Qué ya viene endurecido en el código

- **Contraseñas** hasheadas con bcrypt (nunca en texto plano).
- **JWT** firmado con la SECRET_KEY; expira según `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Rate limiting** del login por IP+correo (anti fuerza bruta, responde 429).
- **CORS restringido** a orígenes explícitos y a los headers/métodos usados.
- **Cabeceras de seguridad** en cada respuesta (nosniff, X-Frame-Options DENY,
  Referrer-Policy, Permissions-Policy, y HSTS en producción).
- **Validación de Host** (TrustedHost) en producción si defines ALLOWED_HOSTS.
- **Docs ocultos** en producción (no se expone la superficie de la API).
- **Subida de imágenes** validada por firma real del archivo (no solo por el
  tipo declarado), con tope de tamaño y nombres con UUID.
- **Borrado de imágenes** protegido contra path traversal.
- **Errores internos** devuelven un mensaje genérico (sin stack traces al
  cliente); el detalle queda solo en los logs del servidor.
- **Validaciones de arranque** que impiden desplegar con secretos de ejemplo.

## Limitaciones conocidas (por diseño)

- La `CATALOG_API_KEY` viaja al navegador del visitante (el catálogo es una
  app pública). Por eso solo protege endpoints de **solo lectura** del
  catálogo; no es un secreto fuerte frente a un usuario determinado. Está bien
  así porque esos datos son públicos. Las operaciones que modifican datos
  siguen exigiendo JWT (login de administrador).
- No hay refresh tokens: al expirar el token, el usuario vuelve a iniciar
  sesión. Suficiente para un panel administrativo interno.
