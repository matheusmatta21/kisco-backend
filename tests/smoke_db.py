"""
Smoke test de conexao com o banco configurado em DATABASE_URL.

Funciona pra SQLite (dev) e Postgres/Supabase (prod). Imprime a versao
do servidor e quais tabelas existem.

Uso:
    uv run python tests/smoke_db.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Se .env.prod existir, carrega ANTES de importar app.config — assim da
# pra testar a conexao Supabase sem mexer no .env de dev.
_env_prod = ROOT / ".env.prod"
if _env_prod.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_prod, override=True)
    print(f"[smoke_db] carregando vars de {_env_prod.name}")

from sqlalchemy import inspect, text
from sqlmodel import Session

from app.config import settings
from app.db import engine


def main():
    print("=" * 60)
    print("SMOKE DB — conexao")
    print("=" * 60)

    url = settings.DATABASE_URL
    masked = _mask_password(url)
    print(f"  DATABASE_URL: {masked}")
    print(f"  Driver:       {engine.dialect.name}")
    print()

    with Session(engine) as session:
        if engine.dialect.name == "sqlite":
            row = session.exec(text("select sqlite_version()")).first()
            print(f"  SQLite version: {row[0]}")
        else:
            row = session.exec(text("select version()")).first()
            print(f"  Server version: {row[0]}")

    print()
    print("=" * 60)
    print("TABELAS EXISTENTES")
    print("=" * 60)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    if not tables:
        print("  (nenhuma — rode o app uma vez pra disparar create_db_and_tables)")
    else:
        for t in tables:
            cols = [c["name"] for c in inspector.get_columns(t)]
            print(f"  - {t}  ({', '.join(cols)})")

    print()
    print("OK")


def _mask_password(url: str) -> str:
    """Esconde a senha no print pra nao vazar em log."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _pw = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return url


if __name__ == "__main__":
    main()
