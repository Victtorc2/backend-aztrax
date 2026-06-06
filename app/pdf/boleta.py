"""
Generación de la boleta en PDF (formato ticket térmico 80 mm).

Diseño inspirado en una boleta de venta electrónica peruana real:
- Encabezado con datos del negocio.
- Recuadro con el RUC, el tipo de comprobante y la serie-correlativo.
- Datos del cliente y de la venta.
- Tabla de items con columnas CANT. / DESCRIPCIÓN / P.U. / IMPORTE.
- Desglose de Op. Gravada + IGV (18%) = Total.
- Importe total en letras ("SON: ...").
- Forma de pago, saldo (en ventas al crédito) y pie legal.

Usa reportlab dibujando sobre un canvas de ancho de ticket (80 mm). El alto
se calcula dinámicamente según el contenido, para que el comprobante no tenga
espacio sobrante ni se corte.

La función recibe un objeto `Venta` YA cargado con sus detalles y productos
(el servicio se encarga de la carga optimizada), por lo que aquí no se hace
ninguna consulta a la base de datos.
"""

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.models.venta import Venta
from app.utils.numero_letras import monto_en_letras

# --- Dimensiones del ticket -------------------------------------------------
TICKET_WIDTH = 80 * mm          # ancho estándar de impresora térmica
MARGIN = 5 * mm                 # margen lateral
LINE_HEIGHT = 4.2 * mm          # alto de cada línea de texto
CONTENT_WIDTH = TICKET_WIDTH - 2 * MARGIN

# IGV peruano (18%). El total de la venta YA incluye el IGV; aquí se
# descompone para mostrar el desglose habitual del comprobante.
IGV_RATE = Decimal("0.18")


def _money(value: Decimal | float) -> str:
    """Formatea un importe como moneda peruana: S/ 25.50."""
    return f"S/ {Decimal(value):.2f}"


def _wrap(text: str, font: str, size: int, max_width: float) -> list[str]:
    """Parte un texto en varias líneas para que quepa en `max_width`."""
    palabras = text.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if stringWidth(prueba, font, size) <= max_width:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [""]


def _estimate_height(venta: Venta) -> float:
    """
    Estima el alto necesario del ticket según su contenido.

    Se cuenta de forma holgada: encabezado, recuadro del comprobante, datos de
    cliente/venta, una a tres líneas por item, totales, importe en letras
    (puede ocupar varias líneas), forma de pago y pie legal.
    """
    n_items_lineas = 0
    for d in venta.detalles:
        nombre = f"{d.producto.nombre} {d.producto.marca or ''}".strip()
        n_items_lineas += len(_wrap(nombre, "Helvetica", 7, CONTENT_WIDTH)) + 1

    # Bloques fijos: encabezado del negocio (~4), recuadro del comprobante (~4),
    # datos cliente/venta (~5), cabecera de tabla (~2), totales (~6), importe en
    # letras (~2), forma de pago (~4) y pie legal (~3). Más un pequeño colchón.
    lineas = 4 + 4 + 5 + 2 + n_items_lineas + 6 + 2 + 4 + 3
    return lineas * LINE_HEIGHT + 10 * mm


def generate_boleta_pdf(venta: Venta) -> bytes:
    """
    Genera el PDF de la boleta para una venta y devuelve los bytes.

    Args:
        venta: Venta con `detalles` y, en cada detalle, `producto` cargados.

    Returns:
        El contenido del PDF en bytes (listo para enviar como descarga).
    """
    buffer = BytesIO()
    height = _estimate_height(venta)
    c = canvas.Canvas(buffer, pagesize=(TICKET_WIDTH, height))

    # Cursor vertical: empezamos arriba y vamos bajando.
    y = height - MARGIN

    def text_center(s: str, font: str = "Helvetica", size: int = 8,
                    gap: float = LINE_HEIGHT) -> None:
        nonlocal y
        c.setFont(font, size)
        c.drawCentredString(TICKET_WIDTH / 2, y, s)
        y -= gap

    def text_left(s: str, font: str = "Helvetica", size: int = 7,
                  gap: float = LINE_HEIGHT, x: float = MARGIN) -> None:
        nonlocal y
        c.setFont(font, size)
        c.drawString(x, y, s)
        y -= gap

    def label_value(label: str, value: str, size: int = 7) -> None:
        """Etiqueta en negrita a la izquierda y su valor a continuación."""
        nonlocal y
        c.setFont("Helvetica-Bold", size)
        c.drawString(MARGIN, y, label)
        w = stringWidth(label + " ", "Helvetica-Bold", size)
        c.setFont("Helvetica", size)
        c.drawString(MARGIN + w, y, value)
        y -= LINE_HEIGHT

    def sep(dashed: bool = True) -> None:
        """Dibuja una línea separadora de borde a borde."""
        nonlocal y
        y += LINE_HEIGHT * 0.3
        if dashed:
            c.setDash(1, 2)
        c.setLineWidth(0.4)
        c.line(MARGIN, y, TICKET_WIDTH - MARGIN, y)
        c.setDash()
        y -= LINE_HEIGHT * 0.9

    # --- Encabezado: datos del negocio ---------------------------------
    text_center(settings.BUSINESS_NAME.upper(), font="Helvetica-Bold", size=11,
                gap=LINE_HEIGHT * 1.1)
    text_center(settings.BUSINESS_ADDRESS, size=7)
    text_center(f"{settings.BUSINESS_CITY}  -  Tel. {settings.BUSINESS_PHONE}", size=7)
    y -= LINE_HEIGHT * 0.5

    # --- Recuadro del comprobante (RUC + tipo + serie-correlativo) -----
    box_top = y + LINE_HEIGHT * 0.6
    box_lines = 3
    box_height = box_lines * LINE_HEIGHT + LINE_HEIGHT * 0.8
    box_bottom = box_top - box_height
    c.setLineWidth(0.9)
    c.rect(MARGIN, box_bottom, CONTENT_WIDTH, box_height)
    y = box_top - LINE_HEIGHT
    text_center(f"R.U.C. {settings.BUSINESS_RUC}", font="Helvetica-Bold", size=8)
    text_center("BOLETA DE VENTA ELECTRÓNICA", font="Helvetica-Bold", size=8)
    text_center(venta.numero_boleta, font="Helvetica-Bold", size=9)
    y = box_bottom - LINE_HEIGHT * 0.8

    # --- Datos de la venta y del cliente -------------------------------
    fecha = venta.fecha
    label_value("Fecha:", fecha.strftime("%d/%m/%Y"))
    label_value("Hora:", fecha.strftime("%H:%M:%S"))

    cliente = getattr(venta, "cliente", None)
    nombre_cliente = (cliente.nombre if cliente and cliente.nombre else "Cliente varios")
    documento = cliente.documento if cliente and cliente.documento else "-"
    for linea in _wrap(f"Cliente: {nombre_cliente}", "Helvetica", 7, CONTENT_WIDTH):
        text_left(linea, size=7)
    label_value("DNI/RUC:", documento)
    sep()

    # --- Cabecera de la tabla de items ---------------------------------
    col_pu = TICKET_WIDTH - MARGIN - 18 * mm     # columna "P.U."
    col_imp = TICKET_WIDTH - MARGIN               # columna "IMPORTE" (derecha)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(MARGIN, y, "CANT  DESCRIPCIÓN")
    c.drawRightString(col_pu, y, "P.U.")
    c.drawRightString(col_imp, y, "IMPORTE")
    y -= LINE_HEIGHT
    sep()

    # --- Items ---------------------------------------------------------
    for d in venta.detalles:
        nombre = d.producto.nombre
        if d.producto.marca:
            nombre = f"{nombre} - {d.producto.marca}"
        # Descripción del producto (puede ocupar varias líneas).
        for linea in _wrap(nombre, "Helvetica", 7, CONTENT_WIDTH):
            text_left(linea, font="Helvetica", size=7, gap=LINE_HEIGHT * 0.95)
        # Línea de cantidad / precio unitario / importe.
        c.setFont("Helvetica", 7)
        c.drawString(MARGIN, y, f"{d.cantidad} x")
        c.drawRightString(col_pu, y, _money(d.precio))
        c.drawRightString(col_imp, y, _money(d.subtotal))
        y -= LINE_HEIGHT
    sep()

    # --- Pie: desglose de totales (Op. Gravada + IGV = Total) ----------
    total = Decimal(venta.total)
    gravada = (total / (Decimal("1") + IGV_RATE)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    igv = (total - gravada).quantize(Decimal("0.01"))

    def total_line(label: str, value: str, bold: bool = False,
                   size: int | None = None) -> None:
        nonlocal y
        font = "Helvetica-Bold" if bold else "Helvetica"
        fsize = size or (10 if bold else 8)
        c.setFont(font, fsize)
        c.drawString(MARGIN, y, label)
        c.drawRightString(TICKET_WIDTH - MARGIN, y, value)
        y -= LINE_HEIGHT

    total_line("Subtotal:", _money(venta.subtotal))
    if venta.descuento and Decimal(venta.descuento) > 0:
        total_line("Descuento:", f"- {_money(venta.descuento)}")
    total_line("Op. Gravada:", _money(gravada))
    total_line("IGV (18%):", _money(igv))
    y -= LINE_HEIGHT * 0.2
    total_line("TOTAL A PAGAR:", _money(total), bold=True)
    sep()

    # --- Importe en letras ---------------------------------------------
    letras = f"SON: {monto_en_letras(total)}"
    for linea in _wrap(letras, "Helvetica-Bold", 7, CONTENT_WIDTH):
        text_left(linea, font="Helvetica-Bold", size=7, gap=LINE_HEIGHT * 0.95)
    y -= LINE_HEIGHT * 0.3

    # --- Forma de pago / crédito ---------------------------------------
    metodo = (venta.metodo_pago or "efectivo").capitalize()
    tipo_pago = (venta.tipo_pago or "contado").capitalize()
    label_value("Condición:", tipo_pago)
    label_value("Forma de pago:", metodo)
    if venta.saldo_pendiente and Decimal(venta.saldo_pendiente) > 0:
        label_value("Saldo pendiente:", _money(venta.saldo_pendiente))
    sep()

    # --- Pie legal -----------------------------------------------------
    y -= LINE_HEIGHT * 0.2
    for linea in _wrap(
        "Representación impresa de la Boleta de Venta Electrónica.",
        "Helvetica", 6, CONTENT_WIDTH
    ):
        text_center(linea, font="Helvetica", size=6, gap=LINE_HEIGHT * 0.85)
    y -= LINE_HEIGHT * 0.3
    text_center("¡Gracias por su compra!", font="Helvetica-Bold", size=9)

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def boleta_filename(numero_boleta: str) -> str:
    """Nombre de archivo de la boleta: boleta_B001-000001.pdf."""
    return f"boleta_{numero_boleta}.pdf"
