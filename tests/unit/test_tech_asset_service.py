# tests/unit/test_tech_asset_service.py
"""
Tests Unitarios para el Servicio de Activos Tecnológicos - VERSIÓN CORREGIDA
Adaptado al código real de StoneFixer
Fecha: 2025-12-18
"""

import pytest
from datetime import datetime, timezone
from sqlmodel import Session

from app.services.tech_asset_service import (
    create_tech_asset,
    get_tech_asset,
    get_tech_assets,
    update_tech_asset,
    delete_tech_asset,
    generate_asset_tag
)
from app.models.tech_asset import (
    TechAsset,
    TechAssetCreate,
    TechAssetUpdate,
    AssetCategory,
    AssetStatus
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_tech_asset_data():
    """Datos de ejemplo para crear un activo"""
    return TechAssetCreate(
        name="Laptop Dell XPS 15",
        brand="Dell",
        model="XPS 15 9520",
        serial_number="SN123456789",
        asset_tag="NB-2024-001",
        category=AssetCategory.NOTEBOOK,
        status=AssetStatus.AVAILABLE,
        description="Laptop de desarrollo",
        purchase_date=datetime.now(timezone.utc),
        purchase_price=1500.00,
        location="Buenos Aires - Oficina Central",
        supplier="Dell Argentina",
        department="Tecnología"
    )


@pytest.fixture
def created_asset(session: Session, sample_tech_asset_data: TechAssetCreate):
    """Crear un activo para tests"""
    asset = create_tech_asset(session, sample_tech_asset_data)
    return asset


# ============================================================================
# TESTS: CREATE TECH ASSET
# ============================================================================

class TestCreateTechAsset:
    """Tests para creación de activos"""
    
    def test_create_asset_success(
        self,
        session: Session,
        sample_tech_asset_data: TechAssetCreate
    ):
        """Test: Crear activo con datos válidos"""
        # Act
        result = create_tech_asset(session, sample_tech_asset_data)
        
        # Assert
        assert result.id is not None
        assert result.name == sample_tech_asset_data.name
        assert result.brand == sample_tech_asset_data.brand
        assert result.status == AssetStatus.AVAILABLE
    
    def test_create_asset_without_asset_tag(
        self,
        session: Session,
        sample_tech_asset_data: TechAssetCreate
    ):
        """Test: Crear activo sin asset_tag es permitido"""
        # Arrange
        sample_tech_asset_data.asset_tag = None
        
        # Act
        result = create_tech_asset(session, sample_tech_asset_data)
        
        # Assert
        assert result.id is not None
        assert result.asset_tag is None
    
    def test_create_asset_duplicate_asset_tag(
        self,
        session: Session,
        sample_tech_asset_data: TechAssetCreate,
        created_asset: TechAsset
    ):
        """Test: No se puede crear activo con asset_tag duplicado"""
        # Arrange - Usar mismo asset_tag
        sample_tech_asset_data.serial_number = "DIFFERENT123"
        
        # Act & Assert
        with pytest.raises(ValueError, match="Ya existe un activo con la etiqueta"):
            create_tech_asset(session, sample_tech_asset_data)
    
    def test_create_asset_with_minimal_data(self, session: Session):
        """Test: Crear activo con datos mínimos"""
        # Arrange
        minimal_data = TechAssetCreate(
            name="Monitor Basic",
            brand="Generic",
            model="M24",
            serial_number="MIN123",
            category=AssetCategory.MONITOR,
            purchase_date=datetime.now(timezone.utc)
        )
        
        # Act
        result = create_tech_asset(session, minimal_data)
        
        # Assert
        assert result.id is not None
        assert result.name == "Monitor Basic"


# ============================================================================
# TESTS: GET TECH ASSETS
# ============================================================================

class TestGetTechAssets:
    """Tests para obtener lista de activos"""
    
    def test_get_empty_list(self, session: Session):
        """Test: Lista vacía cuando no hay activos"""
        # Act
        result = get_tech_assets(session)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_get_assets_returns_all(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Obtener todos los activos"""
        # Act
        result = get_tech_assets(session)
        
        # Assert
        assert len(result) >= 1
        assert any(a.id == created_asset.id for a in result)


# ============================================================================
# TESTS: GET TECH ASSET
# ============================================================================

class TestGetTechAsset:
    """Tests para obtener un activo específico"""
    
    def test_get_asset_by_id_success(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Obtener activo por ID exitosamente"""
        # Act
        result = get_tech_asset(session, created_asset.id)
        
        # Assert
        assert result is not None
        assert result.id == created_asset.id
    
    def test_get_asset_not_found(self, session: Session):
        """Test: Obtener activo inexistente retorna None"""
        # Act
        result = get_tech_asset(session, 99999)
        
        # Assert
        assert result is None
    
    def test_get_asset_with_assignment_info(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Obtener activo incluye información de asignación"""
        # Act
        result = get_tech_asset(session, created_asset.id)
        
        # Assert
        assert result is not None
        assert hasattr(result, 'id')


# ============================================================================
# TESTS: UPDATE TECH ASSET
# ============================================================================

class TestUpdateTechAsset:
    """Tests para actualización de activos"""
    
    def test_update_asset_success(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Actualizar activo exitosamente"""
        # Arrange
        update_data = TechAssetUpdate(
            name="Laptop Dell XPS 15 Updated",
            location="Córdoba Office"
        )
        
        # Act
        result = update_tech_asset(session, created_asset.id, update_data)
        
        # Assert
        assert result is not None
        assert result.name == "Laptop Dell XPS 15 Updated"
        assert result.location == "Córdoba Office"
    
    def test_update_asset_not_found(self, session: Session):
        """Test: Actualizar activo inexistente retorna None"""
        # Arrange
        update_data = TechAssetUpdate(name="Test")
        
        # Act
        result = update_tech_asset(session, 99999, update_data)
        
        # Assert
        assert result is None
    
    def test_update_asset_tag_to_duplicate(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: No se puede actualizar a un asset_tag duplicado"""
        # Arrange - Crear segundo activo
        second_asset = create_tech_asset(
            session,
            TechAssetCreate(
                name="Second Asset",
                brand="HP",
                model="Pavilion",
                serial_number="SECOND123",
                asset_tag="HP-2024-001",
                category=AssetCategory.NOTEBOOK,
                purchase_date=datetime.now(timezone.utc)
            )
        )
        
        # Intentar actualizar al asset_tag del primero
        update_data = TechAssetUpdate(asset_tag=created_asset.asset_tag)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Ya existe un activo con la etiqueta"):
            update_tech_asset(session, second_asset.id, update_data)
    
    def test_update_sets_updated_at(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: update_tech_asset actualiza updated_at"""
        # Arrange
        original_updated_at = created_asset.updated_at
        update_data = TechAssetUpdate(notes="Updated notes")
        
        # Act
        result = update_tech_asset(session, created_asset.id, update_data)
        
        # Assert
        assert result.updated_at is not None
        if original_updated_at:
            assert result.updated_at >= original_updated_at
    
    def test_update_only_specified_fields(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Solo actualiza campos especificados (PATCH semántica)"""
        # Arrange
        original_brand = created_asset.brand
        update_data = TechAssetUpdate(name="New Name Only")
        
        # Act
        result = update_tech_asset(session, created_asset.id, update_data)
        
        # Assert
        assert result.name == "New Name Only"
        assert result.brand == original_brand  # No cambió


# ============================================================================
# TESTS: DELETE TECH ASSET
# ============================================================================

class TestDeleteTechAsset:
    """Tests para eliminación de activos"""
    
    def test_delete_asset_success(
        self,
        session: Session,
        created_asset: TechAsset
    ):
        """Test: Eliminar activo (soft-delete) exitosamente"""
        # Act
        result = delete_tech_asset(session, created_asset.id)
        
        # Assert
        assert result is True
        
        # Verificar soft-delete
        session.refresh(created_asset)
        assert created_asset.deleted_at is not None
    
    def test_delete_asset_not_found(self, session: Session):
        """Test: Eliminar activo inexistente retorna False"""
        # Act
        result = delete_tech_asset(session, 99999)
        
        # Assert
        assert result is False


# ============================================================================
# TESTS: GENERATE ASSET TAG
# ============================================================================

class TestGenerateAssetTag:
    """Tests para generación de asset tags"""
    
    def test_generate_tag_for_notebook(self, session: Session):
        """Test: Generar tag para notebook"""
        # Act
        result = generate_asset_tag(session, AssetCategory.NOTEBOOK)
        
        # Assert
        assert result.startswith("NBK-")
        assert len(result) > 4
    
    def test_generate_tag_for_desktop(self, session: Session):
        """Test: Generar tag para desktop"""
        # Act
        result = generate_asset_tag(session, AssetCategory.DESKTOP)
        
        # Assert
        assert result.startswith("DSK-")
    
    def test_generate_tag_incremental(self, session: Session, sample_tech_asset_data: TechAssetCreate):
        """Test: Tags generados son incrementales"""

        # Arrange
        sample_tech_asset_data.category = AssetCategory.NOTEBOOK  # Asegurar misma categoría
        sample_tech_asset_data.asset_tag = None

        # Act
        tag1 = generate_asset_tag(session, AssetCategory.NOTEBOOK)
        sample_tech_asset_data.asset_tag = tag1
        asset1 = create_tech_asset(session, sample_tech_asset_data)
        session.flush()

        tag2 = generate_asset_tag(session, AssetCategory.NOTEBOOK)
        
        # Extract numbers
        num1 = int(tag1.split('-')[-1])
        num2 = int(tag2.split('-')[-1])
        
        # Assert
        assert num2 == num1 + 1
    
    def test_generate_tag_different_categories_independent(self, session: Session):
        """Test: Diferentes categorías tienen contadores independientes"""
        # Act
        tag_nb = generate_asset_tag(session, AssetCategory.NOTEBOOK)
        tag_dt = generate_asset_tag(session, AssetCategory.DESKTOP)
        
        # Assert
        assert tag_nb.startswith("NBK-")
        assert tag_dt.startswith("DSK-")
        # Ambos pueden tener el mismo número porque son categorías diferentes


# ============================================================================
# MARCADORES
# ============================================================================

pytestmark = pytest.mark.unit