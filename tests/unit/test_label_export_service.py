from openpyxl import load_workbook
from app.services.label_export_service import generate_label_export
from app.services.tech_asset_service import create_tech_asset
from app.models.tech_asset import TechAssetCreate, AssetCategory, CableType
from datetime import datetime, timezone


def test_export_splits_by_category(session):
    create_tech_asset(session, TechAssetCreate(
        name="Notebook Dell", brand="Dell", model="5420",
        serial_number="SNEXP001", asset_tag="NBK-001",
        category=AssetCategory.NOTEBOOK,
        purchase_date=datetime.now(timezone.utc),
    ))
    create_tech_asset(session, TechAssetCreate(
        name="Cable red", brand="Generico", model="CAT6",
        serial_number="SNEXP002", asset_tag="CAB-001",
        category=AssetCategory.CABLE, connector_type=CableType.RJ45,
        purchase_date=datetime.now(timezone.utc),
    ))

    buffer, b1_count, d110_count = generate_label_export(session)

    assert b1_count == 1
    assert d110_count == 1

    wb = load_workbook(buffer)
    assert wb["B1"]["A2"].value == "NBK-001"
    assert wb["B1"]["D2"].value.endswith("/a/NBK-001")
    assert wb["D110"]["A2"].value == "CAB-001"
    assert wb["D110"]["B2"].value == "RJ45"


def test_export_excludes_assets_without_tag(session):
    create_tech_asset(session, TechAssetCreate(
        name="Monitor sin tag", brand="LG", model="27",
        serial_number="SNEXP003", asset_tag=None,
        category=AssetCategory.MONITOR,
        purchase_date=datetime.now(timezone.utc),
    ))
    _, b1_count, d110_count = generate_label_export(session)
    assert b1_count == 0
    assert d110_count == 0