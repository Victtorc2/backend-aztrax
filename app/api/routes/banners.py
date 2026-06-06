"""
Rutas de administración de banners e imágenes.

Protegidas con JWT. Permiten subir banners promocionales y fotos de productos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.models.banner import Banner
from app.models.producto import Producto
from app.schemas.banner import BannerCreate, BannerResponse, BannerUpdate
from app.utils.uploads import delete_image, save_image

router = APIRouter(
    tags=["Banners e imágenes"],
    dependencies=[Depends(get_current_user)],
)

# =====================================================================
# Upload de imagen de producto
# =====================================================================


@router.post(
    "/productos/{producto_id}/imagen",
    summary="Subir o reemplazar la imagen de un producto",
    status_code=status.HTTP_200_OK,
)
async def subir_imagen_producto(
    producto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    file: UploadFile = File(..., description="Imagen JPG/PNG/WebP (máx 5 MB)"),
) -> dict:
    """
    Sube una imagen para un producto. Si ya tenía una, la reemplaza
    (borra la anterior del disco).
    """
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    try:
        relative_path = await save_image(file, "productos")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Borrar imagen anterior si existía.
    if producto.imagen_url:
        delete_image(producto.imagen_url)

    producto.imagen_url = relative_path
    db.commit()

    return {"imagen_url": relative_path}


@router.delete(
    "/productos/{producto_id}/imagen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar la imagen de un producto",
)
def eliminar_imagen_producto(
    producto_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if producto.imagen_url:
        delete_image(producto.imagen_url)
        producto.imagen_url = None
        db.commit()
    return None


# =====================================================================
# CRUD de banners
# =====================================================================


@router.get(
    "/banners",
    response_model=list[BannerResponse],
    summary="Listar todos los banners (admin)",
)
def listar_banners(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> list[BannerResponse]:
    stmt = select(Banner).order_by(Banner.orden.asc(), Banner.id.desc())
    return [BannerResponse.model_validate(b) for b in db.scalars(stmt).all()]


@router.post(
    "/banners",
    response_model=BannerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un banner (subir imagen + datos)",
)
async def crear_banner(
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    file: UploadFile = File(..., description="Imagen del banner"),
    titulo: str = Form(default="Promoción"),
    descripcion: str | None = Form(default=None),
    orden: int = Form(default=0),
) -> BannerResponse:
    try:
        relative_path = await save_image(file, "banners")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    banner = Banner(
        titulo=titulo,
        descripcion=descripcion,
        imagen_url=relative_path,
        orden=orden,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return BannerResponse.model_validate(banner)


@router.put(
    "/banners/{banner_id}",
    response_model=BannerResponse,
    summary="Actualizar un banner",
)
def actualizar_banner(
    banner_id: int,
    data: BannerUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> BannerResponse:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    cambios = data.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(banner, campo, valor)
    db.commit()
    db.refresh(banner)
    return BannerResponse.model_validate(banner)


@router.put(
    "/banners/{banner_id}/imagen",
    summary="Reemplazar la imagen de un banner",
)
async def reemplazar_imagen_banner(
    banner_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
    file: UploadFile = File(...),
) -> dict:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    try:
        new_path = await save_image(file, "banners")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    delete_image(banner.imagen_url)
    banner.imagen_url = new_path
    db.commit()
    return {"imagen_url": new_path}


@router.delete(
    "/banners/{banner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un banner",
)
def eliminar_banner(
    banner_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: CurrentUser,
) -> None:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    delete_image(banner.imagen_url)
    db.delete(banner)
    db.commit()
    return None
