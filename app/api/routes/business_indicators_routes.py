from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from app.db.kpi_database import get_kpi_db
from app.models.business_indicators import (
    BusinessIndicator,
    BusinessIndicatorsRequest,
    BusinessIndicatorsResponse,
    IndicatorHistory,
    IndicatorsHealth,
    IndicatorType
)
# Importar las funciones del servicio refactorizado
from app.services.business_indicators_service import (
    get_business_indicators,
    get_indicator_by_id,
    get_indicator_history,
    get_indicators_health,
)
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BusinessIndicatorsResponse)
async def get_business_indicators_endpoint(
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    period: Optional[str] = Query("daily", description="Período: daily, weekly, monthly"),
    include_history: bool = Query(False, description="Incluir histórico"),
    indicator_types: Optional[List[IndicatorType]] = Query(None, description="Tipos de indicadores"),
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    Obtener todos los indicadores de negocio
    
    - **date_from**: Filtrar desde esta fecha
    - **date_to**: Filtrar hasta esta fecha  
    - **period**: Período de agrupación (daily, weekly, monthly)
    - **include_history**: Si incluir datos históricos
    - **indicator_types**: Tipos específicos de indicadores
    """
    try:
        request = BusinessIndicatorsRequest(
            date_from=date_from,
            date_to=date_to,
            period=period,
            include_history=include_history,
            indicator_types=indicator_types
        )
        
        result = get_business_indicators(request)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo indicadores: {str(e)}")

@router.get("/{indicator_id}", response_model=BusinessIndicator)
async def get_indicator_by_id_endpoint(
    indicator_id: str,
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    period: Optional[str] = Query("daily", description="Período: daily, weekly, monthly"),
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    Obtener un indicador específico por ID
    
    - **indicator_id**: ID único del indicador (total_facturado, total_cobrado, ratio_cobranza)
    - **date_from**: Filtrar desde esta fecha
    - **date_to**: Filtrar hasta esta fecha
    - **period**: Período de agrupación
    """
    try:
        request = BusinessIndicatorsRequest(
            date_from=date_from,
            date_to=date_to,
            period=period
        ) if any([date_from, date_to, period != "daily"]) else None
        
        result = get_indicator_by_id(indicator_id, request)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo indicador: {str(e)}")

@router.get("/{indicator_id}/history", response_model=List[IndicatorHistory])
async def get_indicator_history_endpoint(
    indicator_id: str,
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    Obtener el histórico de un indicador específico
    
    - **indicator_id**: ID único del indicador (total_facturado, total_cobrado, ratio_cobranza)
    - **date_from**: Filtrar desde esta fecha
    - **date_to**: Filtrar hasta esta fecha
    """
    try:
        result = get_indicator_history(indicator_id, date_from, date_to)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo histórico: {str(e)}")


@router.get("/health/status", response_model=IndicatorsHealth)
async def get_indicators_health_endpoint(
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    Obtener el estado de salud de los indicadores
    
    Retorna un resumen del estado general de todos los indicadores,
    incluyendo estadísticas y problemas detectados.
    """
    try:
        result = get_indicators_health()
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado de salud: {str(e)}")

# Endpoint adicional para testing de conexión
@router.get("/test/connection")
async def test_kpi_connection(
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """Endpoint para probar la conexión a la base de datos de KPIs"""
    try:
        from sqlalchemy import text
        result = kpi_db.execute(text("SELECT 1 as test"))
        test_value = result.fetchone().test
        
        return {
            "status": "success",
            "message": "Conexión a KPI database exitosa",
            "test_value": test_value,
            "database": "defaultdb"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de conexión: {str(e)}") 
