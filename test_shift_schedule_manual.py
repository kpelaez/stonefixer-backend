# test_shift_schedule_manual.py
import requests
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"

# 1. Login para obtener token
def get_token():
    response = requests.post(
        f"{BASE_URL}/token",
        data={
            "username": "kevin@omnimedica.com",  # Cambia esto
            "password": "Kepe1702"             # Cambia esto
        }
    )
    return response.json()["access_token"]

token = get_token()
headers = {"Authorization": f"Bearer {token}"}

# 2. Crear turno
tomorrow = (date.today() + timedelta(days=1)).isoformat()
create_response = requests.post(
    f"{BASE_URL}/api/shift-schedules",
    json={
        "date": tomorrow,
        "shift_type": "early",
        "notes": "Test turno early"
    },
    headers=headers
)
print("✅ Crear turno:", create_response.status_code)
print(create_response.json())

# 3. Listar turnos
start = date.today().isoformat()
end = (date.today() + timedelta(days=30)).isoformat()
list_response = requests.get(
    f"{BASE_URL}/api/shift-schedules?start_date={start}&end_date={end}",
    headers=headers
)
print("\n✅ Listar turnos:", list_response.status_code)
print(list_response.json())

# 4. Estadísticas
stats_response = requests.get(
    f"{BASE_URL}/api/shift-schedules/stats?start_date={start}&end_date={end}",
    headers=headers
)
print("\n✅ Estadísticas:", stats_response.status_code)
print(stats_response.json())

# 5. Alertas
alerts_response = requests.get(
    f"{BASE_URL}/api/shift-schedules/alerts",
    headers=headers
)
print("\n✅ Alertas:", alerts_response.status_code)
print(alerts_response.json())

'''
----
'''

## ✅ CHECKLIST BACKEND
'''
[ ] Modelo creado en app/models/shift_schedule.py
[ ] __init__.py actualizado
[ ] Servicio creado en app/services/shift_schedule_service.py
[ ] Dependencia get_user_roles agregada
[ ] Rutas creadas en app/api/routes/shift_schedule_routes.py
[ ] Router registrado en main.py
[ ] holidays instalado
[ ] Migración ejecutada (alembic upgrade head)
[ ] Test manual ejecutado exitosamente
[ ] Backend funcionando sin errores
'''