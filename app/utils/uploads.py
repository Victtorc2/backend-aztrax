"""
Utilidad para subir y gestionar imágenes.

Guarda archivos en subdirectorios del UPLOADS_DIR configurado. Genera nombres
únicos (UUID) para evitar colisiones y valida tipo/tamaño del archivo.
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

# Tipos MIME permitidos.
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# Tamaño máximo: 5 MB.
MAX_SIZE_BYTES = 5 * 1024 * 1024

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _sniff_image_type(data: bytes) -> str | None:
    """
    Detecta el tipo real de imagen leyendo su firma (magic bytes), en vez de
    confiar en el Content-Type que envía el cliente (que es falsificable).

    Devuelve el MIME detectado o None si no corresponde a una imagen soportada.
    """
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _ensure_dir(subdir: str) -> Path:
    """Crea el directorio si no existe y devuelve su Path."""
    path = Path(settings.UPLOADS_DIR) / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_image(file: UploadFile, subdir: str) -> str:
    """
    Guarda una imagen subida y devuelve su ruta relativa (usable como URL).

    Validaciones de seguridad:
    - El contenido se lee con un tope (MAX+1) para no agotar memoria.
    - El tipo se determina por la FIRMA real del archivo, no por el
      Content-Type declarado (defensa contra archivos disfrazados).
    - El nombre se genera con UUID (sin path traversal ni colisiones).

    Args:
        file: archivo subido por el cliente.
        subdir: subdirectorio interno (controlado por la app: "productos"/"banners").

    Returns:
        Ruta relativa tipo "productos/abc123.jpg".

    Raises:
        ValueError: si el tipo o tamaño no son válidos.
    """
    # Leer con tope para evitar cargar archivos enormes en memoria.
    content = await file.read(MAX_SIZE_BYTES + 1)
    if len(content) > MAX_SIZE_BYTES:
        raise ValueError("El archivo supera el tamaño máximo de 5 MB")
    if not content:
        raise ValueError("El archivo está vacío")

    # El tipo real manda; el Content-Type del cliente es solo informativo.
    real_type = _sniff_image_type(content)
    if real_type is None or real_type not in ALLOWED_TYPES:
        raise ValueError(
            "El archivo no es una imagen válida. Solo se aceptan JPG, PNG, WebP o GIF."
        )

    ext = EXTENSIONS[real_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    dirpath = _ensure_dir(subdir)
    filepath = dirpath / filename

    with open(filepath, "wb") as f:
        f.write(content)

    # Ruta relativa que se guarda en la BD y se sirve como URL estática.
    return f"{subdir}/{filename}"


def delete_image(relative_path: str) -> None:
    """
    Elimina una imagen del disco (silencioso si no existe).

    Verifica que la ruta resuelta quede DENTRO de UPLOADS_DIR, para que un
    valor manipulado (p. ej. "../../etc/passwd") nunca pueda borrar archivos
    fuera del directorio de subidas.
    """
    base = Path(settings.UPLOADS_DIR).resolve()
    try:
        full = (base / relative_path).resolve()
        full.relative_to(base)  # lanza ValueError si escapa de base
    except (ValueError, OSError):
        return
    if full.is_file():
        os.remove(full)
