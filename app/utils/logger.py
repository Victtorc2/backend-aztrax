"""
Utilidades de logging reutilizables.

Provee una función simple para obtener loggers con un formato consistente
en todo el proyecto. Centralizarlo aquí facilita cambiar el formato o el
destino de los logs (archivo, servicio externo) en una sola ubicación.
"""

import logging

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger configurado con el formato estándar del proyecto.

    Args:
        name: Nombre del logger, típicamente `__name__` del módulo.

    Returns:
        Un logging.Logger listo para usar.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
