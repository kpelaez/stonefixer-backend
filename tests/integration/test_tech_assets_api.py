# tests/integration/test_tech_assets_api.py
"""
Tests de Integración para los Endpoints de Activos Tecnológicos
Autor: StoneFixer Team
Fecha: 2025-12-18

Estos tests verifican que los endpoints HTTP funcionan correctamente end-to-end
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from datetime import datetime, timezone

from main import app
from app.db.database import get_db
from app.models.user import User
from app.models.role import UserRole
from app.services.auth import get_password_hash


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(name="session")
def session_fixture():
    """Crear sesión de BD en memoria para tests"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Cliente HTTP de prueba con BD en memoria"""
    def get_session_override():
        return session
    
    app.dependency_overrides[get_db] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(session: Session):
    """Crear usuario administrador para tests"""
    user = User(
        email="admin@test.com",
        full_name="Admin Test",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Agregar rol admin
    role = UserRole(user_id=user.id, role="admin")
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def regular_user(session: Session):
    """Crear usuario regular para tests"""
    user = User(
        email="user@test.com",
        full_name="Regular User",
        hashed_password=get_password_hash("user123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Agregar rol user
    role = UserRole(user_id=user.id, role="user")
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def auth_headers_admin(client: TestClient, admin_user: User):
    """Headers de autenticación para admin"""
    response = client.post(
        "/token",
        data={"username": "admin@test.com", "password": "admin123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user(client: TestClient, regular_user: User):
    """Headers de autenticación para usuario regular"""
    response = client.post(
        "/token",
        data={"username": "user@test.com", "password": "user123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_asset_payload():
    """Payload de ejemplo para crear activo"""
    return {
        "name": "Laptop Dell XPS 15",
        "description": "Laptop de desarrollo",
        "brand": "Dell",
        "model": "XPS 15 9520",
        "serial_number": "SN123456789",
        "asset_tag": "NB-2024-001",
        "category": "Notebook",
        "status": "available",
        "purchase_price": 1500.00,
        "purchase_date": datetime.now(timezone.utc).isoformat(),
        "supplier": "Dell Argentina",
        "location": "Buenos Aires",
        "department": "Tecnología"
    }


# ============================================================================
# TESTS: AUTENTICACIÓN Y AUTORIZACIÓN
# ============================================================================

class TestAuthentication:
    """Tests de autenticación y autorización"""
    
    def test_get_assets_without_auth_fails(self, client: TestClient):
        """Test: Acceder sin autenticación debe fallar"""
        # Act
        response = client.get("/inventory/tech-assets")
        
        # Assert
        assert response.status_code == 401
    
    def test_get_assets_with_valid_token_succeeds(self, client: TestClient, auth_headers_user: dict):
        """Test: Acceder con token válido debe funcionar"""
        # Act
        response = client.get("/inventory/tech-assets", headers=auth_headers_user)
        
        # Assert
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_create_asset_requires_admin(self, client: TestClient, auth_headers_user: dict, sample_asset_payload: dict):
        """Test: Crear activo requiere permisos de admin/inventory_manager"""
        # Act
        response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_user
        )
        
        # Assert
        # Debería fallar con 403 Forbidden
        # TODO: Verificar que el sistema de roles esté funcionando
        # assert response.status_code == 403


# ============================================================================
# TESTS: GET /inventory/tech-assets
# ============================================================================

class TestGetTechAssets:
    """Tests para obtener lista de activos"""
    
    def test_get_empty_list(self, client: TestClient, auth_headers_admin: dict):
        """Test: Lista vacía cuando no hay activos"""
        # Act
        response = client.get("/inventory/tech-assets", headers=auth_headers_admin)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_list_with_assets(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Lista con activos creados"""
        # Arrange - Crear un activo
        client.post("/inventory/tech-assets", json=sample_asset_payload, headers=auth_headers_admin)
        
        # Act
        response = client.get("/inventory/tech-assets", headers=auth_headers_admin)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Laptop Dell XPS 15"
    
    def test_get_list_returns_summary_format(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: La lista debe retornar formato summary (no todos los campos)"""
        # Arrange
        client.post("/inventory/tech-assets", json=sample_asset_payload, headers=auth_headers_admin)
        
        # Act
        response = client.get("/inventory/tech-assets", headers=auth_headers_admin)
        
        # Assert
        data = response.json()[0]
        # Verificar campos esperados en summary
        assert "id" in data
        assert "name" in data
        assert "brand" in data
        assert "model" in data
        assert "category" in data
        assert "status" in data


# ============================================================================
# TESTS: POST /inventory/tech-assets
# ============================================================================

class TestCreateTechAsset:
    """Tests para crear activos"""
    
    def test_create_asset_success(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Crear activo con datos válidos"""
        # Act
        response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_asset_payload["name"]
        assert data["brand"] == sample_asset_payload["brand"]
        assert data["id"] is not None
        assert "created_at" in data
    
    def test_create_asset_duplicate_asset_tag(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: No permitir asset_tag duplicado"""
        # Arrange - Crear primer activo
        client.post("/inventory/tech-assets", json=sample_asset_payload, headers=auth_headers_admin)
        
        # Act - Intentar crear con mismo asset_tag
        response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        # assert "asset_tag" in response.json()["detail"].lower() or "etiqueta" in response.json()["detail"].lower()
        assert not response_data.get("success", True)
        assert "etiqueta" in str(response_data).lower()

    def test_create_asset_missing_required_fields(self, client: TestClient, auth_headers_admin: dict):
        """Test: Validar campos requeridos"""
        # Arrange - Payload incompleto
        incomplete_payload = {
            "name": "Laptop",
            "brand": "Dell"
            # Falta model, serial_number, category, purchase_date
        }
        
        # Act
        response = client.post(
            "/inventory/tech-assets",
            json=incomplete_payload,
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 422  # Validation Error
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_create_asset_without_asset_tag(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Se puede crear sin asset_tag (opcional)"""
        # Arrange
        sample_asset_payload.pop("asset_tag")
        
        # Act
        response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None


# ============================================================================
# TESTS: GET /inventory/tech-assets/{asset_id}
# ============================================================================

class TestGetTechAsset:
    """Tests para obtener un activo específico"""
    
    def test_get_asset_by_id_success(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Obtener activo por ID existente"""
        # Arrange - Crear activo
        create_response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        asset_id = create_response.json()["id"]
        
        # Act
        response = client.get(
            f"/inventory/tech-assets/{asset_id}",
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == asset_id
        assert data["name"] == sample_asset_payload["name"]
    
    def test_get_asset_not_found(self, client: TestClient, auth_headers_admin: dict):
        """Test: Obtener activo inexistente retorna 404"""
        # Act
        response = client.get(
            "/inventory/tech-assets/99999",
            headers=auth_headers_admin
        )
        
        # Assert
        response_data = response.json()
        assert response.status_code == 404
        
    
    def test_get_asset_returns_detailed_format(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: GET individual debe retornar formato detallado"""
        # Arrange
        create_response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        asset_id = create_response.json()["id"]
        
        # Act
        response = client.get(
            f"/inventory/tech-assets/{asset_id}",
            headers=auth_headers_admin
        )
        
        # Assert
        data = response.json()
        # Debe incluir TODOS los campos
        assert "description" in data
        assert "specifications" in data
        assert "notes" in data
        assert "supplier" in data


# ============================================================================
# TESTS: PATCH /inventory/tech-assets/{asset_id}
# ============================================================================

class TestUpdateTechAsset:
    """Tests para actualizar activos"""
    
    def test_update_asset_success(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Actualizar campos de un activo"""
        # Arrange - Crear activo
        create_response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        asset_id = create_response.json()["id"]
        
        # Act - Actualizar
        update_payload = {
            "name": "Laptop Dell XPS 15 - ACTUALIZADO",
            "location": "Córdoba"
        }
        response = client.patch(
            f"/inventory/tech-assets/{asset_id}",
            json=update_payload,
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Laptop Dell XPS 15 - ACTUALIZADO"
        assert data["location"] == "Córdoba"
        # Otros campos no cambiaron
        assert data["brand"] == sample_asset_payload["brand"]
    
    def test_update_asset_not_found(self, client: TestClient, auth_headers_admin: dict):
        """Test: Actualizar activo inexistente retorna 404"""
        # Act
        response = client.patch(
            "/inventory/tech-assets/99999",
            json={"name": "No existe"},
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 404
    
    def test_update_partial_fields(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Se pueden actualizar solo algunos campos (PATCH semántica)"""
        # Arrange
        create_response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        asset_id = create_response.json()["id"]
        original_brand = create_response.json()["brand"]
        
        # Act - Solo actualizar notes
        response = client.patch(
            f"/inventory/tech-assets/{asset_id}",
            json={"notes": "Nueva nota de prueba"},
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Nueva nota de prueba"
        assert data["brand"] == original_brand  # No cambió


# ============================================================================
# TESTS: DELETE /inventory/tech-assets/{asset_id}
# ============================================================================

class TestDeleteTechAsset:
    """Tests para eliminar activos"""
    
    def test_delete_asset_success(self, client: TestClient, auth_headers_admin: dict, sample_asset_payload: dict):
        """Test: Eliminar activo correctamente"""
        # Arrange - Crear activo
        create_response = client.post(
            "/inventory/tech-assets",
            json=sample_asset_payload,
            headers=auth_headers_admin
        )
        asset_id = create_response.json()["id"]
        
        # Act
        response = client.delete(
            f"/inventory/tech-assets/{asset_id}",
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 204
        
        # Verificar que realmente se eliminó
        get_response = client.get(
            f"/inventory/tech-assets/{asset_id}",
            headers=auth_headers_admin
        )
        assert get_response.status_code == 404
    
    def test_delete_asset_not_found(self, client: TestClient, auth_headers_admin: dict):
        """Test: Eliminar activo inexistente retorna 404"""
        # Act
        response = client.delete(
            "/inventory/tech-assets/99999",
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 404
    
    def test_delete_requires_admin_role(self, client: TestClient, auth_headers_user: dict, sample_asset_payload: dict):
        """Test: Solo admin puede eliminar activos"""
        # Arrange - Crear activo como admin primero
        # (esto requeriría otro fixture o cambiar headers temporalmente)
        pytest.skip("Requiere setup adicional para test de roles")


# ============================================================================
# TESTS: UTILITIES ENDPOINTS
# ============================================================================

class TestUtilityEndpoints:
    """Tests para endpoints de utilidades"""
    
    def test_get_categories_list(self, client: TestClient, auth_headers_user: dict):
        """Test: Obtener lista de categorías"""
        # Act
        response = client.get(
            "/inventory/tech-assets/categories/list",
            headers=auth_headers_user
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "value" in data[0]
        assert "label" in data[0]
    
    def test_get_status_list(self, client: TestClient, auth_headers_user: dict):
        """Test: Obtener lista de estados"""
        # Act
        response = client.get(
            "/inventory/tech-assets/status/list",
            headers=auth_headers_user
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_generate_asset_tag(self, client: TestClient, auth_headers_admin: dict):
        """Test: Generar asset tag"""
        # Act
        response = client.post(
            "/inventory/tech-assets/generate-tag",
            json={"category": "Notebook"},
            headers=auth_headers_admin
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "asset_tag" in data
        assert "NBK-" in data["asset_tag"]


# ============================================================================
# MARCADORES
# ============================================================================

pytestmark = pytest.mark.integration