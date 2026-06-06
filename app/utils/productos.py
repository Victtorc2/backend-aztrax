"""
Utilidades reutilizables del módulo de productos.

Contiene piezas puras (sin estado ni dependencias de FastAPI/BD):
- `EstadoProducto`: enumeración de los estados posibles según el stock.
- `generate_product_code()`: formatea un código de producto secuencial.
- `calculate_stock_status()`: calcula el estado a partir del stock.

Al ser funciones puras, son triviales de testear y se reutilizan tanto en
la creación como en la actualización de productos, evitando lógica duplicada.
"""

from enum import Enum


class EstadoProducto(str, Enum):
    """
    Estados posibles de un producto según su stock.

    Hereda de `str` para que el valor se serialice directamente como texto
    ("agotado", "bajo_stock", "disponible") en respuestas y filtros.
    """

    AGOTADO = "agotado"
    BAJO_STOCK = "bajo_stock"
    DISPONIBLE = "disponible"


def generate_product_code(sequence: int) -> str:
    """
    Genera un código de producto a partir de un número secuencial.

    Formato: prefijo 'P' + número con 4 dígitos rellenos con ceros.
        1   -> "P0001"
        2   -> "P0002"
        42  -> "P0042"
    Si el secuencial supera 9999, simplemente crece (P10000), sin truncar.

    Args:
        sequence: Número secuencial (>= 1).

    Returns:
        El código de producto formateado.
    """
    return f"P{sequence:04d}"


def calculate_stock_status(stock: int, stock_minimo: int) -> str:
    """
    Calcula el estado de un producto según su stock disponible.

    Reglas (evaluadas en este orden):
        - stock == 0            -> "agotado"
        - stock <= stock_minimo -> "bajo_stock"
        - stock >  stock_minimo -> "disponible"

    Args:
        stock: Unidades disponibles.
        stock_minimo: Umbral mínimo de stock.

    Returns:
        El estado como cadena (uno de los valores de EstadoProducto).
    """
    if stock == 0:
        return EstadoProducto.AGOTADO.value
    if stock <= stock_minimo:
        return EstadoProducto.BAJO_STOCK.value
    return EstadoProducto.DISPONIBLE.value


class EstadoPorPedir(str, Enum):
    """
    Estados válidos para el filtro del módulo de reposición.

    Es un subconjunto de EstadoProducto: solo tiene sentido pedir productos
    que estén agotados o en bajo stock (nunca "disponible").
    """

    AGOTADO = "agotado"
    BAJO_STOCK = "bajo_stock"


def is_product_restock_needed(stock: int, stock_minimo: int) -> bool:
    """
    Indica si un producto necesita reposición ("por pedir").

    Centraliza la regla de negocio del módulo de reposición, unificando las
    dos condiciones en una sola fuente de verdad:
        - agotado:     stock == 0
        - bajo stock:  0 < stock <= stock_minimo

    Dado que el stock y el stock mínimo nunca son negativos, ambas condiciones
    se reducen a `stock <= stock_minimo`.

    Args:
        stock: Unidades disponibles.
        stock_minimo: Umbral mínimo de stock.

    Returns:
        True si el producto debe pedirse (agotado o bajo stock); False si no.
    """
    return stock <= stock_minimo
