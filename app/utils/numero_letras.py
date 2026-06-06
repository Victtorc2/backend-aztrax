"""
Conversión de un importe numérico a su representación en letras (español).

Se usa en la boleta para la línea legal "SON: ... SOLES", habitual en los
comprobantes peruanos. Soporta importes hasta 999 999 999.99.
"""

from decimal import Decimal

_UNIDADES = (
    "", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO",
    "NUEVE", "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS",
    "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE",
)
_DECENAS = (
    "", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA",
    "SETENTA", "OCHENTA", "NOVENTA",
)
_CENTENAS = (
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
    "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
)


def _centena_a_letras(n: int) -> str:
    """Convierte un número de 0 a 999 a letras."""
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    centena, resto = divmod(n, 100)
    palabras = _CENTENAS[centena] if centena else ""
    if resto <= 20:
        unidad = _UNIDADES[resto]
    else:
        decena, unidad_n = divmod(resto, 10)
        if 21 <= resto <= 29:
            unidad = "VEINTI" + _UNIDADES[unidad_n].lower().upper()
        else:
            unidad = _DECENAS[decena]
            if unidad_n:
                unidad += f" Y {_UNIDADES[unidad_n]}"
    if palabras and unidad:
        return f"{palabras} {unidad}".strip()
    return (palabras or unidad).strip()


def _entero_a_letras(n: int) -> str:
    """Convierte un entero (0 - 999 999 999) a letras."""
    if n == 0:
        return "CERO"

    millones, resto = divmod(n, 1_000_000)
    miles, centenas = divmod(resto, 1_000)

    partes: list[str] = []
    if millones:
        if millones == 1:
            partes.append("UN MILLON")
        else:
            partes.append(f"{_centena_a_letras(millones)} MILLONES")
    if miles:
        if miles == 1:
            partes.append("MIL")
        else:
            partes.append(f"{_centena_a_letras(miles)} MIL")
    if centenas:
        partes.append(_centena_a_letras(centenas))

    return " ".join(p for p in partes if p).strip()


def monto_en_letras(valor: Decimal | float, moneda: str = "SOLES") -> str:
    """
    Devuelve el importe en letras con el formato típico de la boleta peruana.

    Ejemplo: 1250.50 -> "MIL DOSCIENTOS CINCUENTA CON 50/100 SOLES".
    """
    valor = Decimal(valor).quantize(Decimal("0.01"))
    entero = int(valor)
    centimos = int((valor - entero) * 100)
    letras = _entero_a_letras(entero)
    return f"{letras} CON {centimos:02d}/100 {moneda}"
