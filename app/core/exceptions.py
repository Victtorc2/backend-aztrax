"""
Excepciones personalizadas del dominio.

Definir excepciones propias (en lugar de lanzar HTTPException por todos lados)
nos permite mantener los servicios y repositorios libres de detalles de FastAPI.
Luego, en `main.py`, registramos *exception handlers* que traducen cada una
de estas excepciones a una respuesta HTTP coherente.
"""

from typing import Any, Optional


class AppException(Exception):
    """
    Excepción base de la aplicación.

    Todas las excepciones del dominio heredan de esta. Llevan asociado
    un código de estado HTTP y un mensaje legible.
    """

    status_code: int = 500
    detail: str = "Error interno del servidor"

    def __init__(
        self,
        detail: Optional[str] = None,
        *,
        headers: Optional[dict[str, str]] = None,
        **extra: Any,
    ) -> None:
        if detail is not None:
            self.detail = detail
        self.headers = headers
        self.extra = extra
        super().__init__(self.detail)


class InvalidCredentialsError(AppException):
    """Credenciales incorrectas (correo o contraseña inválidos)."""

    status_code = 401
    detail = "Credenciales incorrectas"


class InvalidTokenError(AppException):
    """El token JWT es inválido o está malformado."""

    status_code = 401
    detail = "Token inválido"


class ExpiredTokenError(AppException):
    """El token JWT ha expirado."""

    status_code = 401
    detail = "El token ha expirado"


class UserNotFoundError(AppException):
    """No existe un usuario con el identificador indicado."""

    status_code = 404
    detail = "Usuario no encontrado"


class EmailAlreadyExistsError(AppException):
    """Ya existe un usuario registrado con ese correo."""

    status_code = 409
    detail = "El correo ya está registrado"


class TooManyRequestsError(AppException):
    """Demasiadas solicitudes (rate limit superado)."""

    status_code = 429
    detail = "Demasiados intentos. Inténtalo más tarde."


# ---------------------------------------------------------------------------
# Categorías (Fase 3)
# ---------------------------------------------------------------------------
class CategoriaNotFoundError(AppException):
    """No existe una categoría con el identificador indicado."""

    status_code = 404
    detail = "Categoría no encontrada"


class CategoriaAlreadyExistsError(AppException):
    """Ya existe una categoría con ese nombre (comparación sin distinguir mayúsculas)."""

    status_code = 400
    detail = "Ya existe una categoría con ese nombre"


class CategoriaHasProductsError(AppException):
    """
    La categoría tiene productos asociados y no puede eliminarse.

    Pensado para integrarse con el módulo de productos en fases futuras.
    """

    status_code = 409
    detail = "No se puede eliminar una categoría asociada a productos"


# ---------------------------------------------------------------------------
# Proveedores (Fase 4)
# ---------------------------------------------------------------------------
class ProveedorNotFoundError(AppException):
    """No existe un proveedor con el identificador indicado."""

    status_code = 404
    detail = "Proveedor no encontrado"


class ProveedorAlreadyExistsError(AppException):
    """Ya existe un proveedor con ese nombre (comparación sin distinguir mayúsculas)."""

    status_code = 400
    detail = "Ya existe un proveedor con ese nombre"


class ProveedorRucAlreadyExistsError(AppException):
    """Ya existe un proveedor registrado con ese RUC."""

    status_code = 400
    detail = "Ya existe un proveedor con ese RUC"


class ProveedorHasProductsError(AppException):
    """
    El proveedor tiene productos asociados y no puede eliminarse.

    Pensado para integrarse con el módulo de productos en fases futuras.
    """

    status_code = 409
    detail = "No se puede eliminar un proveedor asociado a productos"


# ---------------------------------------------------------------------------
# Productos (Fase 5)
# ---------------------------------------------------------------------------
class ProductoNotFoundError(AppException):
    """No existe un producto activo con el identificador indicado."""

    status_code = 404
    detail = "Producto no encontrado"


# ---------------------------------------------------------------------------
# Ventas / Boleta / Historial (Fases 7-11)
# ---------------------------------------------------------------------------
class VentaNotFoundError(AppException):
    """No existe una venta con el identificador indicado."""

    status_code = 404
    detail = "Venta no encontrada"


class BoletaNotAvailableError(AppException):
    """La boleta de la venta no está disponible (no se pudo generar)."""

    status_code = 404
    detail = "Boleta no disponible"


class StockInsuficienteError(AppException):
    """No hay stock suficiente para satisfacer la cantidad solicitada."""

    status_code = 400
    detail = "Stock insuficiente para el producto solicitado"


class VentaInvalidaError(AppException):
    """La venta es inválida (por ejemplo, sin items o con datos incorrectos)."""

    status_code = 400
    detail = "La venta no es válida"


class FiltroInvalidoError(AppException):
    """Un parámetro de filtro/búsqueda es inválido (por ejemplo, fecha mal formada)."""

    status_code = 400
    detail = "Filtro inválido"


# ---------------------------------------------------------------------------
# Clientes y crédito (fiado)
# ---------------------------------------------------------------------------
class ClienteNotFoundError(AppException):
    """El cliente solicitado no existe."""

    status_code = 404
    detail = "Cliente no encontrado"


class ClienteAlreadyExistsError(AppException):
    """Ya existe un cliente con ese documento."""

    status_code = 400
    detail = "Ya existe un cliente con ese documento"


class ClienteHasDeudaError(AppException):
    """No se puede eliminar/desactivar un cliente con deuda pendiente."""

    status_code = 409
    detail = "El cliente tiene deuda pendiente"


class VentaNoEsCreditoError(AppException):
    """Se intentó abonar a una venta que no es al crédito."""

    status_code = 400
    detail = "La venta no es al crédito"


class AbonoInvalidoError(AppException):
    """El monto del abono no es válido (<= 0 o mayor que el saldo)."""

    status_code = 400
    detail = "El monto del abono no es válido"


class CreditoSinClienteError(AppException):
    """Una venta al crédito requiere un cliente asociado."""

    status_code = 400
    detail = "Una venta al crédito requiere un cliente"


# ---------------------------------------------------------------------------
# Fidelización (puntos)
# ---------------------------------------------------------------------------
class PuntosInsuficientesError(AppException):
    """El cliente no tiene suficientes puntos para el canje solicitado."""

    status_code = 400
    detail = "El cliente no tiene suficientes puntos"


class CanjeInvalidoError(AppException):
    """La cantidad de puntos a canjear no es válida (<= 0)."""

    status_code = 400
    detail = "La cantidad de puntos a canjear no es válida"


# ---------------------------------------------------------------------------
# Caja diaria (apertura / cierre / arqueo)
# ---------------------------------------------------------------------------
class CajaYaAbiertaError(AppException):
    """Ya existe una caja abierta; debe cerrarse antes de abrir otra."""

    status_code = 409
    detail = "Ya hay una caja abierta"


class CajaNoAbiertaError(AppException):
    """No hay ninguna caja abierta para la operación solicitada."""

    status_code = 409
    detail = "No hay una caja abierta"


class CajaNotFoundError(AppException):
    """No existe una sesión de caja con el identificador indicado."""

    status_code = 404
    detail = "Sesión de caja no encontrada"


class MovimientoCajaInvalidoError(AppException):
    """El movimiento de caja es inválido (monto <= 0 o tipo desconocido)."""

    status_code = 400
    detail = "El movimiento de caja no es válido"


# ---------------------------------------------------------------------------
# Anulación de ventas (devoluciones)
# ---------------------------------------------------------------------------
class VentaYaAnuladaError(AppException):
    """La venta ya estaba anulada; no puede anularse de nuevo."""

    status_code = 409
    detail = "La venta ya está anulada"


class VentaNoEditableError(AppException):
    """La venta no se puede editar (fuera de plazo o anulada)."""

    status_code = 409
    detail = "La venta ya no se puede modificar"
