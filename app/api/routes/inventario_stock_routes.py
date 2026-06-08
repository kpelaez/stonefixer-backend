# app/api/routes/inventario_stock_routes.py
"""
Router del módulo Inventario de Stock.

Endpoints:
  POST   /                          → crear relevamiento
  POST   /{id}/ejecutar-scraping    → lanzar background task
  GET    /{id}/estado               → polling del estado del scraping
  GET    /{id}/series               → listar series paginadas
  PATCH  /{id}/resultados-fisicos   → carga masiva del conteo físico
  POST   /{id}/analisis             → generar diferencias
  GET    /{id}/analisis             → ver diferencias
  GET    /{id}/excel                → descargar planilla
  POST   /{id}/ajustes              → crear ajuste
  PATCH  /ajustes/{ajuste_id}/autorizar → autorizar ajuste
  GET    /                          → listar relevamientos

Convenciones del proyecto:
  - 1 router por módulo, registrado en main.py.
  - Excepciones del dominio capturadas aquí y convertidas a HTTPException.
  - BackgroundTasks de FastAPI para el scraping (no Celery, no hay broker).
  - RoleChecker como dependencia para autorizar ajustes (admin/manager).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user, RoleChecker
from app.core.exceptions import ResourceNotFoundError, InvalidOperationError
from app.db.database import get_db
from app.models.inventario_stock import (
    InventarioRelevamientoAjusteRead,
    InventarioRelevamientoRead,
    InventarioRelevamientoSerieRead,
)
from app.models.user import User
from app.schemas.inventario_stock import (
    AjusteAutorizarRequest,
    AjusteCreate,
    AnalisisSummary,
    CargaResultadosFisicosRequest,
    CargaResultadosResponse,
    RelevamientoCreate,
    RelevamientoDetailResponse,
    ScrapingStatusResponse,
    SeriesListResponse,
)
from app.services.inventario_stock_excel import generar_planilla_excel
from app.services.inventario_stock_service import InventarioStockService

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handle_domain_error(exc: Exception) -> None:
    """Convierte excepciones de dominio a HTTPException para FastAPI."""
    if isinstance(exc, ResourceNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, InvalidOperationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    logger.exception("Error inesperado en inventario_stock_routes")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error interno del servidor",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[InventarioRelevamientoRead])
def listar_relevamientos(
    proveedor: str | None = Query(default=None),
    mes_ciclo: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todos los relevamientos. Filtros opcionales por proveedor y mes."""
    try:
        return InventarioStockService.listar_relevamientos(db, proveedor, mes_ciclo)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/", response_model=InventarioRelevamientoRead, status_code=status.HTTP_201_CREATED)
def crear_relevamiento(
    payload: RelevamientoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea la cabecera de un ciclo de relevamiento.
    Estado inicial: PENDIENTE. El scraping se lanza por separado.
    """
    try:
        return InventarioStockService.crear_relevamiento(db, payload, current_user.id)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post(
    "/{relevamiento_id}/ejecutar-scraping",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
)
def ejecutar_scraping(
    relevamiento_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lanza el scraping de Omnimedica + consulta Finnegans en background.
    El cliente debe hacer polling en /{id}/estado para conocer el progreso.

    Retorna inmediatamente con 202 Accepted.
    """
    # Verificar que el relevamiento exista antes de encolar la tarea
    try:
        InventarioStockService.get_relevamiento(db, relevamiento_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    background_tasks.add_task(
        InventarioStockService.ejecutar_scraping, db, relevamiento_id
    )
    logger.info(
        f"[InventarioStock] Scraping encolado para relevamiento #{relevamiento_id} "
        f"por user_id={current_user.id}"
    )
    return {
        "message": "Scraping iniciado en background",
        "relevamiento_id": relevamiento_id,
    }


@router.get("/{relevamiento_id}/estado", response_model=ScrapingStatusResponse)
def obtener_estado_scraping(
    relevamiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Polling para conocer el estado del scraping.
    Retorna estado, totales y errores si los hubiera.
    """
    try:
        rel = InventarioStockService.get_relevamiento(db, relevamiento_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return ScrapingStatusResponse(
        relevamiento_id=rel.id,
        estado=rel.estado,
        total_series_omni=rel.total_series_omni,
        total_codigos_finn=rel.total_codigos_finn,
        scraping_iniciado_en=rel.scraping_iniciado_en,
        scraping_finalizado_en=rel.scraping_finalizado_en,
        scraping_error=rel.scraping_error,
    )


@router.get("/{relevamiento_id}/series", response_model=SeriesListResponse)
def listar_series(
    relevamiento_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    solo_pendientes: bool = Query(default=False),
    solo_diferencias: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista las series del relevamiento con paginación y filtros.
    - `solo_pendientes`: filtra series sin resultado físico cargado.
    - `solo_diferencias`: filtra series con diferencias detectadas.
    """
    try:
        items, total = InventarioStockService.listar_series(
            db, relevamiento_id, page, page_size, solo_pendientes, solo_diferencias
        )
        return SeriesListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[InventarioRelevamientoSerieRead.model_validate(s) for s in items],
        )
    except Exception as exc:
        _handle_domain_error(exc)


@router.patch(
    "/{relevamiento_id}/resultados-fisicos",
    response_model=CargaResultadosResponse,
)
def cargar_resultados_fisicos(
    relevamiento_id: int,
    payload: CargaResultadosFisicosRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Carga masiva de resultados del conteo físico (presente / en_transito / no_encontrada).
    Acepta múltiples series en un solo request para minimizar roundtrips.
    """
    try:
        return InventarioStockService.cargar_resultados_fisicos(
            db, relevamiento_id, payload, current_user.id
        )
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/{relevamiento_id}/analisis", response_model=AnalisisSummary)
def generar_analisis(
    relevamiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera las diferencias a partir del conteo físico cargado.
    Requiere estado EN_CONTEO. Re-ejecutable (borra y regenera diferencias).
    """
    try:
        diferencias = InventarioStockService.generar_analisis(db, relevamiento_id)
        from collections import Counter
        por_tipo = dict(Counter(d.tipo for d in diferencias))
        return AnalisisSummary(
            relevamiento_id=relevamiento_id,
            total_diferencias=len(diferencias),
            por_tipo=por_tipo,
            diferencias=diferencias,
        )
    except Exception as exc:
        _handle_domain_error(exc)


@router.get("/{relevamiento_id}/analisis", response_model=AnalisisSummary)
def ver_analisis(
    relevamiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna las diferencias ya generadas sin volver a calcularlas."""
    from sqlmodel import select
    from app.models.inventario_stock import InventarioRelevamientoDiferencia
    from collections import Counter

    try:
        InventarioStockService.get_relevamiento(db, relevamiento_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    diferencias = list(
        db.exec(
            select(InventarioRelevamientoDiferencia).where(
                InventarioRelevamientoDiferencia.relevamiento_id == relevamiento_id
            )
        ).all()
    )
    por_tipo = dict(Counter(d.tipo for d in diferencias))
    return AnalisisSummary(
        relevamiento_id=relevamiento_id,
        total_diferencias=len(diferencias),
        por_tipo=por_tipo,
        diferencias=diferencias,
    )


@router.get("/{relevamiento_id}/excel")
def descargar_excel(
    relevamiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Descarga la planilla Excel del relevamiento.
    Requiere estado LISTO o superior.
    """
    try:
        rel = InventarioStockService.get_relevamiento(db, relevamiento_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    from app.models.inventario_stock import EstadoRelevamiento

    if rel.estado == EstadoRelevamiento.PENDIENTE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El relevamiento aún no tiene datos. Ejecute el scraping primero.",
        )

    from sqlmodel import select
    from app.models.inventario_stock import InventarioRelevamientoSerie

    series = list(
        db.exec(
            select(InventarioRelevamientoSerie)
            .where(InventarioRelevamientoSerie.relevamiento_id == relevamiento_id)
            .order_by(
                InventarioRelevamientoSerie.codigo,
                InventarioRelevamientoSerie.serie,
            )
        ).all()
    )

    excel_bytes = generar_planilla_excel(rel, series)
    filename = (
        f"relevamiento_{rel.proveedor.replace(' ', '_')}_{rel.mes_ciclo}.xlsx"
    )

    import io

    return StreamingResponse(
        content=io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{relevamiento_id}/ajustes",
    response_model=InventarioRelevamientoAjusteRead,
    status_code=status.HTTP_201_CREATED,
)
def crear_ajuste(
    relevamiento_id: int,
    payload: AjusteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea un ajuste asociado a una diferencia del análisis."""
    try:
        return InventarioStockService.crear_ajuste(
            db, relevamiento_id, payload, current_user.id
        )
    except Exception as exc:
        _handle_domain_error(exc)


@router.patch(
    "/ajustes/{ajuste_id}/autorizar",
    response_model=InventarioRelevamientoAjusteRead,
)
def autorizar_ajuste(
    ajuste_id: int,
    payload: AjusteAutorizarRequest,
    db: Session = Depends(get_db),
    # Solo admin o manager pueden autorizar ajustes
    current_user: User = Depends(RoleChecker(["admin", "manager"])),
):
    """
    Autoriza un ajuste para aplicar en Finnegans.
    Requiere rol admin o manager.
    """
    try:
        return InventarioStockService.autorizar_ajuste(
            db, ajuste_id, payload.nota, current_user.id
        )
    except Exception as exc:
        _handle_domain_error(exc)