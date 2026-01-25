from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlmodel import Session

from app.db.database import get_db
from app.models.tech_asset import AssetCategory, AssetStatus, TechAssetResponse, TechAssetSummary, TechAssetUpdate, TechAssetCreate, TechAssetWithAssignment
from app.models.user import User

from app.api.deps import get_current_user, RoleChecker, require_inventory_manager, require_admin
from app.services.tech_asset_service import create_tech_asset, generate_asset_tag, get_tech_assets, get_tech_asset, update_tech_asset, delete_tech_asset, get_tech_assets_count

from app.core.rate_limiter import limiter
from app.config import settings


router = APIRouter()


@router.post("/", response_model=TechAssetResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.CRITICAL_WRITE_RATE_LIMIT) # 20/minuto
def create_tech_asset_endpoint(
    request: Request,
    tech_asset: TechAssetCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_admin) # solo admin
    ):
    """
    Crear un nuevo activo tecnologico
    Permisos: Solo adminsitradores
    Rate limit: 20 requests/minuto
    """
    try:
        print(f"Received tech_asset data: {tech_asset}")  # Para debugging
        result = create_tech_asset(db, tech_asset)
        print(f"Created tech_asset: {result}")  # Para debugging
        return result
    except ValueError as e:
        print(f"ValueError creating tech_asset: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error creating tech_asset: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor")
    
@router.get("/", response_model=List[TechAssetSummary])
@limiter.limit(settings.READ_RATE_LIMIT) #200/minuto
async def get_tech_assets_endpoint(
    request: Request,
    page: int = Query(1,ge=1, description="Numero de pagina (empieza en 1)"),
    page_size: int = Query(50, ge=1, le=100, description="Registros por pagina"),
    category: Optional[AssetCategory] = Query(None, description="Filtrar por categoria"),
    status: Optional[AssetStatus] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)):
    """
    Obtener lista de activos tecnologicos con paginacion

    **Parámetros:**
    - `page`: Número de página (1, 2, 3, ...)
    - `page_size`: Cantidad de registros por página (máx 100)
    - `category`: Filtrar por categoría (opcional)
    - `status`: Filtrar por estado (opcional)

    **Ejemplos:**
    - Primera página: `?page=1&page_size=50`
    - Solo notebooks: `?category=Notebook`
    - Notebooks disponibles: `?category=Notebook&status=available`

    Rate limit: 200 request/minuto
    """
    # Calcular skip basado en pagina
    skip = (page - 1 ) * page_size

    # Obtener total de registros (para calcular paginas)
    total = get_tech_assets_count(
        db,
        category=category,
        status=status,
        include_deleted=False
    )

    # Calcular total de páginas
    total_pages = (total + page_size - 1) // page_size  # Redondeo hacia arriba

    try:
        assets = get_tech_assets(db,skip=skip, limit=page_size, category=category, status=status)
        return assets
    
    except Exception as e:
        print(f"[ERROR] Error obteniendo activos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de activos"
        )

@router.get("/{asset_id}", response_model=TechAssetWithAssignment)
@limiter.limit(settings.READ_RATE_LIMIT) # 200/minuto
async def get_tech_asset_endpoint(
    request: Request,
    asset_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    """
    Obtener un activo tecnologico especifico por ID
    Rate limit: 200 requests/minuto
    """
    tech_asset = get_tech_asset(db, asset_id)
    if not tech_asset:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND, detail="Activo no encontrado"
        )
    return tech_asset

@router.patch("/{asset_id}", response_model=TechAssetResponse)
@limiter.limit(settings.WRITE_RATE_LIMIT) #50/minuto
async def update_tech_asset_endpoint(
    request: Request,
    asset_id: int, 
    tech_asset_update: TechAssetUpdate, 
    current_user: User = Depends(require_inventory_manager), 
    db: Session = Depends(get_db)
    ):
    """
    Actualizar un activo tecnologico

    Permisos: Administradores e Inventory Managers
    Rate limit: 50 requests/minuto
    """
    try:
        print(f"[INFO] Usuario {current_user.email} actualizando activo ID: {asset_id}")
        
        tech_asset = update_tech_asset(db, asset_id, tech_asset_update)
        
        if not tech_asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )
        
        print(f"[SUCCESS] Activo {asset_id} actualizado correctamente")
        return tech_asset
        
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al actualizar el activo"
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.CRITICAL_WRITE_RATE_LIMIT) #20/minuto
async def delete_asset_endpoint(
    request: Request,
    asset_id: int, 
    current_user: User = Depends(require_admin), 
    db: Session = Depends(get_db)):
    """
    Eliminar un activo

    Operacion Critica
    Permiso: Solo administradores
    Rate limit: 20 requests/minuto
    """
    try:
        print(f"[WARNING] Usuario {current_user.email} eliminando activo ID: {asset_id}")
        
        success = delete_tech_asset(db, asset_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )
        
        print(f"[SUCCESS] Activo {asset_id} eliminado correctamente")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Error eliminando activo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al eliminar el activo"
        )

@router.get("/{asset_id}/maintenance-history")
async def get_asset_maintenance_history_endpoint(asset_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener historial de mantenimiento del activo"""
    from app.services.asset_maintenance_service import get_asset_maintenance_history

    asset = get_tech_asset(db, asset_id)
    if not asset: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activo con ID {asset_id} no encontrado"
        )
    
    try:
        history = get_asset_maintenance_history(db, asset_id)
        return history
    except Exception as e:
        print(f"[ERROR] Error obteniendo historial: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el historial de mantenimiento"
        )


@router.get("/categories/list")
async def get_asset_categories(current_user: User = Depends(get_current_user)):
    """Obtener lista de categorías disponibles para activos tecnológicos"""
    try:
        categories = [
            {
                "value": category.value,
                "label": category.value.replace("_", " ").title()
            }
            for category in AssetCategory
        ]
        return categories
    except Exception as e:
        print(f"[ERROR] Error obteniendo categorías: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las categorías"
        )

@router.get("/status/list")
async def get_asset_statuses(current_user: User = Depends(get_current_user)):
    """Obtener lista de estados disponibles para activos tecnológicos"""
    try:
        statuses = [
            {
                "value": status_item.value,
                "label": status_item.value.replace("_", " ").title()
            }
            for status_item in AssetStatus
        ]
        return statuses
    except Exception as e:
        print(f"[ERROR] Error obteniendo estados: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los estados"
        )
    
@router.post("/generate-tag")
#@require_roles(["admin", "inventory_manager"])
async def generate_asset_tag_endpoint(
    request: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)    
):
    """Generar una etiqueta de activo única"""
    try:
        category_value = request.get("category")
        
        if not category_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoría es requerida"
            )
        
        try:
            category = AssetCategory(category_value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Categoría inválida: {category_value}"
            )
        
        tag = generate_asset_tag(db, category)
        
        print(f"[INFO] Tag generado: {tag} para categoría {category.value}")
        
        return {
            "asset_tag": tag,
            "category": category.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Error generando tag: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar el tag del activo"
        )