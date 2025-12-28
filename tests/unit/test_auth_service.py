# tests/unit/test_auth_service.py
"""
Tests Unitarios para el Servicio de Autenticación - VERSIÓN CORREGIDA
Adaptado al código real de StoneFixer
Fecha: 2025-12-18
"""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.services.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token,  # Tu código usa verify_token, no decode_access_token
    authenticate_user,
    get_user_by_email,
    get_user_roles,
    has_role,
    has_any_role
)
from app.models.user import User
from app.models.role import UserRole, Role
from app.config import settings


# ============================================================================
# TESTS: PASSWORD HASHING
# ============================================================================

class TestPasswordHashing:
    """Tests para hash y verificación de contraseñas"""
    
    def test_hash_password_creates_hash(self):
        """Test: Hash de contraseña debe crear un hash diferente del texto plano"""
        password = "mi_password_123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50
        assert hashed.startswith("$2b$")
    
    def test_hash_same_password_twice_creates_different_hashes(self):
        """Test: Mismo password hasheado dos veces debe dar hashes diferentes (salt)"""
        password = "mi_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
    
    def test_verify_correct_password(self):
        """Test: Verificar password correcto debe retornar True"""
        password = "mi_password_123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self):
        """Test: Verificar password incorrecto debe retornar False"""
        password = "mi_password_123"
        wrong_password = "password_incorrecto"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False


# ============================================================================
# TESTS: JWT TOKENS
# ============================================================================

class TestJWTTokens:
    """Tests para creación y verificación de tokens JWT"""
    
    def test_create_access_token_with_email_and_roles(self):
        """Test: Crear token con email y roles"""
        email = "test@example.com"
        roles = ["user", "admin"]
        token = create_access_token(data={"sub": email}, user_roles=roles)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_create_access_token_with_custom_expiration(self):
        """Test: Crear token con expiración personalizada"""
        email = "test@example.com"
        roles = ["user"]
        expires_delta = timedelta(minutes=15)
        
        token = create_access_token(
            data={"sub": email},
            user_roles=roles,
            expires_delta=expires_delta
        )
        
        # Decodificar y verificar expiración
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Debe expirar en aproximadamente 15 minutos
        time_until_expiry = exp_datetime - now
        assert 14 <= time_until_expiry.total_seconds() / 60 <= 16
    
    def test_verify_valid_token(self):
        """Test: Verificar token válido"""
        email = "test@example.com"
        roles = ["user"]
        token = create_access_token(data={"sub": email}, user_roles=roles)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == email
        assert "roles" in payload
        assert payload["roles"] == roles
    
    def test_verify_invalid_token(self):
        """Test: Token inválido debe retornar None"""
        invalid_token = "esto_no_es_un_token_valido"
        
        payload = verify_token(invalid_token)
        assert payload is None
    
    def test_verify_token_with_wrong_signature(self):
        """Test: Token con firma incorrecta debe retornar None"""
        # Crear token con otra clave
        fake_token = jwt.encode(
            {"sub": "test@example.com"},
            "clave_incorrecta",
            algorithm="HS256"
        )
        
        payload = verify_token(fake_token)
        assert payload is None


# ============================================================================
# TESTS: USER AUTHENTICATION
# ============================================================================

class TestUserAuthentication:
    """Tests para autenticación de usuarios"""
    
    def test_authenticate_user_success(self, session):
        """Test: Autenticar con credenciales correctas"""
        # Arrange - Crear usuario
        password = "password123"
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash(password),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        
        # Act
        authenticated_user = authenticate_user(session, "test@example.com", password)
        
        # Assert
        assert authenticated_user is not False
        assert authenticated_user.email == "test@example.com"
    
    def test_authenticate_user_wrong_password(self, session):
        """Test: Autenticar con password incorrecto debe fallar"""
        # Arrange
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        
        # Act
        authenticated_user = authenticate_user(session, "test@example.com", "wrong_password")
        
        # Assert
        assert authenticated_user is False
    
    def test_authenticate_nonexistent_user(self, session):
        """Test: Autenticar usuario que no existe debe fallar"""
        # Act
        authenticated_user = authenticate_user(
            session,
            "noexiste@example.com",
            "cualquier_password"
        )
        
        # Assert
        assert authenticated_user is False


# ============================================================================
# TESTS: GET USER BY EMAIL
# ============================================================================

class TestGetUserByEmail:
    """Tests para obtener usuario por email"""
    
    def test_get_existing_user(self, session):
        """Test: Obtener usuario existente"""
        # Arrange
        user = User(
            email="existing@example.com",
            full_name="Existing User",
            hashed_password=get_password_hash("password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        
        # Act
        found_user = get_user_by_email(session, "existing@example.com")
        
        # Assert
        assert found_user is not None
        assert found_user.email == "existing@example.com"
    
    def test_get_nonexistent_user(self, session):
        """Test: Usuario que no existe debe retornar None"""
        # Act
        found_user = get_user_by_email(session, "noexiste@example.com")
        
        # Assert
        assert found_user is None


# ============================================================================
# TESTS: ROLES
# ============================================================================

class TestUserRoles:
    """Tests para manejo de roles de usuarios"""
    
    def test_get_user_roles(self, session):
        """Test: Obtener roles de un usuario"""
        # Arrange
        user = User(
            email="user@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Agregar roles
        session.add(UserRole(user_id=user.id, role=Role.USER.value))
        session.add(UserRole(user_id=user.id, role=Role.ADMIN.value))
        session.commit()
        
        # Act
        roles = get_user_roles(session, user.id)
        
        # Assert
        assert len(roles) == 2
        assert Role.USER.value in roles
        assert Role.ADMIN.value in roles
    
    def test_user_with_no_roles(self, session):
        """Test: Usuario sin roles retorna lista vacía"""
        # Arrange
        user = User(
            email="noroles@example.com",
            full_name="No Roles User",
            hashed_password=get_password_hash("password"),
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


# ============================================================================
# MARCADORES
# ============================================================================

pytestmark = pytest.mark.unit