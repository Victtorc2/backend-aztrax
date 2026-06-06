# Despliegue en Railway (backend + BD) + Vercel (frontends)

Esta guía despliega tu sistema completo: el backend y la base de datos en
**Railway**, y los dos frontends en **Vercel**. No necesitas servidor propio
ni Docker.

> **Importante sobre el orden:** hay una dependencia circular natural (el
> frontend necesita la URL del backend, y el backend necesita las URLs del
> frontend para el CORS). Por eso el orden es: 1) backend, 2) frontends,
> 3) volver al backend a completar el CORS. Sigue los pasos tal cual.

---

## Parte A — Backend + Base de datos en Railway

### A1. Crear el proyecto y la base de datos
1. Entra a railway.app e inicia sesión con GitHub.
2. **New Project → Deploy from GitHub repo** y elige el repo del backend.
   - Si tienes los 3 proyectos en un solo repositorio (monorepo), entra a
     **Settings → Root Directory** del servicio y pon la carpeta del backend
     (por ejemplo `backend`).
3. En el mismo proyecto: **New → Database → Add MySQL**. Railway crea la base
   y sus credenciales automáticamente.

### A2. Generar los secretos
En tu computadora (o en cualquier generador confiable) crea dos claves:
```bash
openssl rand -hex 32   # para SECRET_KEY
openssl rand -hex 32   # para CATALOG_API_KEY
```
Guárdalas; las usarás abajo y una de ellas también en el catálogo.

### A3. Variables de entorno del backend
En el servicio del backend → pestaña **Variables**, agrega:

| Variable | Valor |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{MySQL.MYSQL_URL}}` (referencia a tu base; Railway la completa) |
| `SECRET_KEY` | la primera clave generada |
| `CATALOG_API_KEY` | la segunda clave generada |
| `ALLOWED_ORIGINS` | déjalo temporal en `https://example.com` (lo corriges en C) |
| `ALLOWED_HOSTS` | `*` (más adelante lo pones a tu dominio) |
| `DOCS_ENABLED` | `false` |
| `UPLOADS_DIR` | `uploads` |

> El campo `DATABASE_URL`: al escribir el valor, Railway te deja referenciar
> la base con `${{MySQL.MYSQL_URL}}`. El backend ya corrige internamente el
> formato `mysql://` → `mysql+pymysql://`, así que no te preocupes por eso.

### A4. Volumen para las imágenes (importante)
Las imágenes de productos/banners se guardan en disco. Sin un volumen, se
**borran en cada reinicio**. En el servicio del backend:
1. **Settings → Volumes → New Volume**.
2. Mount path: `/app/uploads` (la misma ruta de `UPLOADS_DIR`).

### A5. Desplegar
Railway detecta el proyecto Python y usa el `Procfile` incluido, que corre las
migraciones (`alembic upgrade head`) y arranca el servidor. Cuando termine:
1. **Settings → Networking → Generate Domain**. Copia la URL pública
   (algo como ``). **La necesitarás en la
   Parte B.**
2. Verifica que responde entrando a esa URL: debe mostrar `{"status":"ok",...}`.

---

## Parte B — Frontends en Vercel

Vas a crear **dos proyectos** en Vercel (uno por frontend), ambos desde el
mismo repositorio o desde sus repos respectivos.

### B1. Frontend 1 — Inventario
1. Entra a vercel.com con GitHub → **Add New → Project** y elige el repo.
   - Monorepo: en **Root Directory** elige la carpeta del inventario
     (por ejemplo `frontend`).
   - Framework Preset: **Vite** (lo detecta solo).
2. En **Environment Variables** agrega:

| Variable | Valor |
|---|---|
| `VITE_API_URL` | la URL del backend de Railway (paso A5) |

3. **Deploy**. Al terminar, copia la URL (ej. ``).

### B2. Frontend 2 — Catálogo
1. **Add New → Project** otra vez, mismo repo, pero **Root Directory** =
   carpeta del catálogo (por ejemplo ``).
2. Variables de entorno:

| Variable | Valor |
|---|---|
| `VITE_API_URL` | la URL del backend de Railway |
| `VITE_CATALOG_API_KEY` | **la misma** `CATALOG_API_KEY` del backend (paso A2) |
| `VITE_STORE_NAME` | `Fishing and More - Nasca` |
| `VITE_WHATSAPP_NUMBER` | `` |
| `VITE_TIKTOK_URL` | `` |
| `VITE_FACEBOOK_URL` | `` |

3. **Deploy**. Copia la URL (ej. ``).

> El `vercel.json` incluido en cada frontend ya configura el redireccionamiento
> para que rutas como `/admin/productos` no den error 404 al recargar.

---

## Parte C — Conectar el CORS (volver a Railway)

Ahora que tienes las dos URLs de Vercel, vuelve al backend en Railway →
**Variables** → edita `ALLOWED_ORIGINS` con ambas, separadas por coma y **sin
espacios ni barra final**:

```

```

Guarda; Railway redepliega solo. Con esto, los frontends ya pueden hablar con
el backend.

---

## Parte D — Comprobar que todo funciona
1. Abre la URL del **inventario** → inicia sesión con el usuario administrador
   que ya existe en la base de datos. Crea una categoría y un producto.
2. Abre la URL del **catálogo** → deberías ver el producto. Marca uno como
   destacado desde el panel y súbele una imagen; confirma que aparece.
3. Si el catálogo no carga datos, casi siempre es el CORS (Parte C) o que
   `VITE_CATALOG_API_KEY` no coincide con la del backend.

---

## Más adelante — Tu dominio propio
Cuando tengas el dominio:
- En Vercel (cada frontend): **Settings → Domains** y agrega tu dominio o
  subdominio (ej. `tienda.tudominio.com` y `panel.tudominio.com`). Vercel
  gestiona el HTTPS solo.
- En Railway (backend): **Settings → Networking → Custom Domain** (ej.
  `api.tudominio.com`).
- Actualiza en Railway: `ALLOWED_ORIGINS` con los dominios nuevos y
  `ALLOWED_HOSTS` con el dominio del backend (ej. `api.tudominio.com`).
- Actualiza en Vercel: `VITE_API_URL` con la nueva URL del backend y
  redepliega los frontends.

## Notas
- **Costos:** Vercel tiene plan gratuito generoso para frontends. Railway da
  un crédito mensual de prueba; el backend + MySQL pequeños suelen entrar en lo
  básico, pero revisa su precio actual.
- **Copias de seguridad:** programa respaldo de la base MySQL desde Railway y,
  si puedes, del volumen de `uploads`.
- **Cada push a GitHub** redepliega automáticamente el servicio afectado.
