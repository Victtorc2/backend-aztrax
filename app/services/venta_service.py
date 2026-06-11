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

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    BoletaNotAvailableError,
    ClienteNotFoundError,
    CreditoSinClienteError,
    ProductoNotFoundError,
    StockInsuficienteError,
    VentaInvalidaError,
    VentaNoEditableError,
    VentaNotFoundError,
    VentaYaAnuladaError,
)
from app.models.venta import DetalleVenta, Venta
from app.pdf.boleta import boleta_filename, generate_boleta_pdf
from app.repositories.caja_repository import CajaRepository
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.producto_repository import ProductoRepository
from app.repositories.venta_repository import VentaRepository
from app.schemas.venta import DescuentoTipo, TipoPago, VentaCreate
from app.services.puntos_service import PuntosService
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

        subtotal, detalles, productos_cant = self._construir_lineas(data.items)

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

        # Vincular la venta a la caja abierta (si la hay) para el arqueo.
        caja_abierta = CajaRepository(self.db).get_abierta()
        if caja_abierta is not None:
            venta.caja_id = caja_abierta.id

        # Otorgar puntos de fidelización si la venta tiene cliente asociado.
        if cliente_id is not None:
            PuntosService(self.db).otorgar_por_venta(cliente_id, total, venta.id)

        self.db.commit()

        return venta

    # ==================================================================
    # Anulación (devolución total)
    # ==================================================================
    def anular_venta(self, venta_id: int, motivo: Optional[str] = None) -> Venta:
        """
        Anula una venta (devolución total): repone el stock de sus productos,
        revierte los puntos otorgados y la marca como anulada. La venta se
        conserva en el historial pero deja de contar en los reportes.

        Raises:
            VentaNotFoundError: si la venta no existe.
            VentaYaAnuladaError: si ya estaba anulada.
        """
        venta = self.repository.get_by_id(venta_id)
        if venta is None:
            raise VentaNotFoundError()
        if venta.anulada:
            raise VentaYaAnuladaError()

        # Reponer stock de las líneas con producto registrado.
        for detalle in venta.detalles:
            if detalle.producto_id is None or detalle.producto is None:
                continue
            producto = detalle.producto
            producto.stock += detalle.cantidad
            producto.estado = calculate_stock_status(
                producto.stock, producto.stock_minimo
            )

        # Revertir los puntos de fidelización que otorgó.
        if venta.cliente_id is not None:
            PuntosService(self.db).revertir_por_venta(venta.cliente_id, venta.id)

        venta.anulada = True
        venta.anulada_at = datetime.utcnow()
        venta.motivo_anulacion = motivo
        # Una deuda de una venta anulada deja de exigirse.
        venta.saldo_pendiente = Decimal("0.00")

        self.db.commit()
        return self.repository.get_by_id(venta_id)  # type: ignore[return-value]

    # ==================================================================
    # Editar venta (modificar boleta dentro del plazo)
    # ==================================================================
    def puede_editarse(self, venta: Venta) -> bool:
        """True si la venta está dentro del plazo de edición y no está anulada."""
        if venta.anulada:
            return False
        fecha = venta.fecha
        if fecha.tzinfo is not None:
            fecha = fecha.replace(tzinfo=None)
        limite = datetime.utcnow() - timedelta(days=settings.VENTA_EDIT_DIAS)
        return fecha >= limite

    def editar_venta(self, venta_id: int, data: VentaCreate) -> Venta:
        """
        Modifica una venta existente dentro del plazo permitido
        (settings.VENTA_EDIT_DIAS días). Recalcula stock, totales y puntos:

        1. Revierte la venta actual: repone el stock de sus productos y los
           puntos que otorgó.
        2. Valida y construye las nuevas líneas (con el stock ya repuesto).
        3. Reemplaza el detalle y recalcula subtotal/descuento/total.
        4. Vuelve a descontar el stock y a otorgar los puntos.

        Conserva el número de boleta, la fecha original y la caja asociada. En
        ventas al crédito recalcula el saldo restando lo ya abonado.

        Raises:
            VentaNotFoundError: la venta no existe.
            VentaNoEditableError: está anulada o fuera de plazo.
            VentaInvalidaError / ProductoNotFoundError / StockInsuficienteError.
        """
        venta = self.repository.get_by_id(venta_id)
        if venta is None:
            raise VentaNotFoundError()
        if venta.anulada:
            raise VentaNoEditableError("No se puede editar una venta anulada")
        if not self.puede_editarse(venta):
            raise VentaNoEditableError(
                f"Solo se puede modificar una venta dentro de "
                f"{settings.VENTA_EDIT_DIAS} días"
            )
        if not data.items:
            raise VentaInvalidaError("La venta debe incluir al menos un producto")

        # 1. Revertir efectos de la venta actual.
        for det in venta.detalles:
            if det.producto_id is not None and det.producto is not None:
                det.producto.stock += det.cantidad
                det.producto.estado = calculate_stock_status(
                    det.producto.stock, det.producto.stock_minimo
                )
        if venta.cliente_id is not None:
            PuntosService(self.db).revertir_por_venta(venta.cliente_id, venta.id)

        # 2. Construir nuevas líneas (valida contra el stock ya repuesto).
        subtotal, detalles, productos_cant = self._construir_lineas(data.items)
        descuento_aplicado = self._calcular_descuento(
            subtotal, data.descuento, data.descuento_tipo
        )
        total = (subtotal - descuento_aplicado).quantize(Decimal("0.01"))
        if total < 0:
            total = Decimal("0.00")

        # 3. Resolver cliente y tipo de pago.
        es_credito = data.tipo_pago == TipoPago.CREDITO
        cliente_id = data.cliente_id
        if es_credito:
            if cliente_id is None:
                raise CreditoSinClienteError()
            if self.cliente_repository.get_by_id(cliente_id) is None:
                raise ClienteNotFoundError()
        elif cliente_id is not None:
            if self.cliente_repository.get_by_id(cliente_id) is None:
                raise ClienteNotFoundError()
        elif data.cliente_nombre or data.cliente_documento:
            cliente_id = self._resolver_cliente_rapido(
                data.cliente_nombre, data.cliente_documento
            )

        # Saldo: en crédito, total menos lo ya abonado (nunca negativo).
        pagado = sum((Decimal(a.monto) for a in venta.abonos), Decimal("0.00"))
        if es_credito:
            saldo = (total - pagado).quantize(Decimal("0.01"))
            if saldo < 0:
                saldo = Decimal("0.00")
        else:
            saldo = Decimal("0.00")

        # 4. Reemplazar el detalle (cascade delete-orphan borra los anteriores).
        venta.detalles = [
            DetalleVenta(
                producto_id=d.get("producto_id"),
                descripcion_libre=d.get("descripcion_libre"),
                cantidad=d["cantidad"],
                precio=d["precio"],
                costo_unitario=d.get("costo_unitario", Decimal("0.00")),
                subtotal=d["subtotal"],
            )
            for d in detalles
        ]
        venta.subtotal = subtotal
        venta.descuento = descuento_aplicado
        venta.descuento_tipo = (
            data.descuento_tipo.value if data.descuento_tipo else None
        )
        venta.total = total
        venta.metodo_pago = data.metodo_pago.value
        venta.tipo_pago = data.tipo_pago.value
        venta.cliente_id = cliente_id
        venta.saldo_pendiente = saldo

        # 5. Descontar el stock nuevo.
        for producto, cantidad in productos_cant:
            producto.stock -= cantidad
            producto.estado = calculate_stock_status(
                producto.stock, producto.stock_minimo
            )

        # 6. Re-otorgar puntos según el total final.
        if cliente_id is not None:
            PuntosService(self.db).otorgar_por_venta(cliente_id, total, venta.id)

        self.db.commit()
        return self.repository.get_by_id(venta_id)  # type: ignore[return-value]

    def _construir_lineas(self, items) -> tuple[Decimal, list[dict], list[tuple]]:
        """
        Valida los items de una venta y construye las líneas de detalle.

        Devuelve (subtotal, detalles, productos_cant) donde:
        - subtotal: suma de las líneas (Decimal, 2 decimales).
        - detalles: lista de dicts para crear DetalleVenta.
        - productos_cant: [(producto, cantidad)] para descontar stock luego.

        Valida existencia y stock de cada producto registrado. Las líneas libres
        (producto_id None) usan el precio escrito a mano y no controlan stock.
        """
        subtotal = Decimal("0.00")
        detalles: list[dict] = []
        productos_cant: list[tuple] = []

        for item in items:
            # --- Línea libre (producto NO registrado, escrito a mano) --------
            if item.producto_id is None:
                precio = Decimal(item.precio)
                costo = Decimal(item.costo) if item.costo is not None else Decimal("0.00")
                linea_subtotal = (precio * item.cantidad).quantize(Decimal("0.01"))
                subtotal += linea_subtotal
                detalles.append(
                    {
                        "producto_id": None,
                        "descripcion_libre": item.descripcion,
                        "cantidad": item.cantidad,
                        "precio": precio,
                        "costo_unitario": costo,
                        "subtotal": linea_subtotal,
                    }
                )
                continue

            # --- Producto registrado: precio del servidor + control de stock -
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

        return subtotal.quantize(Decimal("0.01")), detalles, productos_cant

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
