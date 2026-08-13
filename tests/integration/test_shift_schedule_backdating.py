# tests/integration/test_shift_schedule_backdating.py
"""
Tests de integración: backdating de turnos y asignación a terceros por admin/manager.

Cubre el bug reportado: "como admin necesito poder cargar turnos en fechas pasadas
y asignárselos a otros miembros del equipo".

Requiere los fixtures ya definidos en tests/conftest.py:
    session, client, admin_user, manager_user, regular_user,
    auth_cookies_admin, auth_cookies_manager, auth_cookies_user

Nota sobre fechas: se elige deliberadamente un día hábil (lunes a viernes) tanto
para "ayer" como para "mañana", para no pisar la regla de negocio de "no hay
turnos early los findes" y contaminar los resultados con un 400 que no tiene
que ver con lo que se está testeando.
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.user import User

BASE = "/api/v1/shift-schedules"


# ============================================================================
# HELPERS
# ============================================================================

def _previous_weekday(from_date: date, days_back: int = 1) -> date:
    """Devuelve un día hábil (lun-vie) hacia atrás desde from_date."""
    d = from_date - timedelta(days=days_back)
    while d.weekday() >= 5:  # sábado=5, domingo=6
        d -= timedelta(days=1)
    return d


def _next_weekday(from_date: date, days_ahead: int = 1) -> date:
    """Devuelve un día hábil (lun-vie) hacia adelante desde from_date."""
    d = from_date + timedelta(days=days_ahead)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@pytest.fixture
def past_weekday() -> str:
    """Un día hábil pasado, en formato ISO."""
    return _previous_weekday(date.today(), days_back=5).isoformat()


@pytest.fixture
def future_weekday() -> str:
    """Un día hábil futuro, en formato ISO (evita chocar con el deadline de 17hs de hoy)."""
    return _next_weekday(date.today(), days_ahead=5).isoformat()


CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _create_shift(client: TestClient, cookies: dict, date_str: str, target_user_id: int | None = None, notes: str = "test"):
    payload = {"date": date_str, "shift_type": "regular", "notes": notes}
    if target_user_id is not None:
        payload["target_user_id"] = target_user_id
    return client.post(f"{BASE}/", json=payload, cookies=cookies, headers=CSRF_HEADERS)


# ============================================================================
# CASO 1: usuario regular NO puede asignar turnos a otros usuarios
# ============================================================================

class TestRegularUserCannotAssignOthers:

    def test_regular_user_target_user_id_forbidden(
        self, client: TestClient, auth_cookies_user: dict,
        regular_user: User, manager_user: User, future_weekday: str,
    ):
        """Un user común mandando target_user_id de otro usuario -> 403."""
        response = _create_shift(
            client, auth_cookies_user, future_weekday,
            target_user_id=manager_user.id,
        )
        assert response.status_code == 403

    def test_regular_user_self_assign_still_works(
        self, client: TestClient, auth_cookies_user: dict,
        regular_user: User, future_weekday: str,
    ):
        """Un user común autoasignándose (sin target_user_id, o con el propio id) sigue funcionando."""
        response = _create_shift(client, auth_cookies_user, future_weekday)
        assert response.status_code == 201
        body = response.json()
        assert body["user_id"] == regular_user.id
        assert body["modified_by_user_id"] is None


# ============================================================================
# CASO 2: usuario regular sigue bloqueado en fechas pasadas
# ============================================================================

class TestRegularUserStillBlockedInPast:

    def test_regular_user_cannot_create_past_shift(
        self, client: TestClient, auth_cookies_user: dict, past_weekday: str,
    ):
        """El fix de backdating es SOLO para admin/manager. Un user común debe seguir recibiendo 400."""
        response = _create_shift(client, auth_cookies_user, past_weekday)
        assert response.status_code == 400
        assert "fechas pasadas" in response.json()["error"]["message"].lower()


# ============================================================================
# CASO 3: manager puede crear turno pasado a nombre de otro usuario, con auditoría
# ============================================================================

class TestSupervisorCanBackdateForOthers:

    def test_manager_creates_past_shift_for_regular_user(
        self, client: TestClient, auth_cookies_manager: dict,
        manager_user: User, regular_user: User, past_weekday: str,
    ):
        """Manager crea turno en el pasado para otro usuario -> 201 y queda auditado."""
        response = _create_shift(
            client, auth_cookies_manager, past_weekday,
            target_user_id=regular_user.id,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["user_id"] == regular_user.id
        assert body["date"] == past_weekday
        # Auditoría: debe quedar registrado quién lo cargó en nombre de quién
        assert body["modified_by_user_id"] == manager_user.id

    def test_admin_creates_past_shift_for_self(
        self, client: TestClient, auth_cookies_admin: dict,
        admin_user: User, past_weekday: str,
    ):
        """Admin backdatea un turno propio -> 201, y NO debe marcarse modified_by
        (no tiene sentido auditar "se modificó a sí mismo")."""
        response = _create_shift(client, auth_cookies_admin, past_weekday)
        assert response.status_code == 201
        body = response.json()
        assert body["user_id"] == admin_user.id
        assert body["modified_by_user_id"] is None


# ============================================================================
# CASO 4: la capacidad de turno early se sigue respetando aunque sea backdating
# ============================================================================

class TestEarlyCapacityStillEnforcedWhenBackdating:

    def test_second_early_shift_same_past_day_conflicts(
        self, client: TestClient, auth_cookies_admin: dict,
        auth_cookies_manager: dict, admin_user: User, manager_user: User,
        past_weekday: str,
    ):
        """Dos turnos 'early' el mismo día pasado -> el segundo debe fallar con 409,
        sin importar que ambos los cargue un supervisor."""
        first = client.post(
            f"{BASE}/",
            json={"date": past_weekday, "shift_type": "early", "notes": "primero"},
            cookies=auth_cookies_admin,
            headers=CSRF_HEADERS,
        )
        assert first.status_code == 201

        second = client.post(
            f"{BASE}/",
            json={
                "date": past_weekday, "shift_type": "early", "notes": "segundo",
                "target_user_id": manager_user.id,
            },
            cookies=auth_cookies_manager,
            headers=CSRF_HEADERS,
        )
        assert second.status_code == 409


# ============================================================================
# CASO 5: no se puede asignar dos turnos el mismo día al mismo usuario (backdating)
# ============================================================================

class TestDuplicateAssignmentStillEnforcedWhenBackdating:

    def test_duplicate_shift_same_user_same_past_day(
        self, client: TestClient, auth_cookies_admin: dict,
        regular_user: User, past_weekday: str,
    ):
        first = _create_shift(
            client, auth_cookies_admin, past_weekday,
            target_user_id=regular_user.id, notes="primero",
        )
        assert first.status_code == 201

        second = _create_shift(
            client, auth_cookies_admin, past_weekday,
            target_user_id=regular_user.id, notes="segundo",
        )
        assert second.status_code == 409


# ============================================================================
# CASO 6: update (PATCH) también respeta el bypass — solo para supervisores
# ============================================================================

class TestUpdateShiftDateBypass:

    def test_regular_user_cannot_move_own_shift_to_past(
        self, client: TestClient, auth_cookies_user: dict,
        regular_user: User, future_weekday: str, past_weekday: str,
    ):
        """Un user mueve un turno propio (futuro, dentro del deadline) hacia el pasado -> 400."""
        create_resp = _create_shift(client, auth_cookies_user, future_weekday)
        assert create_resp.status_code == 201
        shift_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"{BASE}/{shift_id}",
            json={"date": past_weekday},
            cookies=auth_cookies_user,
            headers=CSRF_HEADERS,
        )
        assert patch_resp.status_code == 400

    def test_manager_can_move_shift_to_past(
        self, client: TestClient, auth_cookies_admin: dict, auth_cookies_manager: dict,
        manager_user: User, admin_user: User, future_weekday: str, past_weekday: str,
    ):
        """Admin crea un turno futuro para el manager; el manager lo mueve al pasado -> 200."""
        create_resp = _create_shift(
            client, auth_cookies_admin, future_weekday,
            target_user_id=manager_user.id,
        )
        assert create_resp.status_code == 201
        shift_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"{BASE}/{shift_id}",
            json={"date": past_weekday},
            cookies=auth_cookies_manager,
            headers=CSRF_HEADERS,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["date"] == past_weekday


# ============================================================================
# BONUS: la regla de "no hay early los findes" sigue activa incluso para supervisores
# ============================================================================

class TestWeekendEarlyRuleAppliesEvenToSupervisors:

    def test_admin_cannot_create_early_shift_on_weekend(
        self, client: TestClient, auth_cookies_admin: dict,
    ):
        """Confirma que el bypass de fecha pasada NO se coló también en la regla
        de fin de semana para turnos early — son dos validaciones independientes."""
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=days_until_saturday or 7)

        response = client.post(
            f"{BASE}/",
            json={"date": saturday.isoformat(), "shift_type": "early", "notes": "no debería crearse"},
            cookies=auth_cookies_admin,
            headers=CSRF_HEADERS,
        )
        assert response.status_code == 400
        assert "fines de semana" in response.json()["error"]["message"].lower()