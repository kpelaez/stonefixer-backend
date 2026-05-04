import requests
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"

# 1. Login (CAMBIA estas credenciales por las tuyas)
print("1️⃣ Login...")
login_response = requests.post(
    f"{BASE_URL}/token",
    data={
        "username": "kevin@omnimedica.com",  # ← CAMBIA ESTO
        "password": "Kepe1702"              # ← CAMBIA ESTO
    }
)

if login_response.status_code != 200:
    print(f"❌ Error en login: {login_response.status_code}")
    print(login_response.json())
    exit()

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"✅ Token obtenido: {token[:20]}...")

# 2. Crear turno para mañana
print("\n2️⃣ Crear turno early para pasadomañana...")
tomorrow = (date.today() + timedelta(days=2)).isoformat()

create_response = requests.post(
    f"{BASE_URL}/api/shift-schedules",
    json={
        "date": tomorrow,
        "shift_type": "early",
        "notes": "Test desde Python"
    },
    headers=headers
)

print(f"Status: {create_response.status_code}")
if create_response.status_code == 201:
    print("✅ Turno creado:")
    print(create_response.json())
    shift_id = create_response.json()["id"]
else:
    print(f"❌ Error: {create_response.json()}")
    shift_id = None

# 3. Listar turnos del mes
print("\n3️⃣ Listar turnos del mes...")
start = date.today().isoformat()
end = (date.today() + timedelta(days=30)).isoformat()

list_response = requests.get(
    f"{BASE_URL}/api/shift-schedules",
    params={
        "start_date": start,
        "end_date": end
    },
    headers=headers
)

print(f"Status: {list_response.status_code}")
if list_response.status_code == 200:
    shifts = list_response.json()
    print(f"✅ Encontrados {len(shifts)} turnos:")
    for shift in shifts:
        print(f"  - {shift['date']} | {shift['shift_type']} | {shift['user_full_name']}")
else:
    print(f"❌ Error: {list_response.json()}")

# 4. Estadísticas
print("\n4️⃣ Estadísticas del mes...")
stats_response = requests.get(
    f"{BASE_URL}/api/shift-schedules/stats",
    params={
        "start_date": start,
        "end_date": end
    },
    headers=headers
)

print(f"Status: {stats_response.status_code}")
if stats_response.status_code == 200:
    stats = stats_response.json()
    print(f"✅ Estadísticas de {len(stats)} usuarios:")
    for stat in stats:
        print(f"  - {stat['user_full_name']}: {stat['total_shifts']} turnos ({stat['percentage_of_total']:.1f}%)")
else:
    print(f"❌ Error: {stats_response.json()}")

# 5. Alertas
print("\n5️⃣ Alertas de turnos sin asignar...")
alerts_response = requests.get(
    f"{BASE_URL}/api/shift-schedules/alerts",
    headers=headers
)

print(f"Status: {alerts_response.status_code}")
if alerts_response.status_code == 200:
    alerts_data = alerts_response.json()
    print(f"✅ {alerts_data['count']} alertas:")
    for alert in alerts_data['alerts']:
        print(f"  {alert['severity'].upper()}: {alert['message']}")
else:
    print(f"❌ Error: {alerts_response.json()}")

# 6. Actualizar turno (si se creó)
if shift_id:
    print(f"\n6️⃣ Actualizar turno {shift_id}...")
    update_response = requests.patch(
        f"{BASE_URL}/api/shift-schedules/{shift_id}",
        json={
            "notes": "Nota actualizada desde test"
        },
        headers=headers
    )
    
    print(f"Status: {update_response.status_code}")
    if update_response.status_code == 200:
        print("✅ Turno actualizado")
    else:
        print(f"❌ Error: {update_response.json()}")

print("\n" + "="*50)
print("🎉 TEST COMPLETADO")
print("="*50)