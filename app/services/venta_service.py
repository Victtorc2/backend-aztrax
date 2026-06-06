"""
Servicio de ventas, boleta e historial (Fases 7-11 condensadas + 10-11).

Responsabilidades:
- Registrar una venta: validar stock, calcular subtotal/descuento/total,
  generar el número de boleta y descontar el stock (recalculando el estado
  del producto, reutilizando la regla de la Fase 5).
- Generar/Reimprimir la boleta en PDF (delegando en app.pdf.boleta).
- Consultar el historial (listado paginado, por fecha, por boleta, detalle).

No conoce FastAPI: lanza excepciones de dominio que la API traduce a HTTP.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BoletaNotAvailableError,
    ClienteNotFoundError,
    CreditoSinClienteError,
    ProductoNotFoundError,
    StockInsuficienteError,
    VentaInvalidaError,
    VentaNotFoundError,
)
from app.models.venta import Venta
from app.pdf.boleta import boleta_filename, generate_boleta_pdf
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.producto_repository import ProductoRepository
from app.repositories.venta_repository import VentaRepository
from app.schemas.venta import DescuentoTipo, TipoPago, VentaCreate
from app.utils.productos import calculate_stock_status


class VentaService:
    """Orquesta los casos de uso de ventas, boleta e historial."""

    # Máximo de resultados por página en el historial (evita respuestas enormes).
    MAX_PAGE_SIZE = 100

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = VentaRepository(db)
        self.producto_repository = ProductoRepository(db)
        self.cliente_repository = ClienteRepository(db)

    # ==================================================================
    # Registrar venta (base necesaria para boleta e historial)
    # ==================================================================
    def registrar_venta(self, data: VentaCreate) -> Venta:
        """
        Registra una venta completa.

        Pasos:
            1. Validar cada producto (existe y tiene stock suficiente).
            2. Calcular el subtotal a partir del precio de venta actual.
            3. Aplicar el descuento (monto o porcentaje) y obtener el total.
            4. Generar el número de boleta.
            5. Persistir la venta + detalles.
            6. Descontar el stock y recalcular el estado de cada producto.

        Raises:
            VentaInvalidaError: si no hay items.
            ProductoNotFoundError: si un producto no existe/está inactivo.
            StockInsuficienteError: si la cantidad supera el stock.
        """
        if not data.items:
            raise VentaInvalidaError("La venta debe incluir al menos un producto")

        subtotal = Decimal("0.00")
        detalles: list[dict] = []
        # Guardamos referencias a los productos para descontar stock luego.
        productos_cant: list[tuple] = []

        for item in data.items:
            producto = self.producto_repository.get_by_id(item.producto_id)
            if producto is None:
                raise ProductoNotFoundError(
                    f"Producto {item.producto_id} no encontrado"
                )
            if item.cantidad > producto.stock:
                raise StockInsuficienteError(
                    f"Stock insuficiente para '{producto.nombre}' "
                    f"(disponible: {producto.stock}, solicitado: {item.cantidad})"
                )

            precio = Decimal(producto.precio_venta)
            costo = Decimal(producto.precio_compra)
            linea_subtotal = (precio * item.cantidad).quantize(Decimal("0.01"))
            subtotal += linea_subtotal
            detalles.append(
                {
                    "producto_id": producto.id,
                    "cantidad": item.cantidad,
                    "precio": precio,
                    "costo_unitario": costo,
                    "subtotal": linea_subtotal,
                }
            )
            productos_cant.append((producto, item.cantidad))

        subtotal = subtotal.quantize(Decimal("0.01"))
        descuento_aplicado = self._calcular_descuento(
            subtotal, data.descuento, data.descuento_tipo
        )
        total = (subtotal - descuento_aplicado).quantize(Decimal("0.01"))
        if total < 0:
            total = Decimal("0.00")

        numero_boleta = self.repository.next_numero_boleta()

        # --- Resolver tipo de pago (contado / crédito) --------------------
        es_credito = data.tipo_pago == TipoPago.CREDITO
        cliente_id = data.cliente_id
        saldo_pendiente = Decimal("0.00")

        if es_credito:
            # Una venta al crédito necesita un cliente válido.
            if cliente_id is None:
                raise CreditoSinClienteError()
            if self.cliente_repository.get_by_id(cliente_id) is None:
                raise ClienteNotFoundError()
            # El saldo inicial de la deuda es el total de la venta.
            saldo_pendiente = total
        elif cliente_id is not None:
            # Venta al contado con cliente asociado (opcional): validar que exista.
            if self.cliente_repository.get_by_id(cliente_id) is None:
                raise ClienteNotFoundError()
        elif data.cliente_nombre or data.cliente_documento:
            # Venta al contado con datos rápidos del cliente (nombre y/o DNI):
            # se busca por documento; si no existe, se crea con esos datos para
            # que luego puedas completar su ficha en el módulo de clientes.
            cliente_id = self._resolver_cliente_rapido(
                data.cliente_nombre, data.cliente_documento
            )

        venta = self.repository.create_venta(
            numero_boleta=numero_boleta,
            subtotal=subtotal,
            descuento=descuento_aplicado,
            descuento_tipo=data.descuento_tipo.value if data.descuento_tipo else None,
            total=total,
            detalles=detalles,
            metodo_pago=data.metodo_pago.value,
            tipo_pago=data.tipo_pago.value,
            cliente_id=cliente_id,
            saldo_pendiente=saldo_pendiente,
        )

        # Descontar stock y recalcular estado (reutiliza la regla de Fase 5).
        for producto, cantidad in productos_cant:
            producto.stock -= cantidad
            producto.estado = calculate_stock_status(
                producto.stock, producto.stock_minimo
            )
        self.db.commit()

        return venta

    def _resolver_cliente_rapido(
        self, nombre: Optional[str], documento: Optional[str]
    ) -> Optional[int]:
        """
        Resuelve el cliente de una venta al contado con datos rápidos.

        - Si hay documento y ya existe un cliente con él, devuelve ese id.
        - Si hay documento nuevo, crea el cliente (con nombre si se dio, o el
          documento como nombre provisional).
        - Si solo hay nombre, crea un cliente con ese nombre.

        Devuelve el id del cliente, o None si no hay datos suficientes.
        """
        nombre = (nombre or "").strip()
        documento = (documento or "").strip()

        if documento:
            existente = self.cliente_repository.get_by_documento(documento)
            if existente is not None:
                # Si el cliente existía sin nombre y ahora lo tenemos, lo completamos.
                if nombre and (not existente.nombre or existente.nombre == existente.documento):
                    self.cliente_repository.update(existente, {"nombre": nombre})
                return existente.id
            nuevo = self.cliente_repository.create_cliente(
                nombre=nombre or documento,
                documento=documento,
            )
            return nuevo.id

        if nombre:
            nuevo = self.cliente_repository.create_cliente(nombre=nombre)
            return nuevo.id

        return None

    def _calcular_descuento(
        self,
        subtotal: Decimal,
        descuento: Decimal,
        tipo: Optional[DescuentoTipo],
    ) -> Decimal:
        """
        Calcula el monto de descuento efectivo.

        - tipo "porcentaje": `descuento` es un % (0-100) del subtotal.
        - tipo "monto" o None: `descuento` es un importe fijo en soles.
        El descuento nunca supera el subtotal.
        """
        if descuento <= 0:
            return Decimal("0.00")

        if tipo == DescuentoTipo.PORCENTAJE:
            pct = min(Decimal(descuento), Decimal("100"))
            monto = (subtotal * pct / Decimal("100")).quantize(Decimal("0.01"))
        else:
            monto = Decimal(descuento).quantize(Decimal("0.01"))

        return min(monto, subtotal)

    # ==================================================================
    # Boleta PDF (Fase 10)
    # ==================================================================
    def generate_boleta(self, venta_id: int) -> tuple[bytes, str]:
        """
        Genera (o reimprime) la boleta PDF de una venta.

        Returns:
            (pdf_bytes, filename) listos para devolver como descarga.

        Raises:
            VentaNotFoundError: si la venta no existe.
            BoletaNotAvailableError: si la venta no tiene número de boleta.
        """
        venta = self.repository.get_by_id(venta_id)
        if venta is None:
            raise VentaNotFoundError()
        if not venta.numero_boleta:
            raise BoletaNotAvailableError()

        try:
            pdf_bytes = generate_boleta_pdf(venta)
        except Exception as exc:  # pragma: no cover - error de render improbable
            # Si el render falla, lo tratamos como boleta no disponible.
            raise BoletaNotAvailableError() from exc

        return pdf_bytes, boleta_filename(venta.numero_boleta)

    # ==================================================================
    # Historial (Fase 11)
    # ==================================================================
    def listar_historial(
        self,
        page: int = 1,
        page_size: int = 20,
        boleta: Optional[str] = None,
        fecha: Optional[date] = None,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
    ) -> tuple[Sequence[Venta], int, int, int]:
        """
        Lista paginada del historial con filtros.

        Returns:
            (ventas_pagina, total, page, page_size) — normaliza page/page_size.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, self.MAX_PAGE_SIZE))

        ventas, total = self.repository.get_historial(
            page=page,
            page_size=page_size,
            boleta=boleta,
            fecha=fecha,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        return ventas, total, page, page_size

    def obtener_detalle(self, venta_id: int) -> Venta:
        """
        Devuelve el detalle completo de una venta.

        Raises:
            VentaNotFoundError: si la venta no existe.
        """
        venta = self.repository.get_by_id(venta_id)
        if venta is None:
            raise VentaNotFoundError()
        return venta
