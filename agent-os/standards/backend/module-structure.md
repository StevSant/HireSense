# Module Layer Structure

Every domain module follows this layout:

```
module_name/
  api/
    __init__.py
    routes.py        # FastAPI router + endpoints
    schemas.py       # Request/response Pydantic models
    dependencies.py  # Depends() functions (read app.state)
    provider.py      # Builds and caches service instances
  domain/
    __init__.py
    models.py        # Domain/ORM models, value objects
    services.py      # Business logic / orchestrators
  infrastructure/
    __init__.py
    repository.py    # Database access
  ports/
    __init__.py
    *.py             # Protocol interfaces for the module
  __init__.py
```

## Rules

- All four layers (`api/`, `domain/`, `infrastructure/`, `ports/`) are required — even if infrastructure/ or ports/ only has `__init__.py`
- One class or function per file
- `ports/` defines Protocol interfaces that adapters implement
- `domain/` never imports from `api/` or `infrastructure/`
- `api/` depends on `domain/` and `ports/`, never on `infrastructure/` directly
- `infrastructure/` implements `ports/` interfaces
- Cross-module imports go through `kernel/contracts/`
