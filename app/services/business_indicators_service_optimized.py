from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.kpi_database import get_kpi_engine
from app.models.business_indicators import (
    BusinessIndicator,
    IndicatorColor, 
    IndicatorHistory, 
    BusinessIndicatorsRequest,
    BusinessIndicatorsResponse,
    IndicatorsHealth,
    IndicatorType,
    TrendDirection,
    IndicatorStatus
)

def convert_date_to_datetime(date_obj) -> datetime:
    """Convertir date object a datetime para compatibilidad con Pydantic"""
    if isinstance(date_obj, date) and not isinstance(date_obj, datetime):
        return datetime.combine(date_obj, datetime.min.time())
    elif isinstance(date_obj, datetime):
        return date_obj
    else:
        if isinstance(date_obj, str):
            try:
                return datetime.strptime(date_obj, '%Y-%m-%d')
            except:
                return datetime.now()
        return datetime.now()

def get_all_indicators_optimized(kpi_conn: Connection) -> List[BusinessIndicator]:
    """
    OPTIMIZACIÓN PRINCIPAL: Una sola consulta para todos los indicadores
    """
    
    query = """
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
    ),
    previous_data AS (
        SELECT 
            anio_mes,
            total_facturado,
            total_cobrado,
            CASE 
                WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                ELSE 0
            END as ratio_cobranza
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes = TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYY-MM')
    )
    SELECT 
        -- Datos actuales
        c.total_facturado as current_facturado,
        c.total_cobrado as current_cobrado,
        c.ratio_cobranza as current_ratio,
        
        -- Datos anteriores para calcular tendencias
        p.total_facturado as prev_facturado,
        p.total_cobrado as prev_cobrado,
        p.ratio_cobranza as prev_ratio,
        
        -- Metadatos
        c.anio_mes as current_period,
        p.anio_mes as prev_period
    FROM current_data c
    LEFT JOIN previous_data p ON 1=1
    """
    
    try:
        result = kpi_conn.execute(text(query))
        row = result.fetchone()
        
        if not row:
            raise ValueError("No hay datos disponibles para el período actual")
        
        indicators = []
        
        # Helper function para calcular tendencia
        def calculate_trend(current: float, previous: Optional[float]) -> tuple[TrendDirection, Optional[float]]:
            if previous is None or previous == 0:
                return TrendDirection.STABLE, None
            
            percentage_change = ((current - previous) / previous) * 100
            
            if percentage_change > 5:
                return TrendDirection.UP, percentage_change
            elif percentage_change < -5:
                return TrendDirection.DOWN, percentage_change
            else:
                return TrendDirection.STABLE, percentage_change
        
        # 1. Total Facturado
        trend_dir, trend_pct = calculate_trend(
            row.current_facturado, 
            row.prev_facturado
        )
        
        facturado_indicator = BusinessIndicator(
            id="ventas",
            name="Total Facturado",
            description="Facturación total del mes actual",
            value=float(row.current_facturado),
            unit="USD",
            type=IndicatorType.REVENUE,
            color=IndicatorColor.GREEN,
            trend_direction=trend_dir,
            trend_percentage=trend_pct,
            status=IndicatorStatus.HEALTHY,
            target_value=None,
            last_updated=datetime.now(),
            metadata={"period": row.current_period}
        )
        indicators.append(facturado_indicator)
        
        # 2. Total Cobrado
        trend_dir, trend_pct = calculate_trend(
            row.current_cobrado, 
            row.prev_cobrado
        )
        
        cobrado_indicator = BusinessIndicator(
            id="cobranzas",
            name="Total Cobrado",
            description="Total cobrado del mes actual",
            value=float(row.current_cobrado),
            unit="USD",
            type=IndicatorType.REVENUE,
            color=IndicatorColor.BLUE,
            trend_direction=trend_dir,
            trend_percentage=trend_pct,
            status=IndicatorStatus.HEALTHY,
            target_value=None,
            last_updated=datetime.now(),
            metadata={"period": row.current_period}
        )
        indicators.append(cobrado_indicator)
        
        # 3. Ratio de Cobranza
        trend_dir, trend_pct = calculate_trend(
            row.current_ratio, 
            row.prev_ratio
        )
        
        # Determinar status basado en el ratio
        if row.current_ratio >= 80:
            status = IndicatorStatus.HEALTHY
            color = IndicatorColor.GREEN
        elif row.current_ratio >= 60:
            status = IndicatorStatus.WARNING
            color = IndicatorColor.YELLOW
        else:
            status = IndicatorStatus.CRITICAL
            color = IndicatorColor.RED
        
        ratio_indicator = BusinessIndicator(
            id="giro_negocio",
            name="Giro de Negocio",
            description="Porcentaje de cobranza vs facturación",
            value=float(row.current_ratio),
            unit="%",
            type=IndicatorType.FINANCIAL,
            color=color,
            trend_direction=trend_dir,
            trend_percentage=trend_pct,
            status=status,
            target_value=85.0,
            last_updated=datetime.now(),
            metadata={"period": row.current_period}
        )
        indicators.append(ratio_indicator)
        
        return indicators
        
    except Exception as e:
        print(f"Error obteniendo indicadores optimizados: {e}")
        raise Exception(f"Error obteniendo indicadores: {str(e)}")

def get_business_indicators(request: Optional[BusinessIndicatorsRequest] = None) -> BusinessIndicatorsResponse:
    """
    FUNCIÓN PRINCIPAL OPTIMIZADA: Una sola conexión, una sola consulta
    """
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            # Una sola llamada para obtener todos los indicadores
            indicators = get_all_indicators_optimized(kpi_conn)
            
            return BusinessIndicatorsResponse(
                indicators=indicators,
                total_count=len(indicators),
                last_updated=datetime.now()
            )
            
        except Exception as e:
            print(f"Error general obteniendo indicadores: {e}")
            raise Exception(f"Error obteniendo indicadores: {str(e)}")

def get_indicator_history_optimized(
    kpi_conn: Connection,
    indicator_id: str, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """
    OPTIMIZACIÓN: Obtener histórico con una sola consulta más eficiente
    """
    
    try:
        # Consulta optimizada que calcula todos los indicadores históricos de una vez
        query = """
        SELECT 
            anio_mes,
            total_facturado,
            total_cobrado,
            CASE 
                WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                ELSE 0
            END as ratio_cobranza,
            TO_DATE(anio_mes || '-01', 'YYYY-MM-DD') as date_recorded
        FROM produccion.vw_facturacion_vs_cobranza
        WHERE 1=1
        """
        
        params = {}
        
        if date_from:
            query += " AND anio_mes >= :date_from"
            params['date_from'] = date_from[:7]
            
        if date_to:
            query += " AND anio_mes <= :date_to"
            params['date_to'] = date_to[:7]
        
        query += " ORDER BY anio_mes DESC LIMIT 12"
        
        result = kpi_conn.execute(text(query), params)
        rows = result.fetchall()
        
        history = []
        for row in rows:
            date_recorded = convert_date_to_datetime(row.date_recorded)
            
            # Determinar el valor según el indicador solicitado
            if indicator_id == "total_facturado":
                value = float(row.total_facturado)
            elif indicator_id == "total_cobrado":
                value = float(row.total_cobrado)
            elif indicator_id == "ratio_cobranza":
                value = float(row.ratio_cobranza)
            else:
                continue
            
            history_item = IndicatorHistory(
                date=date_recorded,
                value=value,
                metadata={"period": row.anio_mes}
            )
            history.append(history_item)
        
        return history
        
    except Exception as e:
        print(f"Error obteniendo histórico optimizado: {e}")
        raise Exception(f"Error obteniendo histórico: {str(e)}")

def get_indicator_by_id(indicator_id: str, request: Optional[BusinessIndicatorsRequest] = None) -> BusinessIndicator:
    """Obtener un indicador específico por ID - OPTIMIZADO"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            # Obtener todos los indicadores de una vez y filtrar el solicitado
            indicators = get_all_indicators_optimized(kpi_conn)
            
            for indicator in indicators:
                if indicator.id == indicator_id:
                    return indicator
            
            raise ValueError(f"Indicador con ID {indicator_id} no encontrado")
                
        except Exception as e:
            print(f"Error obteniendo indicador {indicator_id}: {e}")
            raise Exception(f"Error obteniendo indicador: {str(e)}")

def get_indicator_history(
    indicator_id: str, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """Obtener el histórico de un indicador específico - OPTIMIZADO"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            return get_indicator_history_optimized(kpi_conn, indicator_id, date_from, date_to)
        except Exception as e:
            print(f"Error obteniendo histórico: {e}")
            raise Exception(f"Error obteniendo histórico: {str(e)}")

def get_indicators_health() -> IndicatorsHealth:
    """Obtener el estado de salud de los indicadores"""
    
    try:
        # Obtener indicadores para evaluar salud
        response = get_business_indicators()
        indicators = response.indicators
        
        healthy_count = sum(1 for i in indicators if i.status == IndicatorStatus.HEALTHY)
        warning_count = sum(1 for i in indicators if i.status == IndicatorStatus.WARNING)
        critical_count = sum(1 for i in indicators if i.status == IndicatorStatus.CRITICAL)
        
        # Determinar estado general
        if critical_count > 0:
            overall_status = "critical"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        issues = []
        if critical_count > 0:
            issues.append(f"{critical_count} indicadores en estado crítico")
        if warning_count > 0:
            issues.append(f"{warning_count} indicadores con advertencias")
        
        return IndicatorsHealth(
            status=overall_status,
            last_update=datetime.now(),
            issues=issues,
            total_indicators=len(indicators),
            healthy_indicators=healthy_count,
            warning_indicators=warning_count,
            critical_indicators=critical_count
        )
        
    except Exception as e:
        print(f"Error obteniendo estado de salud: {e}")
        raise Exception(f"Error obteniendo estado de salud: {str(e)}")