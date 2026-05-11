from app.models import User  # noqa: F401  (garante registro no metadata)
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings


def _build_engine():
    """
    Monta o engine certo pro DATABASE_URL configurado.

    - sqlite: precisa de check_same_thread=False porque o FastAPI roda em
      múltiplas threads e a Session é passada por Depends. echo=True ajuda
      em dev.
    - postgres (Supabase): NÃO aceita check_same_thread. Usa pool_pre_ping
      pra detectar conexões mortas (importante em hosts gerenciados que
      derrubam idle connections). echo=False pra não vazar SQL com tokens
      nos logs de prod.
    """
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        return create_engine(
            url,
            echo=True,
            connect_args={"check_same_thread": False},
        )

    # Postgres / Supabase
    # Se um dia migrar pro pooler em transaction mode (porta 6543), adicionar:
    #   connect_args={"prepare_threshold": None}
    # pra desligar prepared statements que o pgbouncer não suporta nesse modo.
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


engine = _build_engine()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
