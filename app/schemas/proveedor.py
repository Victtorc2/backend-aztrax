"""
Schemas Pydantic para la entidad Proveedor.

Detalles de diseño:
- El nombre se normaliza (recorte y colapso de espacios). La comparación
  sin distinguir mayúsculas/minúsculas para duplicados se hace en la capa
  de servicio/repositorio, preservando aquí el casing original.
- Los campos opcionales se normalizan también: una cadena vacía o de solo
  espacios se convierte en `None`, para no almacenar "basura" en la BD.
- `ProveedorUpdate` tiene TODOS los campos opcionales para permitir
  actualizaciones parciales (PATCH-like) vía PUT.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _limpiar_nombre(valor: str) -> str:
    """Recorta y colapsa espacios; el nombre no puede quedar vacío."""
    limpio = " ".join(valor.split())
    if not limpio:
        raise ValueError("El nombre no puede estar vacío")
    return limpio


def _limpiar_opcional(valor: Optional[str]) -> Optional[str]:
    """
    Normaliza un campo de texto opcional: recorta espacios y, si el resultado
    queda vacío, devuelve None (no se guardan cadenas vacías).
    """
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


class ProveedorCreate(BaseModel):
    """Datos para registrar un proveedor. Solo `nombre` es obligatorio."""

    nombre: str = Field(
        ..., min_length=1, max_length=150, examples=["Distribuidora Norte"]
    )
    telefono: Optional[str] = Field(default=None, max_length=30, examples=["999999999"])
    direccion: Optional[str] = Field(
        default=None, max_length=255, examples=["Av Perú 123"]
    )
    ruc: Optional[str] = Field(default=None, max_length=20, examples=["20456789123"])
    observaciones: Optional[str] = Field(default=None, examples=["Entrega los lunes"])

    @field_validator("nombre")
    @classmethod
    def _v_nombre(cls, v: str) -> str:
        return _limpiar_nombre(v)

    @field_validator("telefono", "direccion", "ruc", "observaciones")
    @classmethod
    def _v_opcionales(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_opcional(v)


class ProveedorUpdate(BaseModel):
    """
    Datos para actualizar un proveedor.

    TODOS los campos son opcionales: el cliente envía únicamente los que
    desea modificar. El servicio aplica solo los campos realmente enviados
    (usando `model_dump(exclude_unset=True)`).
    """

    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=30)
    direccion: Optional[str] = Field(default=None, max_length=255)
    ruc: Optional[str] = Field(default=None, max_length=20)
    observaciones: Optional[str] = Field(default=None)

    @field_validator("nombre")
    @classmethod
    def _v_nombre(cls, v: Optional[str]) -> Optional[str]:
        # Si se envía el nombre, debe normalizarse y no quedar vacío.
        return _limpiar_nombre(v) if v is not None else None

    @field_validator("telefono", "direccion", "ruc", "observaciones")
    @classmethod
    def _v_opcionales(cls, v: Optional[str]) -> Optional[str]:
        return _limpiar_opcional(v)


class ProveedorResponse(BaseModel):
    """Representación pública de un proveedor."""

    id: int
    nombre: str
    telefono: Optional[str]
    direccion: Optional[str]
    ruc: Optional[str]
    observaciones: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
