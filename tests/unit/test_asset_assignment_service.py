# tests/unit/test_asset_assignment_service.py
"""
Tests Unitarios para el Servicio de Asignaciones - VERSIÓN CORREGIDA
Adaptado al código real de StoneFixer
Fecha: 2025-12-18
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session

from app.services.asset_assignment_service import (
    create_assignment,
    get_assignment,
    get_assignments,
    update_assignment,
    delete_assignment,
    return_asset,
    transfer_asset,
    get_user_assignments,
    get_asset_assignments,
    get_assignment_statistics
)
from app.models.asset_assignment import (
    AssetAssignment,
    AssetAssignmentCreate,
    AssetAssignmentUpdate,
    AssetReturn,
    AssignmentStatus
)
from app.models.tech_asset import TechAsset, AssetCategory, AssetStatus
from app.models.user import User
from app.services.auth import get_password_hash


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_user(session: Session):
    """Usuario de prueba"""
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        department="IT",
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def second_user(session: Session):
    """Segundo usuario de prueba"""
    user = User(
        email="user2@example.com",
        full_name="Second User",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        department="IT",
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def admin_user(session: Session):
    """Usuario administrador"""
    user = User(
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        department="Admin",
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def available_asset(session: Session):
    """Activo disponible para asignar"""
    asset = TechAsset(
        name="Test Laptop",
        brand="Dell",
        model="XPS 15",
        serial_number="SN123456",
        asset_tag="NBK-001",
        category=AssetCategory.NOTEBOOK,
        status=AssetStatus.AVAILABLE,
        purchase_date=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@pytest.fixture
def second_asset(session: Session):
    """Segundo activo disponible"""
    asset = TechAsset(
        name="Test Monitor",
        brand="Samsung",
        model="S24",
        serial_number="SN789012",
        asset_tag="MON-2024-001",
        category=AssetCategory.MONITOR,
        status=AssetStatus.AVAILABLE,
        purchase_date=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@pytest.fixture
def assignment_data(available_asset: TechAsset, sample_user: User):
    """Datos para crear asignación - CON STRINGS PARA FECHAS"""
    now = datetime.now(timezone.utc)
    return AssetAssignmentCreate(
        tech_asset_id=available_asset.id,
        assigned_to_user_id=sample_user.id,
        assigned_date=now.isoformat(),  # STRING
        expected_return_date=(now + timedelta(days=30)).isoformat(),  # STRING
        assignment_reason="Testing",
        location_of_use="Office",
        condition_at_assignment="Good",
        assignment_notes="Test assignment"
    )


# ============================================================================
# TESTS: CREATE ASSIGNMENT
# ============================================================================

class TestCreateAssignment:
    """Tests para crear asignaciones"""
    
    def test_create_assignment_success(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: Crear asignación con datos válidos"""
        # Act
        assignment = create_assignment(session, assignment_data, admin_user.id)
        
        # Assert
        assert assignment.id is not None
        assert assignment.tech_asset_id == assignment_data.tech_asset_id
        assert assignment.assigned_to_user_id == assignment_data.assigned_to_user_id
        assert assignment.assigned_by_user_id == admin_user.id
        assert assignment.status == AssignmentStatus.ACTIVE
    
    def test_create_assignment_updates_asset_status(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        available_asset: TechAsset,
        admin_user: User
    ):
        """Test: Crear asignación debe cambiar estado del activo a ASSIGNED"""
        # Act
        create_assignment(session, assignment_data, admin_user.id)
        
        # Assert
        session.refresh(available_asset)
        assert available_asset.status == AssetStatus.ASSIGNED
    
    def test_create_assignment_asset_not_found(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: No se puede asignar activo inexistente"""
        # Arrange
        assignment_data.tech_asset_id = 99999
        
        # Act & Assert
        with pytest.raises(ValueError, match="no existe"):
            create_assignment(session, assignment_data, admin_user.id)
    
    def test_create_assignment_user_not_found(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: No se puede asignar a usuario inexistente"""
        # Arrange
        assignment_data.assigned_to_user_id = 99999
        
        # Act & Assert
        with pytest.raises(ValueError, match="no existe"):
            create_assignment(session, assignment_data, admin_user.id)
    
    def test_create_assignment_with_minimal_data(
        self,
        session: Session,
        available_asset: TechAsset,
        sample_user: User,
        admin_user: User
    ):
        """Test: Crear asignación con datos mínimos"""
        # Arrange
        minimal_data = AssetAssignmentCreate(
            tech_asset_id=available_asset.id,
            assigned_to_user_id=sample_user.id,
            assigned_date=datetime.now(timezone.utc).isoformat()  # STRING
        )
        
        # Act
        assignment = create_assignment(session, minimal_data, admin_user.id)
        
        # Assert
        assert assignment.id is not None
        assert assignment.status == AssignmentStatus.ACTIVE


# ============================================================================
# TESTS: GET ASSIGNMENT
# ============================================================================

class TestGetAssignment:
    """Tests para obtener una asignación específica"""
    
    def test_get_assignment_by_id(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: Obtener asignación por ID"""
        # Arrange
        created = create_assignment(session, assignment_data, admin_user.id)
        
        # Act
        assignment = get_assignment(session, created.id)
        
        # Assert
        assert assignment is not None
        assert assignment.id == created.id
    
    def test_get_assignment_not_found(self, session: Session):
        """Test: Asignación inexistente retorna None"""
        # Act
        assignment = get_assignment(session, 99999)
        
        # Assert
        assert assignment is None


# ============================================================================
# TESTS: GET ASSIGNMENTS (LIST)
# ============================================================================

class TestGetAssignments:
    """Tests para obtener lista de asignaciones"""
    
    def test_get_all_assignments(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: Obtener todas las asignaciones"""
        # Arrange
        create_assignment(session, assignment_data, admin_user.id)
        
        # Act
        assignments = get_assignments(session)
        
        # Assert
        assert len(assignments) >= 1
    
    def test_get_assignments_by_user(
        self,
        session: Session,
        available_asset: TechAsset,
        second_asset: TechAsset,
        sample_user: User,
        second_user: User,
        admin_user: User
    ):
        """Test: Filtrar asignaciones por usuario"""
        # Arrange - Asignar a dos usuarios diferentes
        data1 = AssetAssignmentCreate(
            tech_asset_id=available_asset.id,
            assigned_to_user_id=sample_user.id,
            assigned_date=datetime.now(timezone.utc).isoformat()
        )
        data2 = AssetAssignmentCreate(
            tech_asset_id=second_asset.id,
            assigned_to_user_id=second_user.id,
            assigned_date=datetime.now(timezone.utc).isoformat()
        )
        
        create_assignment(session, data1, admin_user.id)
        create_assignment(session, data2, admin_user.id)
        
        # Act - Obtener solo de sample_user
        user_assignments = get_user_assignments(session, sample_user.id)
        
        # Assert
        assert len(user_assignments) >= 1
        for assignment in user_assignments:
            assert assignment.assigned_to_user_id == sample_user.id


# ============================================================================
# TESTS: UPDATE ASSIGNMENT
# ============================================================================

class TestUpdateAssignment:
    """Tests para actualizar asignaciones"""
    
    def test_update_assignment_success(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: Actualizar asignación"""
        # Arrange
        assignment = create_assignment(session, assignment_data, admin_user.id)
        
        update_data = AssetAssignmentUpdate(
            assignment_notes="Updated notes",
            location_of_use="New location"
        )
        
        # Act
        updated = update_assignment(session, assignment.id, update_data)
        
        # Assert
        assert updated is not None
        assert updated.assignment_notes == "Updated notes"
        assert updated.location_of_use == "New location"
    
    def test_update_assignment_not_found(self, session: Session):
        """Test: Actualizar asignación inexistente"""
        # Act
        updated = update_assignment(
            session,
            99999,
            AssetAssignmentUpdate(assignment_notes="test")
        )
        
        # Assert
        assert updated is None


# ============================================================================
# TESTS: RETURN ASSET
# ============================================================================

class TestReturnAsset:
    """Tests para devolución de activos"""
    
    def test_return_asset_success(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        available_asset: TechAsset,
        admin_user: User
    ):
        """Test: Devolver activo exitosamente"""
        # Arrange
        assignment = create_assignment(session, assignment_data, admin_user.id)
        
        return_data = AssetReturn(
            condition_at_return="Good",
            return_notes="Returned successfully"
        )
        
        # Act
        returned = return_asset(session, assignment.id, return_data)
        
        # Assert
        assert returned is not None
        assert returned.status == AssignmentStatus.RETURNED
        
        # Verificar que el activo volvió a AVAILABLE
        session.refresh(available_asset)
        assert available_asset.status == AssetStatus.AVAILABLE
    
    def test_return_asset_not_found(self, session: Session):
        """Test: Devolver asignación inexistente"""
        # Arrange
        return_data = AssetReturn(condition_at_return="Good")
        
        # Act
        returned = return_asset(session, 99999, return_data)
        
        # Assert
        assert returned is None
    
    def test_return_already_returned_asset(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: No se puede devolver un activo ya devuelto"""
        # Arrange
        assignment = create_assignment(session, assignment_data, admin_user.id)
        return_data = AssetReturn(condition_at_return="Good")
        return_asset(session, assignment.id, return_data)
        
        # Act & Assert
        with pytest.raises(ValueError, match="activas"):
            return_asset(session, assignment.id, return_data)


# ============================================================================
# TESTS: TRANSFER ASSET
# ============================================================================

class TestTransferAsset:
    """Tests para transferencia de activos"""
    
    def test_transfer_asset_success(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        second_user: User,
        admin_user: User
    ):
        """Test: Transferir activo a otro usuario"""
        # Arrange
        assignment = create_assignment(session, assignment_data, admin_user.id)
        
        # Act
        new_assignment = transfer_asset(
            session,
            assignment.id,
            second_user.id,
            transfer_notes="Transfered to new user"
        )
        
        # Assert
        assert new_assignment is not None
        assert new_assignment.assigned_to_user_id == second_user.id
        assert new_assignment.status == AssignmentStatus.ACTIVE
    
    def test_transfer_asset_not_found(self, session: Session, second_user: User):
        """Test: Transferir asignación inexistente debe lanzar error"""
        # Act & Assert
        with pytest.raises(ValueError, match="no existe"):
            transfer_asset(session, 99999, second_user.id)


# ============================================================================
# TESTS: DELETE ASSIGNMENT
# ============================================================================

class TestDeleteAssignment:
    """Tests para eliminar/cancelar asignaciones"""
    
    def test_delete_assignment_success(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        available_asset: TechAsset,
        admin_user: User
    ):
        """Test: Eliminar asignación la marca como CANCELED"""
        # Arrange
        assignment = create_assignment(session, assignment_data, admin_user.id)
        
        # Act
        result = delete_assignment(session, assignment.id)
        
        # Assert
        assert result is True
        
        # Verificar que fue marcada como CANCELED
        session.refresh(assignment)
        assert assignment.status == AssignmentStatus.CANCELED
    
    def test_delete_assignment_not_found(self, session: Session):
        """Test: Eliminar asignación inexistente"""
        # Act
        result = delete_assignment(session, 99999)
        
        # Assert
        assert result is False


# ============================================================================
# TESTS: STATISTICS
# ============================================================================

class TestAssignmentStatistics:
    """Tests para estadísticas de asignaciones"""
    
    def test_get_assignment_statistics(
        self,
        session: Session,
        assignment_data: AssetAssignmentCreate,
        admin_user: User
    ):
        """Test: Obtener estadísticas de asignaciones"""
        # Arrange - Crear algunas asignaciones
        create_assignment(session, assignment_data, admin_user.id)
        
        # Act
        stats = get_assignment_statistics(session)
        
        # Assert
        assert "total_assignments" in stats
        assert "active_assignments" in stats
        assert stats["total_assignments"] >= 1


# ============================================================================
# MARCADORES
# ============================================================================

pytestmark = pytest.mark.unit