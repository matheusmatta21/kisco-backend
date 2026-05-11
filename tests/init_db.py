"""
Cria as tabelas no banco apontado por DATABASE_URL.

Se .env.prod existir, usa ele (modo Supabase). Senao, cai no .env de dev.
Idempotente: rodar de novo nao quebra nem duplica, o SQLAlchemy faz
CREATE TABLE IF NOT EXISTS internamente.

Uso:
    uv run python tests/init_db.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_env_prod = ROOT / ".env.prod"
if _env_prod.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_prod, override=True)
    print(f"[init_db] carregando vars de {_env_prod.name}")

from sqlalchemy import inspect

from app.db import create_db_and_tables, engine


def main():
    print("=" * 60)
    print(f"INIT DB — driver: {engine.dialect.name}")
    print("=" * 60)

    inspector = inspect(engine)
    before = set(inspector.get_table_names())
    print(f"  Tabelas antes:  {sorted(before) or '(nenhuma)'}")

    create_db_and_tables()

    inspector = inspect(engine)
    after = set(inspector.get_table_names())
    created = sorted(after - before)
    print(f"  Tabelas depois: {sorted(after)}")
    if created:
        print(f"  Criadas agora:  {created}")
    else:
        print("  (nenhuma tabela nova — schema ja existia)")

    print()
    print("OK")


if __name__ == "__main__":
    main()
