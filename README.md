# Sistema de Inventario y Ventas — Fases 2 a 11

Autenticación JWT (2), categorías (3), proveedores (4), productos (5),
reposición/por pedir (6), ventas con descuento de stock (7-9), boleta PDF tipo
Perú (10) e historial de ventas (11). Construido sobre FastAPI con arquitectura
limpia y modular, listo para integración con un frontend (React).

## Novedades (mejoras posteriores)

### Clientes, fiado y rentabilidad (último módulo)

- **Clientes**: CRUD completo (`/clientes`), búsqueda por nombre/documento/teléfono,
  baja lógica. Cada cliente muestra su **deuda total**.
- **Venta al crédito (fiado)**: una venta puede ser `contado` o `credito`. La de
  crédito se asocia a un cliente y arranca con `saldo_pendiente` = total.
  Descuenta stock y genera boleta igual que una venta normal.
- **Abonos**: pagos parciales (`POST /ventas/{id}/abonos`) que reducen el saldo
  hasta saldar la deuda. Validan que no superen el saldo.
- **Estado de cuenta** del cliente (`/clientes/{id}/estado-cuenta`) y listado de
  **deudores** (`/clientes/deudores`).
- **Rentabilidad** (`/rentabilidad`): ganancia por producto (con margen %),
  por periodo (día/mes) y resumen global. Usa el **costo congelado** en cada
  venta (`detalle_venta.costo_unitario`), por lo que es fiel aunque cambie el
  precio de compra. Acepta rango de fechas (`desde`/`hasta`).
- Migraciones `0008` (clientes + crédito + costo) y `0009` (abonos).


- **Producto: campo `modelo`** (opcional). Indexado e incluido en las
  búsquedas (`/productos/buscar` y `?search=`). Migración `0006`.
- **Venta: forma de pago** `efectivo` | `yape` (`metodo_pago`). Se valida en
  el schema, se guarda en BD, aparece en el historial y **se imprime en la
  boleta PDF**. Migración `0007`.
- **Dashboard de métricas** (`GET /dashboard`, `GET /dashboard/resumen`): KPIs
  de ventas e inventario, top de productos, desglose por método de pago y
  serie temporal de ventas por día para gráficos.
- **Seguridad reforzada**:
  - Validación de `SECRET_KEY` fuerte y contraseña admin en producción
    (`ENVIRONMENT=production`).
  - **Rate limiting** anti fuerza bruta en `/auth/login` (responde `429` con
    `Retry-After` tras varios intentos fallidos por IP+correo).
  - Cabeceras de seguridad (`X-Frame-Options`, `X-Content-Type-Options`,
    `Referrer-Policy`, `Permissions-Policy`, y `HSTS` en producción).
  - CORS restringido a métodos y cabeceras concretos.
  - Handler global que registra errores no controlados sin filtrar detalles
    internos al cliente.
- Corrección de `requirements.txt` a **MySQL** (`pymysql`), coherente con
  `DATABASE_URL`.

## Características

### Fase 2 — Autenticación
- Login con JWT (`POST /auth/login`) y endpoint `GET /auth/me`.
- Hash seguro de contraseñas con **bcrypt**.
- Usuario administrador creado **automáticamente** al arrancar (idempotente).

### Fase 3 — Categorías (CRUD)
- CRUD completo en `/categorias`, **todas las rutas protegidas con JWT**.
- Nombres únicos ignorando mayúsculas/minúsculas y espacios.
- Listado ordenado por fecha descendente y búsqueda parcial (`?search=`).
- Eliminación bloqueada si tiene productos asociados (preparado para el futuro).

### Fase 4 — Proveedores (CRUD)
- CRUD completo en `/proveedores`, **todas las rutas protegidas con JWT**.
- Campos: nombre (obligatorio), telefono, direccion, ruc, observaciones.
- Nombres únicos (ignorando mayúsculas/espacios) y **RUC único** si se envía.
- **Actualización parcial**: solo se modifican los campos enviados.
- Búsqueda parcial por **nombre o RUC** (`?search=`).
- Eliminación bloqueada si tiene productos asociados.

### Fase 5 — Productos (CRUD)
- CRUD completo en `/productos`, **todas las rutas protegidas con JWT**.
- Campos: codigo (autogenerado), nombre, **marca**, categoria_id, proveedor_id,
  precio_compra, precio_venta, stock, stock_minimo, estado, created_at.
- **Código automático** secuencial (P0001, P0002, ...).
- **Estado automático** según el stock: `agotado` (0), `bajo_stock` (≤ mínimo),
  `disponible` (> mínimo). Se recalcula al actualizar el stock.
- Relaciones con categoría y proveedor (validadas al crear/editar).
- Filtros combinables (`?search=`, `?categoria=`, `?proveedor=`, `?estado=`) y
  búsqueda dedicada `GET /productos/buscar?q=` (nombre, código o marca).
- **Soft delete** (`is_active`): los productos no se borran físicamente.

### Fase 6 — Productos por pedir (reposición)
- Reutiliza el modelo Producto; **no crea tablas nuevas**.
- `GET /productos/agotados`: stock 0 o estado "agotado".
- `GET /productos/bajo-stock`: bajo el mínimo pero no agotados.
- `GET /productos/por-pedir`: lista combinada (agotados primero, luego bajo
  stock), con filtros `?estado=`, `?categoria=`, `?proveedor=` y `?search=`.
- Regla de reposición centralizada en `is_product_restock_needed()`.
- Consultas optimizadas con `joinedload` (sin N+1).

### Fases 7-9 — Ventas (base)
- `POST /ventas`: registra una venta, toma el precio de venta vigente, aplica
  descuento (monto o porcentaje), genera el número de boleta (`B001-000001`),
  descuenta el stock y recalcula el estado de cada producto.

### Fase 10 — Boleta PDF (formato ticket peruano)
- `GET /ventas/{id}/boleta`: genera y devuelve la boleta en `application/pdf`
  con `Content-Disposition` (`boleta_B001-000001.pdf`).
- Generada con **reportlab** en `app/pdf/boleta.py`. Encabezado del negocio,
  datos de venta, tabla de items, totales en `S/` y mensaje final.
- El generador recibe la venta ya cargada (sin consultas extra).

### Fase 11 — Historial de ventas
- `GET /historial`: listado paginado descendente con filtros `?fecha=`,
  `?fecha_inicio=&fecha_fin=`, `?boleta=` (parcial), `?page=`, `?page_size=`.
- `GET /historial/{id}`: detalle completo (cabecera + líneas con producto,
  marca, código, cantidad, precio y subtotal).
- `GET /historial/{id}/boleta`: reimprime la boleta **reutilizando**
  `generate_boleta()` (sin duplicar lógica).
- Carga optimizada con `selectinload` + `joinedload` (sin N+1).

### Común
- Manejo **centralizado** de errores vía excepciones de dominio.
- Arquitectura por capas: modelos, schemas, repositorios, servicios, rutas,
  dependencias.

## Estructura del proyecto

```
app/
├── api/
│   ├── router.py            # Agregador de routers
│   └── routes/
│       └── auth.py          # Endpoints /auth/login y /auth/me
├── core/
│   ├── config.py            # Configuración desde .env (pydantic-settings)
│   ├── security.py          # hash_password, verify_password, JWT
│   └── exceptions.py        # Excepciones de dominio
├── db/
│   ├── base.py              # Base declarativa SQLAlchemy
│   ├── session.py           # engine, SessionLocal, get_db
│   └── init_db.py           # Seed del administrador
├── dependencies/
│   └── auth.py              # get_current_user (Depends reutilizable)
├── models/
│   └── user.py              # Modelo ORM Usuario
├── repositories/
│   └── user_repository.py   # Acceso a datos
├── schemas/
│   ├── user.py              # UserCreate, UserLogin, UserResponse
│   └── token.py             # Token, TokenData
├── services/
│   └── auth_service.py      # Lógica de negocio (login, register)
├── utils/
│   └── logger.py            # Helper de logging
└── main.py                  # App, lifespan, exception handlers
alembic/                     # Migraciones
```

## Requisitos

- Python 3.11+
- PostgreSQL

## Instalación

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Edita .env y ajusta DATABASE_URL y SECRET_KEY
```

Genera una clave secreta robusta:

```bash
openssl rand -hex 32
```

## Migraciones (Alembic)

```bash
# Aplicar las migraciones a la base de datos
alembic upgrade head

# (Opcional) generar una nueva migración tras cambiar modelos
alembic revision --autogenerate -m "descripcion del cambio"
```

> Nota: al arrancar, la app también ejecuta `create_all()` como respaldo en
> desarrollo. En producción, las migraciones de Alembic son la fuente de verdad.

## Ejecución

```bash
uvicorn app.main:app --reload
```

La API quedará disponible en `http://localhost:8000`.

## Probar en Swagger

1. Abre `http://localhost:8000/docs`.
2. Ejecuta **POST /auth/login** con:
   ```json
   { "correo": "admin@sistema.com", "password": "admin123" }
   ```
3. Copia el `access_token` de la respuesta.
4. Pulsa el botón **Authorize** (arriba a la derecha) y pega el token.
5. Ejecuta **GET /auth/me**: devolverá los datos del administrador.

## Endpoints de categorías (requieren token)

| Método | Ruta                  | Descripción                          |
|--------|-----------------------|--------------------------------------|
| POST   | `/categorias`         | Crear categoría                      |
| GET    | `/categorias`         | Listar (acepta `?search=`)           |
| GET    | `/categorias/{id}`    | Obtener por id                       |
| PUT    | `/categorias/{id}`    | Actualizar nombre                    |
| DELETE | `/categorias/{id}`    | Eliminar (bloqueada si tiene productos) |

Errores principales: `400` nombre duplicado, `404` categoría no encontrada,
`409` categoría con productos asociados, `401` sin token o token inválido.

## Endpoints de proveedores (requieren token)

| Método | Ruta                  | Descripción                          |
|--------|-----------------------|--------------------------------------|
| POST   | `/proveedores`        | Registrar proveedor                  |
| GET    | `/proveedores`        | Listar (acepta `?search=` por nombre o RUC) |
| GET    | `/proveedores/{id}`   | Obtener por id                       |
| PUT    | `/proveedores/{id}`   | Actualizar (parcial)                 |
| DELETE | `/proveedores/{id}`   | Eliminar (bloqueada si tiene productos) |

Errores principales: `400` nombre o RUC duplicado, `404` proveedor no
encontrado, `409` proveedor con productos asociados, `401` sin token.

## Endpoints de productos (requieren token)

| Método | Ruta                  | Descripción                          |
|--------|-----------------------|--------------------------------------|
| POST   | `/productos`          | Registrar (código y estado automáticos) |
| GET    | `/productos`          | Listar con filtros (`search`, `categoria`, `proveedor`, `estado`) |
| GET    | `/productos/buscar`   | Buscar por nombre, código o marca (`?q=`) |
| GET    | `/productos/{id}`     | Obtener por id                       |
| PUT    | `/productos/{id}`     | Actualizar (parcial, recalcula estado) |
| DELETE | `/productos/{id}`     | Eliminar (soft delete)               |

Errores principales: `404` producto/categoría/proveedor no encontrado,
`422` precios no positivos o stock negativo, `401` sin token.

## Endpoints de reposición / por pedir (requieren token)

| Método | Ruta                      | Descripción                          |
|--------|---------------------------|--------------------------------------|
| GET    | `/productos/agotados`     | Productos agotados                   |
| GET    | `/productos/bajo-stock`   | Productos con bajo stock (no agotados) |
| GET    | `/productos/por-pedir`    | Combinada, con filtros y búsqueda    |

Filtros de `/productos/por-pedir`: `?estado=agotado|bajo_stock`, `?categoria=`,
`?proveedor=`, `?search=` (nombre o código). Errores: `404` categoría/proveedor
inexistente en filtro, `422` estado inválido, `401` sin token.

## Endpoints de ventas, boleta e historial (requieren token)

| Método | Ruta                       | Descripción                          |
|--------|----------------------------|--------------------------------------|
| POST   | `/ventas`                  | Registrar venta (descuenta stock)    |
| GET    | `/ventas/{id}/boleta`      | Generar/descargar boleta PDF         |
| GET    | `/historial`               | Listado paginado con filtros         |
| GET    | `/historial/{id}`          | Detalle de una venta                 |
| GET    | `/historial/{id}/boleta`   | Reimprimir boleta PDF                |

Datos del negocio para la boleta (configurables en `.env`): `BUSINESS_NAME`,
`BUSINESS_RUC`, `BUSINESS_ADDRESS`, `BUSINESS_CITY`, `BUSINESS_PHONE`,
`BOLETA_SERIE`. Errores: `404` venta no encontrada / boleta no disponible,
`400` stock insuficiente, `422` fecha o datos inválidos, `401` sin token.


