"""
Reporte de inventario de productos en PDF (formato A4 horizontal).

Genera una tabla profesional con los productos (aplicando los mismos filtros
que el listado) e incluye un encabezado con los datos del negocio, la fecha de
emisión, los filtros aplicados y un resumen al pie (totales y valorización del
inventario a precio de venta).

Usa reportlab Platypus (Table/SimpleDocTemplate) para el maquetado y la
paginación automática. La función recibe los productos YA cargados (con sus
relaciones), por lo que aquí no se consulta la base de datos.
"""

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings
from app.models.producto import Producto

# Colores corporativos del reporte.
_HEADER_BG = colors.HexColor("#1f2937")    # gris azulado oscuro
_HEADER_FG = colors.white
_ROW_ALT = colors.HexColor("#f3f4f6")      # gris muy claro (filas alternas)
_BORDER = colors.HexColor("#d1d5db")
_ACCENT = colors.HexColor("#2563eb")

# Etiquetas legibles para el estado del producto.
_ESTADO_LABEL = {
    "disponible": "Disponible",
    "bajo_stock": "Bajo stock",
    "agotado": "Agotado",
}


def _money(value: Decimal | float) -> str:
    """Formatea un importe como moneda peruana: S/ 25.50."""
    return f"S/ {Decimal(value):.2f}"


def _resumen_filtros(
    search: Optional[str],
    categoria: Optional[str],
    proveedor: Optional[str],
    estado: Optional[str],
) -> str:
    """Construye una frase legible con los filtros aplicados."""
    partes: list[str] = []
    if search:
        partes.append(f"búsqueda «{search}»")
    if categoria:
        partes.append(f"categoría: {categoria}")
    if proveedor:
        partes.append(f"proveedor: {proveedor}")
    if estado:
        partes.append(f"estado: {_ESTADO_LABEL.get(estado, estado)}")
    return "Filtros: " + ", ".join(partes) if partes else "Sin filtros (todos los productos)"


def generate_reporte_productos_pdf(
    productos: Sequence[Producto],
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    proveedor: Optional[str] = None,
    estado: Optional[str] = None,
) -> bytes:
    """
    Genera el PDF del reporte de inventario y devuelve los bytes.

    Args:
        productos: secuencia de productos (con `categoria` y `proveedor`
            cargados) ya filtrada por la capa de servicio.
        search/categoria/proveedor/estado: descripción de los filtros usados,
            solo para mostrarlos en el encabezado del reporte.

    Returns:
        El contenido del PDF en bytes (listo para enviar como descarga).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title="Reporte de inventario",
        author=settings.BUSINESS_NAME,
    )

    styles = getSampleStyleSheet()
    estilo_negocio = ParagraphStyle(
        "Negocio", parent=styles["Title"], fontSize=16, leading=19,
        textColor=_HEADER_BG, spaceAfter=2,
    )
    estilo_titulo = ParagraphStyle(
        "Subtitulo", parent=styles["Normal"], fontSize=11, leading=14,
        textColor=_ACCENT, spaceAfter=2, fontName="Helvetica-Bold",
    )
    estilo_meta = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=8, leading=11,
        textColor=colors.HexColor("#4b5563"),
    )
    estilo_celda = ParagraphStyle(
        "Celda", parent=styles["Normal"], fontSize=7.5, leading=9,
    )

    elementos: list = []

    # --- Encabezado ----------------------------------------------------
    elementos.append(Paragraph(settings.BUSINESS_NAME.upper(), estilo_negocio))
    elementos.append(Paragraph("REPORTE DE INVENTARIO DE PRODUCTOS", estilo_titulo))
    emitido = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    elementos.append(Paragraph(f"RUC: {settings.BUSINESS_RUC}", estilo_meta))
    elementos.append(Paragraph(f"Emitido: {emitido}", estilo_meta))
    elementos.append(Paragraph(
        _resumen_filtros(search, categoria, proveedor, estado), estilo_meta
    ))
    elementos.append(Spacer(1, 6 * mm))

    # --- Tabla ---------------------------------------------------------
    encabezados = [
        "#", "Código", "Producto", "Marca", "Categoría", "Proveedor",
        "P. Compra", "P. Venta", "Stock", "Estado",
    ]
    filas: list[list] = [encabezados]

    valor_compra = Decimal("0.00")
    valor_venta = Decimal("0.00")
    total_unidades = 0

    for i, p in enumerate(productos, start=1):
        categoria_nombre = p.categoria.nombre if p.categoria else "-"
        proveedor_nombre = p.proveedor.nombre if p.proveedor else "-"
        valor_compra += Decimal(p.precio_compra) * p.stock
        valor_venta += Decimal(p.precio_venta) * p.stock
        total_unidades += p.stock

        filas.append([
            str(i),
            p.codigo,
            Paragraph(p.nombre, estilo_celda),
            Paragraph(p.marca or "-", estilo_celda),
            Paragraph(categoria_nombre, estilo_celda),
            Paragraph(proveedor_nombre, estilo_celda),
            _money(p.precio_compra),
            _money(p.precio_venta),
            str(p.stock),
            _ESTADO_LABEL.get(p.estado, p.estado),
        ])

    if len(filas) == 1:
        filas.append(["", "", Paragraph("Sin productos para los filtros indicados.",
                                        estilo_celda), "", "", "", "", "", "", ""])

    # Anchos de columna (suman ~273 mm útiles en A4 horizontal).
    col_widths = [
        8 * mm, 18 * mm, 58 * mm, 30 * mm, 34 * mm, 34 * mm,
        24 * mm, 24 * mm, 16 * mm, 22 * mm,
    ]
    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    estilo_tabla = TableStyle([
        # Cabecera.
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Cuerpo.
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (6, 1), (8, -1), "RIGHT"),    # precios y stock a la derecha
        ("ALIGN", (0, 1), (1, -1), "CENTER"),   # # y código centrados
        ("ALIGN", (9, 1), (9, -1), "CENTER"),   # estado centrado
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
    ])
    tabla.setStyle(estilo_tabla)
    elementos.append(tabla)

    # --- Resumen al pie ------------------------------------------------
    elementos.append(Spacer(1, 6 * mm))
    resumen = [
        [
            Paragraph("<b>Total de productos</b>", estilo_celda),
            Paragraph("<b>Total de unidades en stock</b>", estilo_celda),
            Paragraph("<b>Valor a precio de compra</b>", estilo_celda),
            Paragraph("<b>Valor a precio de venta</b>", estilo_celda),
        ],
        [
            str(len(productos)),
            str(total_unidades),
            _money(valor_compra),
            _money(valor_venta),
        ],
    ]
    tabla_resumen = Table(resumen, colWidths=[50 * mm, 60 * mm, 55 * mm, 55 * mm])
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ROW_ALT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (3, 1), _ACCENT),
    ]))
    elementos.append(tabla_resumen)

    def _pie(canvas_obj, doc_obj) -> None:
        """Pie de página con numeración."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#9ca3af"))
        canvas_obj.drawCentredString(
            doc_obj.pagesize[0] / 2, 8 * mm,
            f"{settings.BUSINESS_NAME} — Página {doc_obj.page}",
        )
        canvas_obj.restoreState()

    doc.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def reporte_filename() -> str:
    """Nombre del archivo del reporte con fecha: reporte_inventario_20260606.pdf."""
    fecha = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M")
    return f"reporte_inventario_{fecha}.pdf"
