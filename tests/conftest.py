# tests/conftest.py
"""
Configuración global de pytest para StoneFixer - VERSIÓN CORREGIDA
Adaptado al código real
Fecha: 2025-12-18
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from datetime import datetime, timezone

# Imports de modelos
from app.models.tech_asset import TechAsset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_maintenance import AssetMaintenance
from app.models.user import User
from app.models.role import UserRole
from app.services.auth import create_access_token, get_password_hash

from app.models.tech_asset import TechAssetWithAssignment
from app.models.asset_assignment import AssetAssignmentRead

TechAssetWithAssignment.model_rebuild()


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(name="engine")
def engine_fixture():
    """
    Motor de SQLite en memoria para tests.
    Se usa StaticPool para que la conexión se mantenga durante los tests.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    """
    Sesión de base de datos que se rollback después de cada test.
    Esto asegura que los tests sean independientes.
    """
    print("\n🧪 Iniciando sesión de tests...")
    
    with Session(engine) as session:
        # Iniciar transacción
        yield session
        
        # Rollback después del test
        session.rollback()
    
    print("✅ Sesión de tests completada\n")


# ============================================================================
# CLIENT FIXTURES (para tests de integración)
# ============================================================================

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """
    Cliente de prueba para FastAPI.
    
    NOTA: Este fixture requiere que exista un app configurada.
    Si no tienes app/main.py, necesitas crear uno o adaptar esto.
    """
    # Intenta importar app de diferentes ubicaciones
    try:
        from main import app
    except ModuleNotFoundError:
        try:
            from app import app
        except ModuleNotFoundError:
            try:
                from main import app
            except ModuleNotFoundError:
                # Si no existe app, crear una básica para tests
                from fastapi import FastAPI
                app = FastAPI(title="StoneFixer Test")
                
                # Importar routers básicos si existen
                try:
                    from app.api.routes import auth_routes
                    app.include_router(auth_routes.router, tags=["auth"])
                except:
                    pass
    
    # Override de dependencia de BD
    from app.db.database import get_db
    
    def get_session_override():
        return session
    
    app.dependency_overrides[get_db] = get_session_override
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


# ============================================================================
# USER FIXTURES
# ============================================================================

@pytest.fixture
def admin_user(session: Session):
    """Usuario administrador con rol admin"""
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
    from app.models.role import Role
    role = UserRole(user_id=user.id, role=Role.ADMIN.value)
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def manager_user(session: Session):
    """Usuario manager"""
    user = User(
        email="manager@test.com",
        full_name="Manager Test",
        hashed_password=get_password_hash("manager123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    from app.models.role import Role
    role = UserRole(user_id=user.id, role=Role.MANAGER.value)
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def regular_user(session: Session):
    """Usuario regular sin permisos especiales"""
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
    
    from app.models.role import Role
    role = UserRole(user_id=user.id, role=Role.USER.value)
    session.add(role)
    session.commit()
    
    return user


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture
def auth_headers_admin(admin_user: User):
    """Headers de autenticación para admin"""
    token = create_access_token(
        data={"sub": admin_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_manager(manager_user: User):
    """Headers de autenticación para manager"""
    token = create_access_token(
        data={"sub": manager_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user(regular_user: User):
    """Headers de autenticación para usuario regular"""
    token = create_access_token(
        data={"sub": regular_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_tech_asset_data():
    """Datos de ejemplo para crear un activo tecnológico"""
    from app.models.tech_asset import TechAssetCreate, AssetCategory, AssetStatus
    
    return TechAssetCreate(
        name="Test Laptop",
        brand="Dell",
        model="XPS 15",
        serial_number="TEST123",
        asset_tag="TEST-001",
        category=AssetCategory.NOTEBOOK,
        status=AssetStatus.AVAILABLE,
        purchase_date=datetime.now(timezone.utc),
        purchase_price=1500.00,
        location="Test Office"
    )


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configuración global de pytest"""
    # Registrar marcadores personalizados
    config.addinivalue_line("markers", "unit: Tests unitarios")
    config.addinivalue_line("markers", "integration: Tests de integración")
    config.addinivalue_line("markers", "e2e: Tests end-to-end")
    config.addinivalue_line("markers", "slow: Tests lentos")
    config.addinivalue_line("markers", "smoke: Tests críticos para CI/CD")


def pytest_collection_modifyitems(config, items):
    """
    Modificar items de tests antes de ejecutarlos.
    Auto-marcar tests según su ubicación.
    """
    for item in items:
        # Marcar según directorio
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup que se ejecuta una vez al inicio de toda la sesión de tests"""
    import os
    # Configurar variables de entorno para tests
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    
    yield
    
    # Cleanup después de todos los tests
    os.environ.pop("TESTING", None)


@pytest.fixture(autouse=True)
def reset_database(session: Session):
    """Limpiar base de datos antes de cada test"""
    yield
    # El rollback en session_fixture ya limpia todo



@pytest.fixture
def auth_cookies_admin(admin_user: User):
    """Cookie de autenticación para admin"""
    token = create_access_token(data={"sub": admin_user.email})
    return {"access_token": token}


@pytest.fixture
def auth_cookies_manager(manager_user: User):
    """Cookie de autenticación para manager"""
    token = create_access_token(data={"sub": manager_user.email})
    return {"access_token": token}


@pytest.fixture
def auth_cookies_user(regular_user: User):
    """Cookie de autenticación para usuario regular"""
    token = create_access_token(data={"sub": regular_user.email})
    return {"access_token": token}