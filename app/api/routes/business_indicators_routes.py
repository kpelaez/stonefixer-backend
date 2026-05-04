from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.engine import Connection
import time
import logging
import asyncio
from functools import wraps

from app.db.kpi_database import get_kpi_db, get_connection_pool_stats
from app.models.business_indicators import (
    BusinessIndicator,
    BusinessIndicatorsRequest,
    BusinessIndicatorsResponse,
    IndicatorHistory,
    IndicatorsHealth,
    IndicatorType
)

# Importar las funciones del servicio OPTIMIZADO
from app.services.business_indicators_service import (
    get_business_indicators,
    get_indicator_by_id,
    get_indicator_history,
    get_indicators_health,
)
from app.api.deps import get_current_user
from app.models.user import User

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter()

# === DECORATOR PARA FASTAPI ===
def log_performance(endpoint_name: str):
    """Decorator CORREGIDO para FastAPI async functions"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    end_time = time.time()
                    execution_time = (end_time - start_time) * 1000
                    
                    if execution_time > 1000:
                        logger.warning(f"{endpoint_name} tardó {execution_time:.0f}ms")
                    else:
                        logger.info(f"{endpoint_name} completado en {execution_time:.0f}ms")
                    
                    return result
                except Exception as e:
                    end_time = time.time()
                    execution_time = (end_time - start_time) * 1000
                    logger.error(f" {endpoint_name} falló después de {execution_time:.0f}ms: {str(e)}")
                    raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    end_time = time.time()
                    execution_time = (end_time - start_time) * 1000
                    
                    if execution_time > 1000:
                        logger.warning(f"{endpoint_name} tardó {execution_time:.0f}ms")
                    else:
                        logger.info(f"{endpoint_name} completado en {execution_time:.0f}ms")
                    
                    return result
                except Exception as e:
                    end_time = time.time()
                    execution_time = (end_time - start_time) * 1000
                    logger.error(f"{endpoint_name} falló después de {execution_time:.0f}ms: {str(e)}")
                    raise
            return sync_wrapper
    return decorator

# === ENDPOINTS PRINCIPALES ===

@router.get("/", response_model=BusinessIndicatorsResponse)
@log_performance("get_business_indicators")
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
    OPTIMIZADO: Obtener todos los indicadores de negocio
    """
    try:
        logger.info("Iniciando get_business_indicators_endpoint")
        
        # Crear objeto request para el servicio
        request = BusinessIndicatorsRequest(
            date_from=date_from,
            date_to=date_to,
            period=period,
            include_history=include_history,
            indicator_types=indicator_types
        )
        
        # Usar servicio optimizado
        logger.info("Ejecutando consulta optimizada...")
        service_start = time.time()
        result = get_business_indicators(request)
        service_end = time.time()
        
        service_time = (service_end - service_start) * 1000
        logger.info(f"Servicio completado en {service_time:.0f}ms")
        
        # Agregar metadata de rendimiento
        result.metadata = {
            "optimization": "v2.0",
            "single_query": True,
            "pool_optimized": True,
            "service_time_ms": round(service_time, 2),
            "indicators_count": len(result.indicators)
        }
        
        logger.info(f"Devolviendo {len(result.indicators)} indicadores")
        return result
        
    except Exception as e:
        logger.error(f"Error en get_business_indicators_endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error obteniendo indicadores: {str(e)}"
        )

@router.get("/{indicator_id}", response_model=BusinessIndicator)
@log_performance("get_indicator_by_id")
async def get_indicator_by_id_endpoint(
    indicator_id: str,
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    OPTIMIZADO: Obtener un indicador específico por ID
    """
    try:
        logger.info(f"Obteniendo indicador: {indicator_id}")
        
        # Validar ID de indicador
        valid_ids = ["total_facturado", "total_cobrado", "ratio_cobranza"]
        if indicator_id not in valid_ids:
            raise HTTPException(
                status_code=404, 
                detail=f"Indicador '{indicator_id}' no encontrado. IDs válidos: {valid_ids}"
            )
        
        request = BusinessIndicatorsRequest(
            date_from=date_from,
            date_to=date_to
        )
        
        result = get_indicator_by_id(indicator_id, request)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error obteniendo indicador {indicator_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo indicador: {str(e)}")

@router.get("/{indicator_id}/history", response_model=List[IndicatorHistory])
@log_performance("get_indicator_history")
async def get_indicator_history_endpoint(
    indicator_id: str,
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    OPTIMIZADO: Obtener el histórico de un indicador específico
    """
    try:
        logger.info(f"Obteniendo histórico de: {indicator_id}")
        
        # Validar ID de indicador
        valid_ids = ["total_facturado", "total_cobrado", "ratio_cobranza"]
        if indicator_id not in valid_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico para indicador '{indicator_id}' no disponible. IDs válidos: {valid_ids}"
            )
        
        result = get_indicator_history(indicator_id, date_from, date_to)
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo histórico de {indicator_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo histórico: {str(e)}")

@router.get("/health/status", response_model=IndicatorsHealth)
@log_performance("get_indicators_health")
async def get_indicators_health_endpoint(
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    OPTIMIZADO: Obtener el estado de salud de los indicadores
    """
    try:
        logger.info("Verificando salud de indicadores")
        result = get_indicators_health()
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de salud: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado de salud: {str(e)}")

# === ENDPOINTS DE DIAGNÓSTICO AVANZADO ===

@router.get("/debug/database-performance")
@log_performance("debug_database_performance")
async def debug_database_performance_endpoint(
    current_user: User = Depends(get_current_user),
    kpi_db: Connection = Depends(get_kpi_db)
):
    """
    NUEVO: Diagnóstico completo de rendimiento de base de datos
    """
    try:
        from sqlalchemy import text
        
        logger.info("Iniciando diagnóstico completo de base de datos...")
        
        results = {}
        
        # 1. Test de conexión básica
        start_time = time.time()
        result = kpi_db.execute(text("SELECT 1"))
        result.fetchone()
        end_time = time.time()
        
        results["connection_test"] = {
            "time_ms": round((end_time - start_time) * 1000, 2),
            "status": "success"
        }
        
        # 2. Test de count en vista
        start_time = time.time()
        result = kpi_db.execute(text("SELECT COUNT(*) FROM produccion.vw_facturacion_vs_cobranza"))
        count = result.fetchone()[0]
        end_time = time.time()
        
        count_time = (end_time - start_time) * 1000
        results["view_count_test"] = {
            "time_ms": round(count_time, 2),
            "total_rows": count,
            "status": "slow" if count_time > 2000 else "normal"
        }
        
        # 3. Test de consulta mes actual
        start_time = time.time()
        result = kpi_db.execute(text("""
            SELECT anio_mes, total_facturado, total_cobrado
            FROM produccion.vw_facturacion_vs_cobranza 
            WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
        """))
        rows = result.fetchall()
        end_time = time.time()
        
        current_month_time = (end_time - start_time) * 1000
        results["current_month_test"] = {
            "time_ms": round(current_month_time, 2),
            "rows_found": len(rows),
            "status": "slow" if current_month_time > 3000 else "normal",
            "data": [{"anio_mes": row.anio_mes, "facturado": float(row.total_facturado), "cobrado": float(row.total_cobrado)} for row in rows[:1]]
        }
        
        # 4. Test de consulta optimizada
        start_time = time.time()
        optimized_query = """
        WITH current_data AS (
            SELECT 
                anio_mes,
                total_facturado,
                total_cobrado,
                CASE 
                    WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                    ELSE 0
                END as ratio_cobranza
            FROM produccion.vw_facturacion_vs_cobranza 
            WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
        )
        SELECT * FROM current_data
        """
        result = kpi_db.execute(text(optimized_query))
        row = result.fetchone()
        end_time = time.time()
        
        optimized_time = (end_time - start_time) * 1000
        results["optimized_query_test"] = {
            "time_ms": round(optimized_time, 2),
            "status": "slow" if optimized_time > 5000 else "normal",
            "data": {
                "facturado": float(row.total_facturado) if row and row.total_facturado else 0,
                "cobrado": float(row.total_cobrado) if row and row.total_cobrado else 0,
                "ratio": float(row.ratio_cobranza) if row and row.ratio_cobranza else 0
            } if row else None
        }
        
        # 5. Diagnóstico general
        total_time = current_month_time + optimized_time
        
        if total_time > 8000:
            diagnosis = "CRITICAL: Vista de base de datos extremadamente lenta"
            recommendations = [
                "Contactar DBA para optimizar vista vw_facturacion_vs_cobranza",
                "Implementar caché agresivo en aplicación",
                "Considerar tabla materializada"
            ]
        elif total_time > 3000:
            diagnosis = "WARNING: Rendimiento subóptimo de vista"
            recommendations = [
                "Revisar índices en tablas base de la vista",
                "Implementar caché de resultados"
            ]
        else:
            diagnosis = "OK: Rendimiento aceptable"
            recommendations = ["Monitorear periódicamente"]
        
        results["diagnosis"] = {
            "overall_status": diagnosis,
            "total_query_time_ms": round(total_time, 2),
            "recommendations": recommendations
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Error en diagnóstico de base de datos: {str(e)}")
        raise