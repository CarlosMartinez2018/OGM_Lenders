# Database migrations (Alembic)

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/).
The DB URL is read from `DATABASE_URL` (via `app.core.config.settings`), so make
sure PostgreSQL is up (`docker-compose up -d postgres`) and `.env` is configured.

## Generate the initial migration

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Everyday workflow

```bash
# After changing SQLAlchemy models in app/models/database.py:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head        # apply
alembic downgrade -1        # roll back one revision
```

> Note: `init_db()` in `app/models/database.py` still creates tables and applies
> a few idempotent `ALTER TABLE ... IF NOT EXISTS` patches for backward
> compatibility. Once the initial Alembic migration is adopted as the source of
> truth, those inline patches can be removed in favor of migrations.
