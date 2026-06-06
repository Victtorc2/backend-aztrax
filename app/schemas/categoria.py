"""
Schemas Pydantic para la entidad Categoría.

Incluyen un validador que recorta los espacios sobrantes del nombre, de modo
que " bebidas " se normaliza a "bebidas" antes de llegar al servicio. La
comparación sin distinguir mayúsculas/minúsculas se resuelve en la capa de
servicio/repositorio (no aquí, para preservar el casing original del usuario).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoriaBase(BaseModel):
    """Campos comunes de los schemas de categoría."""

    nombre: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Nombre de la categoría",
        examples=["Bebidas"],
    )

    @field_validator("nombre")
    @classmethod
    def normalizar_nombre(cls, valor: str) -> str:
        """
        Elimina los espacios al inicio/fin y colapsa espacios internos
        repetidos. Tras recortar, el nombre no puede quedar vacío.
        """
        # Colapsa cualquier secuencia de espacios en blanco a uno solo
        # y recorta los extremos: "  Bebidas   frías " -> "Bebidas frías".
        limpio = " ".join(valor.split())
        if not limpio:
            raise ValueError("El nombre no puede estar vacío")
        return limpio


class CategoriaCreate(CategoriaBase):
    """Datos para crear una categoría."""

    pass


class CategoriaUpdate(CategoriaBase):
    """Datos para actualizar una categoría."""

    pass


class CategoriaResponse(CategoriaBase):
    """
    Representación pública de una categoría.

    `from_attributes=True` permite serializar el modelo ORM directamente.
    """

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
