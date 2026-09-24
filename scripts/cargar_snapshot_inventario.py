"""
scripts/cargar_snapshot_inventario.py

Carga diaria (cron): foto de stock de AYER (hora Argentina) desde Finnegans.

Uso, desde la raíz del backend:
    python -m scripts.cargar_snapshot_inventario            # ayer
    python -m scripts.cargar_snapshot_inventario 2026-08-31 # una fecha puntual

Sale con código 1 si falla: así cron y cualquier monitoreo lo detectan.
El detalle del error queda en la tabla integracion_ejecucion.
"""
import logging
import sys
from datetime import date

from sqlmodel import Session

from app.db.database import engine
from app.services.inventario_service import ayer_argentina, cargar_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    fecha = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else ayer_argentina()
    with Session(engine) as session:
        try:
            r = cargar_snapshot(session, fecha)
        except Exception:
            return 1  # cargar_snapshot ya registró y logueó el error
    logging.info("OK %s: %s grupos, %s unidades, USD %s", r["fecha"], r["grupos"], r["unidades"], r["importe_usd"])
    return 0


if __name__ == "__main__":
    sys.exit(main())