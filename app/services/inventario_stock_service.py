# app/services/inventario_stock_service.py
"""
InventarioStockService — orquesta el flujo completo del módulo.

Responsabilidades:
  1. Crear y actualizar cabeceras de relevamiento.
  2. Ejecutar el scraping (Omnimedica) + consulta Finnegans en background.
  3. Persistir series extraídas.
  4. Procesar la carga masiva de resultados físicos.
  5. Generar el análisis de diferencias.
  6. Gestionar ajustes (create / autorizar).

Convenciones del proyecto:
  - Excepciones centralizadas via app/core/exceptions.py.
  - Logger por módulo.
  - 1 archivo de servicio por módulo (este).
  - El service NO importa FastAPI (sin HTTPException directa aquí;
    los routers transforman las excepciones del dominio).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from app.core.exceptions import ResourceNotFoundError, InvalidOperationError
from app.models.inventario_stock import (
    EstadoAjuste,
    EstadoRelevamiento,
    InventarioRelevamiento,
    InventarioRelevamientoAjuste,
    InventarioRelevamientoDiferencia,
    InventarioRelevamientoSerie,
    ResultadoFisico,
    TipoDiferencia,
)
from app.schemas.inventario_stock import (
    AjusteCreate,
    CargaResultadosFisicosRequest,
    CargaResultadosResponse,
    RelevamientoCreate,
)
from app.services.finnegans_client import FinnegansClient
from app.services.omnimedica_scraper import OmnimedicaScraper

logger = logging.getLogger(__name__)

# Umbral de días para alertar vencimientos próximos
_DIAS_UMBRAL_VENCIMIENTO = 90


class InventarioStockService:
    """
    Lógica de negocio del módulo Inventario de Stock.
    Instanciar sin argumentos; pasar `db` en cada método.
    """

    # ------------------------------------------------------------------
    # 1. Relevamiento — CRUD cabecera
    # ------------------------------------------------------------------

    @staticmethod
    def crear_relevamiento(
        db: Session,
        payload: RelevamientoCreate,
        user_id: int,
    ) -> InventarioRelevamiento:
        """Crea la cabecera del ciclo en estado PENDIENTE."""
        # Verificar que no exista otro relevamiento activo para el mismo
        # proveedor + mes (evitar duplicados accidentales)
        existente = db.exec(
            select(InventarioRelevamiento).where(
                InventarioRelevamiento.proveedor == payload.proveedor,
                InventarioRelevamiento.mes_ciclo == payload.mes_ciclo,
                InventarioRelevamiento.estado.notin_(  # type: ignore[attr-defined]
                    [EstadoRelevamiento.CERRADO]
                ),
            )
        ).first()

        if existente:
            raise ValidationError(
                f"Ya existe un relevamiento activo para '{payload.proveedor}' "
                f"en {payload.mes_ciclo} (id={existente.id})"
            )

        relevamiento = InventarioRelevamiento(
            proveedor=payload.proveedor,
            mes_ciclo=payload.mes_ciclo,
            creado_por_user_id=user_id,
        )
        db.add(relevamiento)
        db.commit()
        db.refresh(relevamiento)
        logger.info(
            f"[InventarioStock] Relevamiento #{relevamiento.id} creado "
            f"por user_id={user_id} [{payload.proveedor} / {payload.mes_ciclo}]"
        )
        return relevamiento

    @staticmethod
    def get_relevamiento(db: Session, relevamiento_id: int) -> InventarioRelevamiento:
        rel = db.get(InventarioRelevamiento, relevamiento_id)
        if not rel:
            raise ResourceNotFoundError(f"Relevamiento #{relevamiento_id} no encontrado")
        return rel

    @staticmethod
    def listar_relevamientos(
        db: Session,
        proveedor: Optional[str] = None,
        mes_ciclo: Optional[str] = None,
    ) -> list[InventarioRelevamiento]:
        query = select(InventarioRelevamiento).order_by(
            InventarioRelevamiento.creado_en.desc()  # type: ignore[attr-defined]
        )
        if proveedor:
            query = query.where(InventarioRelevamiento.proveedor == proveedor)
        if mes_ciclo:
            query = query.where(InventarioRelevamiento.mes_ciclo == mes_ciclo)
        return list(db.exec(query).all())

    # ------------------------------------------------------------------
    # 2. Scraping (se llama desde el background task del router)
    # ------------------------------------------------------------------

    @staticmethod
    async def ejecutar_scraping(db: Session, relevamiento_id: int) -> None:
        """
        Orquesta scraper Omnimedica + consulta Finnegans y persiste resultados.
        Se ejecuta como FastAPI BackgroundTask.

        El estado del relevamiento se actualiza en cada etapa para que
        el frontend pueda hacer polling y mostrar progreso.
        """
        rel = db.get(InventarioRelevamiento, relevamiento_id)
        if not rel:
            logger.error(
                f"[InventarioStock] Background task: relevamiento #{relevamiento_id} no existe"
            )
            return

        # Marcar inicio
        rel.estado = EstadoRelevamiento.EXTRAYENDO
        rel.scraping_iniciado_en = datetime.now(timezone.utc)
        db.commit()

        try:
            # --- OMNIMEDICA ---
            async with OmnimedicaScraper() as scraper:
                resultado = await scraper.extraer_stock(rel.proveedor)

            if not resultado.exitoso:
                raise RuntimeError(
                    f"Scraping Omnimedica falló: {resultado.error}"
                )

            series_omni = resultado.series
            logger.info(
                f"[InventarioStock] #{relevamiento_id}: "
                f"{len(series_omni)} series extraídas de Omnimedica"
            )

            # --- FINNEGANS (en paralelo con semáforo) ---
            codigos_unicos = list({s.codigo for s in series_omni})
            async with FinnegansClient() as finn:
                finn_map = await finn.consultar_codigos(codigos_unicos)

            logger.info(
                f"[InventarioStock] #{relevamiento_id}: "
                f"{len(finn_map)} códigos consultados en Finnegans"
            )

            # --- PERSISTENCIA ---
            # Eliminar series previas del relevamiento (por si se re-ejecuta)
            series_previas = db.exec(
                select(InventarioRelevamientoSerie).where(
                    InventarioRelevamientoSerie.relevamiento_id == relevamiento_id
                )
            ).all()
            for s in series_previas:
                db.delete(s)
            db.flush()

            for s in series_omni:
                cant_finn = finn_map.get(s.codigo)
                db.add(
                    InventarioRelevamientoSerie(
                        relevamiento_id=relevamiento_id,
                        codigo=s.codigo,
                        descripcion=s.descripcion,
                        empresa=s.empresa,
                        serie=s.serie,
                        lote=s.lote,
                        vencimiento=s.vencimiento,
                        deposito=s.deposito,
                        estado_sistema=s.estado_sistema,
                        en_transito=s.en_transito,
                        cant_finnegans=(
                            Decimal(str(cant_finn)) if cant_finn is not None else None
                        ),
                    )
                )

            rel.total_series_omni = len(series_omni)
            rel.total_codigos_finn = len(
                [v for v in finn_map.values() if v is not None]
            )
            rel.estado = EstadoRelevamiento.LISTO
            rel.scraping_finalizado_en = datetime.now(timezone.utc)
            rel.actualizado_en = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                f"[InventarioStock] #{relevamiento_id}: scraping completado OK"
            )

        except Exception as exc:
            logger.exception(
                f"[InventarioStock] #{relevamiento_id}: error en background task"
            )
            rel.estado = EstadoRelevamiento.PENDIENTE
            rel.scraping_error = str(exc)[:500]
            rel.actualizado_en = datetime.now(timezone.utc)
            db.commit()

    # ------------------------------------------------------------------
    # 3. Listar series (con paginación y filtros)
    # ------------------------------------------------------------------

    @staticmethod
    def listar_series(
        db: Session,
        relevamiento_id: int,
        page: int = 1,
        page_size: int = 50,
        solo_pendientes: bool = False,
        solo_diferencias: bool = False,
    ) -> tuple[list[InventarioRelevamientoSerie], int]:
        """
        Returns: (items, total)
        """
        query = select(InventarioRelevamientoSerie).where(
            InventarioRelevamientoSerie.relevamiento_id == relevamiento_id
        )

        if solo_pendientes:
            query = query.where(
                InventarioRelevamientoSerie.resultado_fisico.is_(None)  # type: ignore[attr-defined]
            )

        if solo_diferencias:
            # Solo series que tienen al menos una diferencia asociada
            from sqlmodel import exists

            sub = select(InventarioRelevamientoDiferencia.serie_id).where(
                InventarioRelevamientoDiferencia.relevamiento_id == relevamiento_id
            )
            query = query.where(InventarioRelevamientoSerie.id.in_(sub))  # type: ignore[attr-defined]

        # Total antes de paginar
        total_query = query
        total = len(db.exec(total_query).all())

        # Paginar
        offset = (page - 1) * page_size
        items = list(
            db.exec(
                query.order_by(
                    InventarioRelevamientoSerie.codigo,
                    InventarioRelevamientoSerie.serie,
                )
                .offset(offset)
                .limit(page_size)
            ).all()
        )

        return items, total

    # ------------------------------------------------------------------
    # 4. Carga masiva de resultados físicos
    # ------------------------------------------------------------------

    @staticmethod
    def cargar_resultados_fisicos(
        db: Session,
        relevamiento_id: int,
        payload: CargaResultadosFisicosRequest,
        user_id: int,
    ) -> CargaResultadosResponse:
        """Actualiza el resultado físico de cada serie en la lista."""
        # Verificar que el relevamiento exista y esté en estado correcto
        rel = db.get(InventarioRelevamiento, relevamiento_id)
        if not rel:
            raise ResourceNotFoundError(f"Relevamiento #{relevamiento_id} no encontrado")

        if rel.estado not in {EstadoRelevamiento.LISTO, EstadoRelevamiento.EN_CONTEO}:
            raise InvalidOperationError(
                f"El relevamiento está en estado '{rel.estado}' y no acepta resultados físicos"
            )

        ids_payload = {item.serie_id for item in payload.items}
        series = db.exec(
            select(InventarioRelevamientoSerie).where(
                InventarioRelevamientoSerie.id.in_(ids_payload),  # type: ignore[attr-defined]
                InventarioRelevamientoSerie.relevamiento_id == relevamiento_id,
            )
        ).all()

        ids_encontrados = {s.id for s in series}
        ids_no_encontrados = list(ids_payload - ids_encontrados)

        ahora = datetime.now(timezone.utc)
        for item in payload.items:
            serie = next((s for s in series if s.id == item.serie_id), None)
            if not serie:
                continue
            serie.resultado_fisico = item.resultado
            serie.observaciones = item.observaciones
            serie.cargado_en = ahora
            serie.cargado_por_user_id = user_id
            db.add(serie)

        # Actualizar estado del relevamiento
        if rel.estado == EstadoRelevamiento.LISTO:
            rel.estado = EstadoRelevamiento.EN_CONTEO
            rel.actualizado_en = ahora

        db.commit()

        logger.info(
            f"[InventarioStock] #{relevamiento_id}: "
            f"{len(ids_encontrados)} series actualizadas por user_id={user_id}"
        )
        return CargaResultadosResponse(
            actualizadas=len(ids_encontrados),
            no_encontradas=ids_no_encontrados,
        )

    # ------------------------------------------------------------------
    # 5. Motor de análisis de diferencias
    # ------------------------------------------------------------------

    @staticmethod
    def generar_analisis(
        db: Session, relevamiento_id: int
    ) -> list[InventarioRelevamientoDiferencia]:
        """
        Analiza las series del relevamiento y genera las diferencias.
        Elimina las diferencias previas antes de regenerar.
        """
        rel = db.get(InventarioRelevamiento, relevamiento_id)
        if not rel:
            raise ResourceNotFoundError(f"Relevamiento #{relevamiento_id} no encontrado")

        if rel.estado not in {
            EstadoRelevamiento.EN_CONTEO,
            EstadoRelevamiento.ANALIZADO,
        }:
            raise InvalidOperationError(
                f"El relevamiento debe estar en estado 'en_conteo' para analizar "
                f"(actual: '{rel.estado}')"
            )

        # Limpiar análisis previo
        diffs_previas = db.exec(
            select(InventarioRelevamientoDiferencia).where(
                InventarioRelevamientoDiferencia.relevamiento_id == relevamiento_id
            )
        ).all()
        for d in diffs_previas:
            db.delete(d)
        db.flush()

        series = db.exec(
            select(InventarioRelevamientoSerie).where(
                InventarioRelevamientoSerie.relevamiento_id == relevamiento_id
            )
        ).all()

        diferencias: list[InventarioRelevamientoDiferencia] = []

        # Agrupar por código para comparar cantidades Omni vs Finnegans
        from collections import defaultdict

        por_codigo: dict[str, list[InventarioRelevamientoSerie]] = defaultdict(list)
        for s in series:
            por_codigo[s.codigo].append(s)

        for codigo, grupo in por_codigo.items():
            cant_omni = Decimal(len(grupo))
            cant_finn = grupo[0].cant_finnegans  # misma para todo el código

            # Diferencia de cantidades entre sistemas
            if cant_finn is not None and cant_omni != cant_finn:
                dif = InventarioRelevamientoDiferencia(
                    relevamiento_id=relevamiento_id,
                    tipo=TipoDiferencia.CANT_OMNI_VS_FINN,
                    descripcion=(
                        f"Código {codigo}: Omnimedica={cant_omni}, "
                        f"Finnegans={cant_finn}"
                    ),
                    cant_omnimedica=cant_omni,
                    cant_finnegans=cant_finn,
                    diferencia=cant_omni - cant_finn,
                )
                db.add(dif)
                diferencias.append(dif)

        for serie in series:
            # Serie no encontrada físicamente
            if serie.resultado_fisico == ResultadoFisico.NO_ENCONTRADA:
                dif = InventarioRelevamientoDiferencia(
                    relevamiento_id=relevamiento_id,
                    serie_id=serie.id,
                    tipo=TipoDiferencia.SERIE_NO_ENCONTRADA,
                    descripcion=(
                        f"Serie '{serie.serie}' ({serie.codigo}) "
                        "no encontrada en conteo físico"
                    ),
                )
                db.add(dif)
                diferencias.append(dif)

            # Serie presente sin registro en sistemas (resultado presente pero no está en Omni)
            # Este caso se detecta en el frontend cuando el usuario marca
            # una serie que el sistema no tenía registrada.

            # Lote por vencer
            if serie.vencimiento:
                dias = InventarioStockService._dias_para_vencer(serie.vencimiento)
                if dias is not None and 0 <= dias < _DIAS_UMBRAL_VENCIMIENTO:
                    dif = InventarioRelevamientoDiferencia(
                        relevamiento_id=relevamiento_id,
                        serie_id=serie.id,
                        tipo=TipoDiferencia.LOTE_POR_VENCER,
                        descripcion=(
                            f"Lote '{serie.lote}' de '{serie.codigo}' "
                            f"vence en {dias} días ({serie.vencimiento})"
                        ),
                    )
                    db.add(dif)
                    diferencias.append(dif)

        rel.estado = EstadoRelevamiento.ANALIZADO
        rel.actualizado_en = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"[InventarioStock] #{relevamiento_id}: "
            f"{len(diferencias)} diferencias generadas"
        )
        return diferencias

    # ------------------------------------------------------------------
    # 6. Ajustes
    # ------------------------------------------------------------------

    @staticmethod
    def crear_ajuste(
        db: Session,
        relevamiento_id: int,
        payload: AjusteCreate,
        user_id: int,
    ) -> InventarioRelevamientoAjuste:
        # Verificar que la diferencia exista y pertenezca al relevamiento
        diff = db.get(InventarioRelevamientoDiferencia, payload.diferencia_id)
        if not diff or diff.relevamiento_id != relevamiento_id:
            raise ResourceNotFoundError(
                f"Diferencia #{payload.diferencia_id} no encontrada en el relevamiento"
            )

        ajuste = InventarioRelevamientoAjuste(
            relevamiento_id=relevamiento_id,
            diferencia_id=payload.diferencia_id,
            codigo=payload.codigo,
            descripcion_ajuste=payload.descripcion_ajuste,
            cant_ajuste=payload.cant_ajuste,
        )
        db.add(ajuste)
        db.commit()
        db.refresh(ajuste)
        logger.info(
            f"[InventarioStock] Ajuste #{ajuste.id} creado por user_id={user_id}"
        )
        return ajuste

    @staticmethod
    def autorizar_ajuste(
        db: Session,
        ajuste_id: int,
        nota: Optional[str],
        user_id: int,
    ) -> InventarioRelevamientoAjuste:
        ajuste = db.get(InventarioRelevamientoAjuste, ajuste_id)
        if not ajuste:
            raise ResourceNotFoundError(f"Ajuste #{ajuste_id} no encontrado")

        if ajuste.estado != EstadoAjuste.PENDIENTE:
            raise InvalidOperationError(
                f"El ajuste ya fue procesado (estado: '{ajuste.estado}')"
            )

        ajuste.estado = EstadoAjuste.AUTORIZADO
        ajuste.autorizado_por_user_id = user_id
        ajuste.autorizado_en = datetime.now(timezone.utc)
        ajuste.nota = nota
        db.commit()
        db.refresh(ajuste)
        logger.info(
            f"[InventarioStock] Ajuste #{ajuste_id} autorizado por user_id={user_id}"
        )
        return ajuste

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _dias_para_vencer(vencimiento_str: str) -> Optional[int]:
        """
        Convierte una fecha de vencimiento (dd/mm/yyyy o yyyy-mm-dd)
        y retorna los días hasta el vencimiento desde hoy.
        """
        from datetime import date

        formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formatos:
            try:
                fecha = datetime.strptime(vencimiento_str.strip(), fmt).date()
                return (fecha - date.today()).days
            except ValueError:
                continue
        logger.debug(
            f"[InventarioStock] No se pudo parsear fecha de vencimiento: '{vencimiento_str}'"
        )
        return None