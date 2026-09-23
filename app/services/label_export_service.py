"""
Servicio de exportación de etiquetas para impresión Niimbot (B1 / D110)
"""
from io import BytesIO
from typing import List, Optional

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlmodel import Session, select

from app.config import settings
from app.models.tech_asset import TechAsset, AssetCategory, CableType

CONNECTOR_DISPLAY_LABELS = {
    CableType.RJ45: "RJ45",
    CableType.USB_A: "USB-A",
    CableType.USB_B: "USB-B",
    CableType.USB_C: "USB-C",
    CableType.HDMI: "HDMI",
    CableType.DISPLAYPORT: "DP",
    CableType.VGA: "VGA",
    CableType.INTERLOCK: "Interlock",
    CableType.AUDIO_JACK: "Audio",
    CableType.PS2: "PS/2",
    CableType.SATA_ALIMENTACION: "SATA",
    CableType.OTRO: "Otro",
}


def _build_qr_url(asset_tag: str) -> str:
    base = settings.LABEL_BASE_URL.rstrip("/")
    return f"{base}/a/{asset_tag}"


def _get_exportable_assets(
    db: Session,
    ids: Optional[List[int]] = None,
    category: Optional[AssetCategory] = None,
) -> List[TechAsset]:
    query = select(TechAsset).where(TechAsset.deleted_at.is_(None))

    if ids:
        query = query.where(TechAsset.id.in_(ids))
    if category:
        query = query.where(TechAsset.category == category)

    assets = db.exec(query).all()

    # Sin asset_tag no hay nada que imprimir - se excluyen, no se rompe el export
    return [a for a in assets if a.asset_tag]


def _write_b1_sheet(ws: Worksheet, assets: List[TechAsset]) -> int:
    ws.append(["asset_tag", "name", "category", "qr_url"])
    count = 0
    for asset in assets:
        if asset.category == AssetCategory.CABLE:
            continue
        category_value = (
            asset.category.value if hasattr(asset.category, "value") else asset.category
        )
        ws.append([
            asset.asset_tag,
            asset.name,
            category_value,
            _build_qr_url(asset.asset_tag),
        ])
        count += 1
    return count


def _write_d110_sheet(ws: Worksheet, assets: List[TechAsset]) -> int:
    ws.append(["asset_tag", "connector_type", "barcode_value"])
    count = 0
    for asset in assets:
        if asset.category != AssetCategory.CABLE:
            continue
        connector_label = (
            CONNECTOR_DISPLAY_LABELS.get(asset.connector_type, "")
            if asset.connector_type
            else ""
        )
        ws.append([asset.asset_tag, connector_label, asset.asset_tag])
        count += 1
    return count


def generate_label_export(
    db: Session,
    ids: Optional[List[int]] = None,
    category: Optional[AssetCategory] = None,
) -> tuple[BytesIO, int, int]:
    """
    Genera un .xlsx con dos hojas (B1, D110) listas para importar
    en la app Niimbot. Devuelve el buffer + cantidad de filas por hoja.
    """
    assets = _get_exportable_assets(db, ids=ids, category=category)

    wb = Workbook()
    b1_sheet = wb.active
    b1_sheet.title = "B1"
    b1_count = _write_b1_sheet(b1_sheet, assets)

    d110_sheet = wb.create_sheet("D110")
    d110_count = _write_d110_sheet(d110_sheet, assets)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return buffer, b1_count, d110_count