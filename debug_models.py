# debug_models.py
import pkgutil, importlib, inspect, sys
import pydantic

# Ajustá este paquete al path donde están tus modelos:
import app.models as models_pkg

print("Pydantic version:", pydantic.__version__)

if int(pydantic.__version__.split('.')[0]) >= 2:
    def build_schema(m):
        return m.model_json_schema()
else:
    def build_schema(m):
        return m.schema()

errors = []
for finder, modname, ispkg in pkgutil.walk_packages(models_pkg.__path__, prefix=models_pkg.__name__ + "."):
    mod = importlib.import_module(modname)
    for name in dir(mod):
        obj = getattr(mod, name)
        if inspect.isclass(obj):
            try:
                # SQLModel hereda de BaseModel, así que esto cubre SQLModel y Pydantic models
                # filtrá según tus needs si hace falta
                build_schema(obj)
            except Exception as e:
                print(f"ERROR building schema for {modname}.{name}: {e!r}")
                errors.append((f"{modname}.{name}", e))
if not errors:
    print("OK: No model schema errors encontrados.")
else:
    print("Modelos con error:", [e[0] for e in errors])
    sys.exit(1)
