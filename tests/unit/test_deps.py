# tests/unit/test_deps.py
"""
Tests Unitarios para Dependencias de FastAPI - VERSIÓN CORREGIDA
Adaptado al código real de StoneFixer
Fecha: 2025-12-18
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlmodel import Session

from app.api.deps import (
    get_current_user,
    get_user_roles
)
from app.models.user import User
from app.models.role import UserRole, Role
from app.services.auth import create_access_token, get_password_hash


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_token_admin():
    """Token JWT válido para admin"""
    return create_access_token(
        data={"sub": "admin@test.com"},
        user_roles=["admin"]
    )


@pytest.fixture
def mock_token_user():
    """Token JWT válido para usuario regular"""
    return create_access_token(
        data={"sub": "user@test.com"},
        user_roles=["user"]
    )


@pytest.fixture
def mock_token_invalid():
    """Token JWT inválido"""
    return "invalid.token.here"


@pytest.fixture
def mock_token_expired():
    """Token JWT expirado"""
    return create_access_token(
        data={"sub": "expired@test.com"},
        user_roles=["user"],
        expires_delta=timedelta(seconds=-1)
    )


@pytest.fixture
def admin_user_with_role(session: Session):
    """Usuario admin con rol asignado"""
    user = User(
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Agregar rol admin
    role = UserRole(user_id=user.id, role=Role.ADMIN.value)
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def regular_user_with_role(session: Session):
    """Usuario regular con rol user"""
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
    role = UserRole(user_id=user.id, role=Role.USER.value)
    session.add(role)
    session.commit()
    
    return user


@pytest.fixture
def manager_user(session: Session):
    """Usuario con rol manager"""
    user = User(
        email="manager@test.com",
        full_name="Manager User",
        hashed_password=get_password_hash("mgr123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Agregar rol manager
    role = UserRole(user_id=user.id, role=Role.MANAGER.value)
    session.add(role)
    session.commit()
    
    return user


# ============================================================================
# TESTS: get_current_user
# ============================================================================

class TestGetCurrentUser:
    """Tests para obtener usuario actual desde token"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(
        self,
        session: Session,
        admin_user_with_role: User,
        mock_token_admin: str
    ):
        """Test: Token válido debe retornar usuario"""
        # Act
        user = await get_current_user(token=mock_token_admin, db=session)
        
        # Assert
        assert user is not None
        assert user.email == "admin@test.com"
        assert user.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, session: Session):
        """Test: Token inválido debe lanzar 401"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="invalid_token", db=session)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, session: Session):
        """Test: Token válido pero usuario no existe debe lanzar 401"""
        # Token para usuario que no existe
        token = create_access_token(
            data={"sub": "noexiste@test.com"},
            user_roles=["user"]
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=session)
        
        assert exc_info.value.status_code == 401


# ============================================================================
# TESTS: Funciones de Utilidad
# ============================================================================

class TestUtilityFunctions:
    """Tests para funciones de utilidad"""
    
    def test_get_user_roles(self, session: Session, admin_user_with_role: User):
        """Test: Obtener roles de un usuario"""
        # Act
        roles = get_user_roles(session, admin_user_with_role.id)
        
        # Assert
        assert Role.ADMIN.value in roles
        assert len(roles) >= 1
    
    def test_get_user_roles_multiple(self, session: Session):
        """Test: Usuario con múltiples roles"""
        # Crear usuario con múltiples roles
        user = User(
            email="multi@test.com",
            full_name="Multi Role",
            hashed_password=get_password_hash("pass123"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        session.add(UserRole(user_id=user.id, role=Role.USER.value))
        session.add(UserRole(user_id=user.id, role=Role.ADMIN.value))
        session.add(UserRole(user_id=user.id, role=Role.MANAGER.value))
        session.commit()
        
        # Act
        roles = get_user_roles(session, user.id)
        
        # Assert
        assert len(roles) == 3
        assert Role.USER.value in roles
        assert Role.ADMIN.value in roles
        assert Role.MANAGER.value in roles
    
    def test_get_user_roles_no_roles(self, session: Session):
        """Test: Usuario sin roles"""
        # Crear usuario sin roles
        user = User(
            email="noroles@test.com",
            full_name="No Roles",
            hashed_password=get_password_hash("pass123"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Act
        roles = get_user_roles(session, user.id)
        
        # Assert
        assert len(roles) == 0
    
    def test_get_roles_for_nonexistent_user(self, session: Session):
        """Test: Obtener roles de usuario inexistente"""
        # Act
        roles = get_user_roles(session, 99999)
        
        # Assert
        assert len(roles) == 0


# ============================================================================
# MARCADORES
# ============================================================================

pytestmark = pytest.mark.unit