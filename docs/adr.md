# ADR-001: Migración de tableros ejecutivos de Excel a Lakehouse (Aiven)

**Fecha:** 2026-07-13
**Estado:** Aceptado
**Participantes:** Kevin P y Martin D, Departamento de Tecnología
## Contexto

Los tableros ejecutivos de StoneFixer (Contribución Marginal, indicadores de
facturación/cobranza, OT Modal Detail) se alimentaban de dos formas, ninguna
sostenible a mediano plazo:

1. **Excel manual**, procesado client-side con SheetJS directamente en
   `ContribucionMarginalDashboard.tsx` (sin backend de por medio).
2. Un módulo **`business_indicators`** (backend + frontend) conectado a una
   base Aiven de KPIs (`kpi_database.py`) que apuntaba a un esquema que dejó
   de usarse. Este módulo quedó como código muerto: la ruta nunca se registró
   en `App.tsx` del frontend, pero los endpoints seguían activos en el
   backend (`/api/business-indicators/*`), representando superficie de
   ataque innecesaria.

## Decisión

1. **Eliminar** el módulo `business_indicators` completo (backend y
   frontend) — no se migra, se borra, porque apunta a un esquema obsoleto.
2. **Arquitectura de datos final: dos bases PostgreSQL en Aiven, separadas
   por responsabilidad:**
   - `database.py` → DB principal StoneFixer (usuarios, roles, inventario
     tecnológico, turnos, horas extra). Lectura/escritura.
   - `lakehouse_database.py` (nuevo) → instancia Aiven separada, mantenida
     por Martin con datos curados desde el ERP. Solo lectura desde
     StoneFixer. Fuente única para dashboards y KPIs de negocio.
3. **Reemplazo del Excel:** `ContribucionMarginalDashboard.tsx` y los
   próximos tableros consumen datos del backend (que a su vez lee del
   lakehouse), no de un archivo subido a mano.
4. **Freshness diferenciada por indicador**, no una política global de
   cache:
   - Facturado / Cobrado del mes: cache corto (2-5 min), necesita estar
     lo más al día posible.
   - Contribución Marginal: se calcula a mes vencido, cache de horas
     (actualización semanal/mensual es aceptable).
   - Resto de indicadores: a definir caso por caso según la fuente real
     en el lakehouse.
5. **Acceso a la base del lakehouse vía usuario de solo lectura dedicado**
   (`stonefixer_readonly`), nunca el usuario admin de la instancia, con
   `ALTER DEFAULT PRIVILEGES` para que las tablas que Martin agregue a
   futuro queden accesibles sin intervención manual.

## Consecuencias

- Se elimina superficie de ataque y deuda técnica del módulo KPI viejo.
- El directorio/management pasa a depender de datos versionados y
  trazables en vez de un Excel editado a mano — mejora la auditabilidad.
- Introduce una dependencia operativa: si el proceso de Martin que puebla
  el lakehouse falla o se atrasa, los dashboards muestran datos viejos.
  Mitigación pendiente: exponer en el frontend la fecha/hora del último
  dato disponible por indicador (no solo "actualizado hace X min" del
  lado del cache, sino el `data_asof` real del dato en el lakehouse).
- Requiere migración en paralelo (ver plan de rollout) antes de apagar
  el Excel definitivamente, para validar que los números coincidan.

## Pendientes

- [ ] Definir `data_asof` / timestamp de última actualización por tabla
      del lakehouse con Martin.
- [ ] Validar en paralelo mínimo 2-4 semanas antes de dar de baja el
      flujo Excel.