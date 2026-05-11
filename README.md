# KISCO Backend

Backend da homepage **KISCO** — uma página privada onde 6 amigos veem em tempo real o que cada um anda ouvindo do álbum *Kiss All The Time. Disco, Occasionally.* do Harry Styles, com ranking de tops, estatísticas semanais e mensais.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=white)
![Postgres](https://img.shields.io/badge/PostgreSQL-Supabase-336791?logo=postgresql&logoColor=white)
![Fly.io](https://img.shields.io/badge/Deploy-Fly.io-7B3FE4?logo=flydotio&logoColor=white)
![License](https://img.shields.io/badge/license-personal-lightgrey)

---

## Live

| Recurso | URL |
|---|---|
| API base | https://kisco-backend-api.fly.dev |
| Swagger docs | https://kisco-backend-api.fly.dev/docs |
| Health check | https://kisco-backend-api.fly.dev/health |
| Frontend | *(em deploy)* |

---

## O que ele faz

- **OAuth multi-provider**: login via Spotify (Authorization Code Flow) e via Last.fm (web auth) — cada usuário escolhe seu provider.
- **Polling persistente**: a cada 15 minutos, busca os scrobbles/recently-played de cada usuário, filtra pelo álbum-alvo, e grava em banco.
- **Dedup automático**: UNIQUE constraint composta garante que polls duplicados não geram linhas duplicadas.
- **Estatísticas agregadas cross-provider**: top tracks, top listeners e rankings combinam Spotify e Last.fm via chave normalizada de faixa.
- **Janelas temporais**: semana (7d), mês (30d), ou total (desde o primeiro play registrado).

---

## Stack

- **Python 3.11+** com **FastAPI** e **uvicorn**
- **SQLModel** (SQLAlchemy 2.0 + Pydantic v2) para ORM
- **Postgres** (Supabase) em produção, **SQLite** em dev — alternados via `DATABASE_URL`
- **httpx** assíncrono para Spotify Web API e Last.fm API
- **itsdangerous** para sessões assinadas por cookie
- **uv** (Astral) como gerenciador de dependências
- Deploy em **Fly.io** (região `gru`, São Paulo)

---

## Arquitetura

REST API monolítica em camadas, async, com OAuth e frontend desacoplado.

```
app/
├── config.py              # Settings tipadas (pydantic-settings v2)
├── constants.py           # Album-alvo, URLs, scopes, intervalos
├── db.py                  # Engine condicional sqlite/postgres
├── models.py              # User (composite PK), Play (com índices)
├── main.py                # FastAPI + lifespan + poller background
├── spotify_adapter.py     # HTTP client puro do Spotify
├── spotify_for_user.py    # Service: refresh + retry + DB
├── lastfm_adapter.py      # HTTP client puro do Last.fm
├── lastfm_for_user.py     # Service do Last.fm com persistência
├── play_normalizer.py     # Spotify/Last.fm payload → Play
├── poller.py              # Scheduler 15min, idempotente
├── providers/             # Abstração common base + dois providers
└── routes/
    ├── auth.py            # /auth/spotify, /auth/lastfm e callbacks
    ├── users.py           # /users (lista com últimas tocadas)
    └── stats.py           # /stats/* (agregados)
```

**Princípios:**
- Adapters (`*_adapter.py`) são *burros* — só HTTP, não tocam no banco.
- Services (`*_for_user.py`) orquestram banco + adapter + token refresh.
- Routes só HTTP request/response — sem lógica de negócio.

---

## Endpoints

### Auth

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/auth/spotify` | Inicia OAuth Spotify |
| `GET` | `/auth/callback` | Callback Spotify |
| `GET` | `/auth/lastfm` | Inicia auth Last.fm |
| `GET` | `/auth/lastfm/callback` | Callback Last.fm |
| `GET` | `/auth/me` | Usuário da sessão atual |

### Users

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/users` | Todos os usuários com últimas tocadas do álbum |

### Stats

Todos aceitam `?period=week|month|total`. Listas aceitam `&limit=1-50` (default 10).

| Método | Rota | Retorno |
|---|---|---|
| `GET` | `/stats/top-listener` | Quem mais ouviu no período |
| `GET` | `/stats/top-track` | Faixa mais tocada no período |
| `GET` | `/stats/top-tracks` | Top N faixas (cross-provider) |
| `GET` | `/stats/ranking` | Ranking de ouvintes |

Documentação interativa completa em [`/docs`](https://kisco-backend-api.fly.dev/docs).

---

## Rodando localmente

### Pré-requisitos

- [`uv`](https://docs.astral.sh/uv/) instalado
- Python 3.11+
- App registrado no [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) com redirect URI `http://127.0.0.1:8000/auth/callback`
- App registrado no [Last.fm API](https://www.last.fm/api/account/create) com callback `http://127.0.0.1:8000/auth/lastfm/callback`

### Setup

```bash
# Clona
git clone https://github.com/SEU_USUARIO/kisco-backend.git
cd kisco-backend

# Instala deps no virtualenv local
uv sync

# Configura ambiente
cp .env.example .env
# Edita .env com seus credenciais

# Sobe o servidor (cria o SQLite no primeiro boot)
uv run uvicorn app.main:app --reload
```

API disponível em `http://127.0.0.1:8000`. Swagger em `/docs`.

### Variáveis de ambiente

Todas obrigatórias menos a do banco:

```bash
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/auth/callback

LASTFM_API_KEY=...
LASTFM_SHARED_SECRET=...
LASTFM_REDIRECT_URI=http://127.0.0.1:8000/auth/lastfm/callback

FRONTEND_URL=http://localhost:3000
SESSION_SECRET=string-aleatoria-de-32-bytes

# Opcional. Default: SQLite local.
DATABASE_URL=sqlite:///./kisco.db
```

---

## Testes manuais

A pasta `tests/` contém smoke tests independentes:

```bash
uv run python tests/smoke_db.py          # Valida conexão com banco
uv run python tests/init_db.py           # Cria tabelas
uv run python tests/smoke_lastfm.py rj   # Testa Last.fm API com user público
uv run python tests/smoke_poller.py      # Roda poller 2x (testa dedup)
uv run python tests/list_users.py        # Lista users do banco
```

Se existir `.env.prod`, os smokes carregam ele automaticamente — útil pra testar contra Supabase sem mexer no `.env` de dev.

---

## Deploy

### Backend (Fly.io)

```bash
fly deploy
```

Config em `fly.toml`. Variáveis sensíveis via `flyctl secrets set` — nunca commitadas.

Build via `Dockerfile` (multi-stage com `uv` pra cache eficiente de deps).

### Banco (Supabase)

Postgres gerenciado, plano free. Connection string vai pro secret `DATABASE_URL` do Fly. Schema é criado no primeiro startup via `SQLModel.metadata.create_all`.

---

## Por que essas escolhas

- **Composite PK `(provider, provider_user_id)`** em `User` → permite que o mesmo humano apareça duas vezes (uma como Spotify, outra como Last.fm) sem precisar de matching manual.
- **`track_key` normalizada** (`f"{first_artist}::{track_name}".casefold()`) → mesma faixa de providers diferentes vira a mesma chave nas agregações.
- **Poller assíncrono ao invés de webhook** → Spotify não tem webhook de "now playing", e Last.fm tampouco é confiável. Polling resolve sem dependência externa.
- **UNIQUE constraint + try/except IntegrityError** → idempotência sem precisar de UPSERT (que precisaria de dialect-specific SQL).
- **SQLite em dev, Postgres em prod** → onboarding instantâneo, sem precisar de Docker local pra desenvolver.

---

## Status

Projeto pessoal, em uso ativo por 6 amigos. Não recebe contribuições externas, mas o código é aberto pra referência. Issues e estrelas bem-vindas.

---

## Documentação adicional

- [`SPOTIFY_API.md`](SPOTIFY_API.md) — referência detalhada da Spotify Web API usada
- [`LASTFM_INTEGRATION.md`](LASTFM_INTEGRATION.md) — guia da integração Last.fm

---

Feito por [@matheusmatta21](https://github.com/matheusmatta21).
