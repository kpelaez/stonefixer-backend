from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.kpi_database import get_kpi_engine
from app.models.business_indicators import (
    BusinessIndicator, 
    IndicatorHistory, 
    BusinessIndicatorsRequest,
    BusinessIndicatorsResponse,
    IndicatorsHealth,
    IndicatorType,
    TrendDirection,
    IndicatorStatus
)

# Funcion auxiliar para convertir las fechas de Postgresql a datetime
def convert_date_to_datetime(date_obj) -> datetime:
    """Convertir date object a datetime para compatibilidad con Pydantic"""
    if isinstance(date_obj, date) and not isinstance(date_obj, datetime):
        return datetime.combine(date_obj, datetime.min.time())
    elif isinstance(date_obj, datetime):
        return date_obj
    else:
        # Manejo de strings y otros tipos
        if isinstance(date_obj, str):
            try:
                return datetime.strptime(date_obj, '%Y-%m-%d')
            except:
                return datetime.now()
        return datetime.now()
    


def get_total_facturado_indicator(kpi_conn: Connection) -> BusinessIndicator:
    """Obtener indicador de Total Facturado del mes actual"""
    
    try:
        # Consulta para el mes actual
        current_query = """
        SELECT 
            anio_mes,
            total_facturado
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
        ORDER BY anio_mes DESC
        LIMIT 1
        """
        
        result = kpi_conn.execute(text(current_query))
        current_row = result.fetchone()
        
        if not current_row:
            raise ValueError("No hay datos de facturación para el mes actual")
        
        # Consulta para calcular tendencia
        trend_query = """
        SELECT 
            anio_mes,
            total_facturado,
            LAG(total_facturado) OVER (ORDER BY anio_mes) as prev_facturado
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes >= TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYY-MM')
        ORDER BY anio_mes DESC
        LIMIT 2
        """
        
        trend_result = kpi_conn.execute(text(trend_query))
        trend_rows = trend_result.fetchall()
        
        # Calcular tendencia
        trend_direction = TrendDirection.STABLE
        trend_percentage = None
        
        if len(trend_rows) >= 2 and trend_rows[0].prev_facturado:
            current_value = float(trend_rows[0].total_facturado)
            prev_value = float(trend_rows[0].prev_facturado)
            
            if prev_value > 0:
                trend_percentage = ((current_value - prev_value) / prev_value) * 100
                trend_direction = TrendDirection.UP if trend_percentage > 0 else TrendDirection.DOWN
        
        return BusinessIndicator(
            id="total_facturado",
            name="Total Facturado",
            description="Total facturado del mes actual",
            value=float(current_row.total_facturado),
            unit="$",
            type=IndicatorType.FINANCIAL,
            trend_direction=trend_direction,
            trend_percentage=trend_percentage,
            status=IndicatorStatus.HEALTHY,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        print(f"Error obteniendo indicador de facturación: {e}")
        raise Exception(f"Error obteniendo total facturado: {str(e)}")


def get_total_cobrado_indicator(kpi_conn: Connection) -> BusinessIndicator:
    """Obtener indicador de Total Cobrado del mes actual"""
    
    try:
        # Consulta para el mes actual
        current_query = """
        SELECT 
            anio_mes,
            total_cobrado
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
        ORDER BY anio_mes DESC
        LIMIT 1
        """
        
        result = kpi_conn.execute(text(current_query))
        current_row = result.fetchone()
        
        if not current_row:
            raise ValueError("No hay datos de cobranza para el mes actual")
        
        # Consulta para calcular tendencia
        trend_query = """
        SELECT 
            anio_mes,
            total_cobrado,
            LAG(total_cobrado) OVER (ORDER BY anio_mes) as prev_cobrado
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes >= TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYY-MM')
        ORDER BY anio_mes DESC
        LIMIT 2
        """
        
        trend_result = kpi_conn.execute(text(trend_query))
        trend_rows = trend_result.fetchall()
        
        # Calcular tendencia
        trend_direction = TrendDirection.STABLE
        trend_percentage = None
        
        if len(trend_rows) >= 2 and trend_rows[0].prev_cobrado:
            current_value = float(trend_rows[0].total_cobrado)
            prev_value = float(trend_rows[0].prev_cobrado)
            
            if prev_value > 0:
                trend_percentage = ((current_value - prev_value) / prev_value) * 100
                trend_direction = TrendDirection.UP if trend_percentage > 0 else TrendDirection.DOWN
        
        return BusinessIndicator(
            id="total_cobrado",
            name="Total Cobrado",
            description="Total cobrado del mes actual",
            value=float(current_row.total_cobrado),
            unit="$",
            type=IndicatorType.FINANCIAL,
            trend_direction=trend_direction,
            trend_percentage=trend_percentage,
            status=IndicatorStatus.HEALTHY,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        print(f"Error obteniendo indicador de cobranza: {e}")
        raise Exception(f"Error obteniendo total cobrado: {str(e)}")


def get_ratio_cobranza_indicator(kpi_conn: Connection) -> BusinessIndicator:
    """Obtener indicador de Ratio de Cobranza del mes actual"""
    
    try:
        # Consulta para calcular el ratio
        query = """
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
        ORDER BY anio_mes DESC
        LIMIT 1
        """
        
        result = kpi_conn.execute(text(query))
        row = result.fetchone()
        
        if not row:
            raise ValueError("No hay datos para calcular el ratio de cobranza")
        
        ratio = float(row.ratio_cobranza)
        
        # Determinar status basado en el ratio
        if ratio >= 90:
            status = IndicatorStatus.HEALTHY
        elif ratio >= 70:
            status = IndicatorStatus.WARNING  
        else:
            status = IndicatorStatus.CRITICAL
        
        # Calcular tendencia del ratio (comparar con mes anterior)
        trend_query = """
        SELECT 
            anio_mes,
            CASE 
                WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                ELSE 0
            END as ratio_cobranza,
            LAG(CASE 
                WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                ELSE 0
            END) OVER (ORDER BY anio_mes) as prev_ratio
        FROM produccion.vw_facturacion_vs_cobranza 
        WHERE anio_mes >= TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYY-MM')
        ORDER BY anio_mes DESC
        LIMIT 2
        """
        
        trend_result = kpi_conn.execute(text(trend_query))
        trend_rows = trend_result.fetchall()
        
        trend_direction = TrendDirection.STABLE
        trend_percentage = None
        
        if len(trend_rows) >= 2 and trend_rows[0].prev_ratio:
            current_ratio = float(trend_rows[0].ratio_cobranza)
            prev_ratio = float(trend_rows[0].prev_ratio)
            
            if prev_ratio > 0:
                trend_percentage = current_ratio - prev_ratio  # Diferencia en puntos porcentuales
                trend_direction = TrendDirection.UP if trend_percentage > 0 else TrendDirection.DOWN
        
        return BusinessIndicator(
            id="ratio_cobranza",
            name="Ratio Cobranza",
            description="Porcentaje de cobranza vs facturación del mes",
            value=round(ratio, 2),
            unit="%",
            type=IndicatorType.OPERATIONAL,
            trend_direction=trend_direction,
            trend_percentage=trend_percentage,
            status=status,
            target_value=85.0,  # Meta del 85%
            last_updated=datetime.now()
        )
        
    except Exception as e:
        print(f"Error obteniendo ratio de cobranza: {e}")
        raise Exception(f"Error obteniendo ratio de cobranza: {str(e)}")


# =============================================================================
# FUNCIONES PARA HISTÓRICOS INDIVIDUALES
# =============================================================================

def get_total_facturado_history(
    kpi_conn: Connection, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """Obtener histórico de Total Facturado"""
    
    try:
        query = """
        SELECT 
            anio_mes,
            total_facturado as value,
            TO_DATE(anio_mes || '-01', 'YYYY-MM-DD') as date_recorded
        FROM produccion.vw_facturacion_vs_cobranza
        WHERE 1=1
        """
        
        params = {}
        
        if date_from:
            query += " AND anio_mes >= :date_from"
            params['date_from'] = date_from[:7]  # Solo YYYY-MM
            
        if date_to:
            query += " AND anio_mes <= :date_to"
            params['date_to'] = date_to[:7]  # Solo YYYY-MM
        
        query += " ORDER BY anio_mes DESC LIMIT 12"
        
        result = kpi_conn.execute(text(query), params)
        rows = result.fetchall()
        
        history = []
        for row in rows:
            date_recorded = convert_date_to_datetime(row.date_recorded)
            history_item = IndicatorHistory(
                date=date_recorded,
                value=float(row.value),
                metadata={"period": row.anio_mes}
            )
            history.append(history_item)
        
        return history
        
    except Exception as e:
        print(f"Error obteniendo histórico de facturación: {e}")
        raise Exception(f"Error obteniendo histórico de facturación: {str(e)}")


def get_total_cobrado_history(
    kpi_conn: Connection, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """Obtener histórico de Total Cobrado"""
    
    try:
        query = """
        SELECT 
            anio_mes,
            total_cobrado as value,
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
            history_item = IndicatorHistory(
                date=date_recorded,
                value=float(row.value),
                metadata={"period": row.anio_mes}
            )
            history.append(history_item)
        
        return history
        
    except Exception as e:
        print(f"Error obteniendo histórico de cobranza: {e}")
        raise Exception(f"Error obteniendo histórico de cobranza: {str(e)}")


def get_ratio_cobranza_history(
    kpi_conn: Connection, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """Obtener histórico de Ratio de Cobranza"""
    
    try:
        query = """
        SELECT 
            anio_mes,
            CASE 
                WHEN total_facturado > 0 THEN (total_cobrado / total_facturado * 100)
                ELSE 0
            END as value,
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
            history_item = IndicatorHistory(
                date=date_recorded,
                value=float(row.value),
                metadata={"period": row.anio_mes}
            )
            history.append(history_item)
        
        return history
        
    except Exception as e:
        print(f"Error obteniendo histórico de ratio: {e}")
        raise Exception(f"Error obteniendo histórico de ratio: {str(e)}")


# =============================================================================
# FUNCIONES PRINCIPALES DE SERVICIO
# =============================================================================

def get_business_indicators(request: Optional[BusinessIndicatorsRequest] = None) -> BusinessIndicatorsResponse:
    """Obtener todos los indicadores de negocio"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            indicators = []
            
            # Obtener cada indicador por separado
            try:
                facturado = get_total_facturado_indicator(kpi_conn)
                indicators.append(facturado)
            except Exception as e:
                print(f"Error obteniendo indicador de facturación: {e}")
            
            try:
                cobrado = get_total_cobrado_indicator(kpi_conn)
                indicators.append(cobrado)
            except Exception as e:
                print(f"Error obteniendo indicador de cobranza: {e}")
            
            try:
                ratio = get_ratio_cobranza_indicator(kpi_conn)
                indicators.append(ratio)
            except Exception as e:
                print(f"Error obteniendo ratio de cobranza: {e}")
            
            return BusinessIndicatorsResponse(
                indicators=indicators,
                total_count=len(indicators),
                last_updated=datetime.now()
            )
            
        except Exception as e:
            print(f"Error general obteniendo indicadores: {e}")
            raise Exception(f"Error obteniendo indicadores: {str(e)}")


def get_indicator_by_id(indicator_id: str, request: Optional[BusinessIndicatorsRequest] = None) -> BusinessIndicator:
    """Obtener un indicador específico por ID"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            if indicator_id == "total_facturado":
                return get_total_facturado_indicator(kpi_conn)
            elif indicator_id == "total_cobrado":
                return get_total_cobrado_indicator(kpi_conn)
            elif indicator_id == "ratio_cobranza":
                return get_ratio_cobranza_indicator(kpi_conn)
            else:
                raise ValueError(f"Indicador con ID {indicator_id} no encontrado")
                
        except Exception as e:
            print(f"Error obteniendo indicador {indicator_id}: {e}")
            raise Exception(f"Error obteniendo indicador: {str(e)}")


def get_indicator_history(
    indicator_id: str, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[IndicatorHistory]:
    """Obtener el histórico de un indicador específico"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            if indicator_id == "total_facturado":
                return get_total_facturado_history(kpi_conn, date_from, date_to)
            elif indicator_id == "total_cobrado":
                return get_total_cobrado_history(kpi_conn, date_from, date_to)
            elif indicator_id == "ratio_cobranza":
                return get_ratio_cobranza_history(kpi_conn, date_from, date_to)
            else:
                raise ValueError(f"Histórico para indicador {indicator_id} no disponible")
                
        except Exception as e:
            print(f"Error obteniendo histórico de {indicator_id}: {e}")
            raise Exception(f"Error obteniendo histórico: {str(e)}")


def get_indicators_health() -> IndicatorsHealth:
    """Obtener el estado de salud de los indicadores"""
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as kpi_conn:
        try:
            # Obtener todos los indicadores
            indicators = []
            
            try:
                indicators.append(get_total_facturado_indicator(kpi_conn))
            except:
                pass
                
            try:
                indicators.append(get_total_cobrado_indicator(kpi_conn))
            except:
                pass
                
            try:
                indicators.append(get_ratio_cobranza_indicator(kpi_conn))
            except:
                pass
            
            # Contar por status
            total_indicators = len(indicators)
            healthy_count = len([i for i in indicators if i.status == IndicatorStatus.HEALTHY])
            warning_count = len([i for i in indicators if i.status == IndicatorStatus.WARNING])
            critical_count = len([i for i in indicators if i.status == IndicatorStatus.CRITICAL])
            
            # Determinar estado general
            if critical_count > 0:
                overall_status = 'critical'
            elif warning_count > 0:
                overall_status = 'degraded'
            else:
                overall_status = 'healthy'
            
            # Identificar issues
            issues = []
            if critical_count > 0:
                issues.append(f"{critical_count} indicadores en estado crítico")
            if warning_count > 0:
                issues.append(f"{warning_count} indicadores con advertencias")
            
            return IndicatorsHealth(
                status=overall_status,
                last_update=datetime.now(),
                issues=issues,
                total_indicators=total_indicators,
                healthy_indicators=healthy_count,
                warning_indicators=warning_count,
                critical_indicators=critical_count
            )
            
        except Exception as e:
            print(f"Error obteniendo health de indicadores: {e}")
            raise Exception(f"Error obteniendo estado de salud: {str(e)}")
