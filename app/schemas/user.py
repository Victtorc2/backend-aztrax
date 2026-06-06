"""
Schemas Pydantic para la entidad Usuario.

Los schemas definen el contrato de entrada/salida de la API y validan
los datos automáticamente. Separarlos del modelo ORM nos permite controlar
qué se expone (por ejemplo, NUNCA exponemos `password_hash`).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Campos comunes compartidos por varios schemas de usuario."""

    nombre: str = Field(..., min_length=1, max_length=120, examples=["Administrador"])
    correo: EmailStr = Field(..., examples=["admin@sistema.com"])


class UserCreate(UserBase):
    """
    Datos necesarios para crear un usuario.

    Recibe la contraseña en texto plano; el servicio se encarga de
    hashearla antes de persistirla.
    """

    password: str = Field(..., min_length=6, max_length=128, examples=["admin123"])


class UserLogin(BaseModel):
    """Credenciales que envía el cliente al endpoint de login."""

    correo: EmailStr = Field(..., examples=["admin@sistema.com"])
    password: str = Field(..., examples=["admin123"])


class UserResponse(UserBase):
    """
    Representación pública de un usuario.

    Excluye deliberadamente `password_hash`. `from_attributes=True`
    permite construir el schema directamente desde el objeto ORM.
    """

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
