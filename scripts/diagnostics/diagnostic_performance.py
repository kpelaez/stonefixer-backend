#!/usr/bin/env python3
"""
Script de diagnóstico COMPLETO para identificar dónde está el cuello de botella
"""

import time
import asyncio
from sqlalchemy import text
from app.db.kpi_database import get_kpi_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnostic_database_performance():
    """Diagnosticar rendimiento de la base de datos paso a paso"""
    
    print("🔍 DIAGNÓSTICO COMPLETO DE RENDIMIENTO")
    print("=" * 60)
    
    kpi_engine = get_kpi_engine()
    
    with kpi_engine.connect() as conn:
        
        # 1. Test básico de conexión
        print("\n1️⃣ TEST DE CONEXIÓN BÁSICA")
        print("-" * 30)
        
        start_time = time.time()
        result = conn.execute(text("SELECT 1"))
        end_time = time.time()
        
        connection_time = (end_time - start_time) * 1000
        print(f"✅ Conexión básica: {connection_time:.2f}ms")
        
        if connection_time > 500:
            print("⚠️ WARNING: Conexión lenta (>500ms)")
        
        # 2. Verificar que la vista existe
        print("\n2️⃣ VERIFICACIÓN DE VISTA")
        print("-" * 30)
        
        try:
            start_time = time.time()
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.views 
                WHERE table_name = 'vw_facturacion_vs_cobranza'
                AND table_schema = 'produccion'
            """))
            end_time = time.time()
            
            query_time = (end_time - start_time) * 1000
            view_count = result.fetchone().count
            
            print(f"✅ Vista existe: {view_count > 0}")
            print(f"⏱️ Tiempo verificación: {query_time:.2f}ms")
            
        except Exception as e:
            print(f"❌ Error verificando vista: {e}")
            return
        
        # 3. Test de count total en la vista
        print("\n3️⃣ TEST DE COUNT TOTAL")
        print("-" * 30)
        
        try:
            start_time = time.time()
            result = conn.execute(text("SELECT COUNT(*) FROM produccion.vw_facturacion_vs_cobranza"))
            end_time = time.time()
            
            count_time = (end_time - start_time) * 1000
            total_rows = result.fetchone()[0]
            
            print(f"📊 Total registros: {total_rows}")
            print(f"⏱️ Tiempo COUNT: {count_time:.2f}ms")
            
            if count_time > 2000:
                print("🔴 PROBLEMA: Count muy lento (>2s) - Vista mal optimizada")
            elif count_time > 1000:
                print("🟡 WARNING: Count lento (>1s)")
            
        except Exception as e:
            print(f"❌ Error en count: {e}")
            return
        
        # 4. Test de consulta simple - mes actual
        print("\n4️⃣ TEST CONSULTA MES ACTUAL")
        print("-" * 30)
        
        try:
            start_time = time.time()
            result = conn.execute(text("""
                SELECT anio_mes, total_facturado, total_cobrado
                FROM produccion.vw_facturacion_vs_cobranza 
                WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
            """))
            end_time = time.time()
            
            simple_time = (end_time - start_time) * 1000
            rows = result.fetchall()
            
            print(f"📊 Registros encontrados: {len(rows)}")
            print(f"⏱️ Tiempo consulta simple: {simple_time:.2f}ms")
            
            if len(rows) > 0:
                row = rows[0]
                print(f"📅 Período: {row.anio_mes}")
                print(f"💰 Facturado: ${row.total_facturado:,.2f}")
                print(f"💰 Cobrado: ${row.total_cobrado:,.2f}")
            else:
                print("⚠️ No hay datos para el mes actual")
            
            if simple_time > 3000:
                print("🔴 PROBLEMA CRÍTICO: Consulta simple muy lenta (>3s)")
            elif simple_time > 1000:
                print("🟡 WARNING: Consulta simple lenta (>1s)")
                
        except Exception as e:
            print(f"❌ Error en consulta simple: {e}")
            return
        
        # 5. Test de consulta con CTE (nuestra optimizada)
        print("\n5️⃣ TEST CONSULTA OPTIMIZADA (CTE)")
        print("-" * 30)
        
        try:
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
            ),
            previous_data AS (
                SELECT 
                    anio_mes,
                    total_facturado,
                    total_cobrado
                FROM produccion.vw_facturacion_vs_cobranza 
                WHERE anio_mes = TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYY-MM')
            )
            SELECT 
                c.total_facturado as current_facturado,
                c.total_cobrado as current_cobrado,
                c.ratio_cobranza as current_ratio,
                p.total_facturado as prev_facturado,
                p.total_cobrado as prev_cobrado,
                c.anio_mes as current_period,
                p.anio_mes as prev_period
            FROM current_data c
            LEFT JOIN previous_data p ON 1=1
            """
            
            start_time = time.time()
            result = conn.execute(text(optimized_query))
            end_time = time.time()
            
            optimized_time = (end_time - start_time) * 1000
            row = result.fetchone()
            
            print(f"⏱️ Tiempo consulta optimizada: {optimized_time:.2f}ms")
            
            if row:
                print(f"📊 Facturado actual: ${row.current_facturado:,.2f}")
                print(f"📊 Cobrado actual: ${row.current_cobrado:,.2f}")
                print(f"📊 Ratio actual: {row.current_ratio:.2f}%")
            
            if optimized_time > 5000:
                print("🔴 PROBLEMA CRÍTICO: Consulta optimizada muy lenta (>5s)")
                print("💡 CAUSA: La vista subyacente es el problema")
            elif optimized_time > 2000:
                print("🟡 WARNING: Consulta optimizada lenta (>2s)")
            else:
                print("✅ Consulta optimizada tiene buen rendimiento")
                
        except Exception as e:
            print(f"❌ Error en consulta optimizada: {e}")
            return
        
        # 6. Test de EXPLAIN PLAN
        print("\n6️⃣ ANÁLISIS DEL PLAN DE EJECUCIÓN")
        print("-" * 30)
        
        try:
            explain_query = """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT anio_mes, total_facturado, total_cobrado
            FROM produccion.vw_facturacion_vs_cobranza 
            WHERE anio_mes = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
            """
            
            start_time = time.time()
            result = conn.execute(text(explain_query))
            end_time = time.time()
            
            explain_time = (end_time - start_time) * 1000
            explain_result = result.fetchone()[0]
            
            print(f"⏱️ Tiempo EXPLAIN: {explain_time:.2f}ms")
            
            # Extraer información clave del plan
            plan = explain_result[0]["Plan"]
            execution_time = explain_result[0].get("Execution Time", 0)
            planning_time = explain_result[0].get("Planning Time", 0)
            
            print(f"📊 Planning Time: {planning_time:.2f}ms")
            print(f"📊 Execution Time: {execution_time:.2f}ms")
            print(f"📊 Node Type: {plan.get('Node Type', 'Unknown')}")
            
            if execution_time > 3000:
                print("🔴 PROBLEMA: Execution time muy alto")
            
        except Exception as e:
            print(f"⚠️ No se pudo obtener EXPLAIN: {e}")
        
        # 7. Test de estructura de la vista
        print("\n7️⃣ ANÁLISIS DE ESTRUCTURA DE VISTA")
        print("-" * 30)
        
        try:
            structure_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'vw_facturacion_vs_cobranza'
            AND table_schema = 'produccion'
            ORDER BY ordinal_position
            """
            
            result = conn.execute(text(structure_query))
            columns = result.fetchall()
            
            print("📋 Columnas de la vista:")
            for col in columns:
                print(f"   - {col.column_name}: {col.data_type}")
            
        except Exception as e:
            print(f"⚠️ No se pudo analizar estructura: {e}")
        
        # 8. RESUMEN Y RECOMENDACIONES
        print("\n8️⃣ RESUMEN Y RECOMENDACIONES")
        print("=" * 60)
        
        if simple_time > 3000:
            print("🔴 DIAGNÓSTICO: PROBLEMA EN LA VISTA DE BASE DE DATOS")
            print("\n💡 RECOMENDACIONES INMEDIATAS:")
            print("   1. La vista 'vw_facturacion_vs_cobranza' es MUY lenta")
            print("   2. Necesita optimización de índices en las tablas base")
            print("   3. Considerar materializar la vista o crear índices")
            print("   4. Revisar la definición de la vista por joins complejos")
            
            print("\n🔧 SOLUCIONES TEMPORALES:")
            print("   1. Implementar caché agresivo en aplicación")
            print("   2. Pre-calcular valores en tabla auxiliar")
            print("   3. Limitar consultas a últimos 12 meses solamente")
            
        elif simple_time > 1000:
            print("🟡 DIAGNÓSTICO: Rendimiento subóptimo")
            print("\n💡 RECOMENDACIONES:")
            print("   1. Optimizar la vista con índices apropiados")
            print("   2. Implementar caché en aplicación")
            
        else:
            print("✅ DIAGNÓSTICO: Base de datos tiene buen rendimiento")
            print("💡 El problema puede estar en:")
            print("   1. Latencia de red")
            print("   2. Pool de conexiones")
            print("   3. Procesamiento en aplicación")

def test_network_latency():
    """Test específico de latencia de red"""
    
    print("\n🌐 TEST DE LATENCIA DE RED")
    print("=" * 30)
    
    kpi_engine = get_kpi_engine()
    
    # Test múltiples conexiones
    times = []
    
    for i in range(5):
        try:
            start_time = time.time()
            with kpi_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000
            times.append(latency)
            print(f"   Conexión {i+1}: {latency:.2f}ms")
            
        except Exception as e:
            print(f"   Conexión {i+1}: ERROR - {e}")
    
    if times:
        avg_latency = sum(times) / len(times)
        min_latency = min(times)
        max_latency = max(times)
        
        print(f"\n📊 Estadísticas de latencia:")
        print(f"   Promedio: {avg_latency:.2f}ms")
        print(f"   Mínimo: {min_latency:.2f}ms")
        print(f"   Máximo: {max_latency:.2f}ms")
        
        if avg_latency > 1000:
            print("🔴 PROBLEMA: Latencia de red muy alta")
        elif avg_latency > 500:
            print("🟡 WARNING: Latencia de red alta")
        else:
            print("✅ Latencia de red aceptable")

if __name__ == "__main__":
    try:
        diagnostic_database_performance()
        test_network_latency()
        
        print("\n" + "=" * 60)
        print("🎯 PRÓXIMOS PASOS:")
        print("1. Ejecutar este script y revisar los resultados")
        print("2. Si la vista es lenta, implementar soluciones de caché")
        print("3. Si la latencia es alta, optimizar pool de conexiones")
        print("4. Monitorear con endpoints de performance")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        print("\n💡 SOLUCIÓN DE EMERGENCIA:")
        print("   - Verificar conexión a Aiven")
        print("   - Revisar variables de entorno")
        print("   - Probar conexión manual")