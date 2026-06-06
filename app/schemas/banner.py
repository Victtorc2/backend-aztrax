"""
Schemas Pydantic para banners (administración).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BannerCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    orden: int = Field(default=0, ge=0)


class BannerUpdate(BaseModel):
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    orden: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class BannerResponse(BaseModel):
    id: int
    titulo: str
    descripcion: Optional[str]
    imagen_url: str
    orden: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
