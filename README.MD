# StoneFixer — Backend API

> API REST para la plataforma StoneFixer, construida con **FastAPI + SQLModel + PostgreSQL**.  
> Resuelve los gaps del ERP interno: inventario tecnológico, gestión de turnos, horas extra y KPIs de negocio.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.115+ |
| ORM / Validación | SQLModel (Pydantic v2 + SQLAlchemy) |
| Base de datos principal | PostgreSQL (Aiven) |
| Base de datos KPI | PostgreSQL (Aiven — solo lectura) |
| Migraciones | Alembic |
| Autenticación | JWT (PyJWT) |
| Seguridad | bcrypt, Fernet (cifrado DNI) |
| Rate limiting | slowapi |
| Testing | pytest + pytest-cov + httpx |
| Entorno | Python 3.11+ |

---

## Estructura del proyecto

```
stonefixer-backend/
├── app/
│   ├── api/
│   │   ├── deps.py                    # Dependencias compartidas (auth, permisos)
│   │   └── routes/
│   │       ├── auth_routes.py
│   │       ├── users_routes.py
│   │       ├── tech_assets_routes.py
│   │       ├── asset_assignments_routes.py
│   │       ├── asset_maintenances_routes.py
│   │       ├── assignment_documents_routes.py
│   │       ├── shift_schedule_routes.py
│   │       ├── overtime_routes.py
│   │       ├── business_indicators_routes.py
│   ├── core/
│   │   ├── exceptions.py              # Excepciones centralizadas
│   │   ├── dni_security.py            # Cifrado de DNI con Fernet
│   │   └── rate_limiter.py
│   ├── db/
│   │   ├── database.py                # Engine principal + get_db
│   │   ├── kpi_database.py            # Engine KPI (solo lectura)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── tech_asset.py
│   │   ├── asset_assignment.py
│   │   ├── asset_maintenance.py
│   │   ├── shift_schedule.py
│   │   ├── overtime.py
│   │   └── business_indicators.py
│   ├── services/
│   │   ├── auth.py
│   │   ├── tech_asset_service.py
│   │   ├── asset_assignment_service.py
│   │   ├── asset_maintenance_service.py
│   │   ├── shift_schedule_service.py
│   │   ├── overtime_service.py
│   │   ├── business_indicators_service.py
│   └── config.py                      # Settings con Pydantic BaseSettings
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── scripts/                           
├── main.py
├── alembic.ini
├── pytest.ini
├── requirements.txt                   # ← producción
├── requirements-dev.txt               # ← desarrollo + testing
├── .env.example
├── .gitignore
└── README.md
```

---

## Instalación

### 1. Clonar y crear entorno virtual

```bash
git clone <repo-url>
cd stonefixer-backend
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### 2. Instalar dependencias

```bash
# Producción
pip install -r requirements.txt

# Desarrollo (incluye testing, linting, etc.)
pip install -r requirements-dev.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores reales
```

Variables requeridas en `.env`:

```env
# App
APP_NAME=StoneFixer
ENVIRONMENT=development          # development | staging | production
DEBUG=true
SECRET_KEY=<genera con: openssl rand -hex 32>
LOG_LEVEL=INFO

# Base de datos principal
DATABASE_URL=postgresql://user:password@host:port/dbname

# Base de datos KPI (solo lectura)
KPI_DATABASE_URL=postgresql://user:password@host:port/kpi_dbname

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=480
ALGORITHM=HS256

# CORS
ALLOWED_ORIGINS=http://localhost:5173,https://stonefixer.mklcoders.com.ar

# Seguridad adicional
DNI_ENCRYPTION_KEY=<genera con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Swagger (protegido en producción)
SWAGGER_USERNAME=admin
SWAGGER_PASSWORD=<contraseña segura>

# Rate limiting
LOGIN_RATE_LIMIT=5/minute
READ_RATE_LIMIT=60/minute
WRITE_RATE_LIMIT=30/minute
```

### 4. Aplicar migraciones

```bash
alembic upgrade head
```

### 5. Iniciar el servidor

```bash
# Desarrollo (con auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Módulos principales

### Autenticación (`/`)
- `POST /token` — Login con OAuth2PasswordRequestForm → JWT
- `POST /register` — Registro de usuario

### Usuarios (`/api/users`)
- `GET /me` — Perfil completo con roles y permisos
- `GET /me/roles` — Roles del usuario
- Gestión de roles por admin

### Inventario Tecnológico (`/inventory`)
- CRUD de activos (`/tech-assets`)
- Asignaciones a empleados (`/assignments`)
- Mantenimientos (`/maintenances`)
- Dashboard de métricas

### Programación de Turnos (`/shift-schedules`)
- Gestión de turnos early/regular
- Validaciones de capacidad y deadlines
- Estadísticas por usuario/departamento

### Horas Extra (`/api/overtime`)
- Solicitud y aprobación de HE
- Balance por usuario
- Tipos: crédito (HE) y débito (compensatorio)

### Indicadores de Negocio (`/api/business-indicators`)
- KPIs desde base de datos de producción (solo lectura)
- Facturación vs cobranza
- Historial y health check

---

## Testing

```bash
# Todos los tests
pytest

# Solo unitarios
pytest -m unit

# Solo integración
pytest -m integration

# Con reporte de cobertura (HTML)
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Test específico
pytest tests/unit/test_tech_asset_service.py -v
```

---

## Convenciones de código

- **Formateo**: `black` + `isort`
- **Linting**: `ruff`
- **Type hints**: obligatorios en todos los servicios y rutas
- **Excepciones**: usar siempre las de `app/core/exceptions.py`
- **Logging**: usar `logger = logging.getLogger(__name__)` por módulo
- **Commits**: Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)

---

## Licencia

Uso interno — Departamento de Tecnología. Todos los derechos reservados.
