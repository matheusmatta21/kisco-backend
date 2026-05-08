# Last.fm Integration — Documentação de Implementação

Plano completo pra adicionar **login via Last.fm** como segunda opção de autenticação ao lado do Spotify, mantendo a homepage do KISCO funcional pra users dos dois ecossistemas (incluindo, indiretamente, users de Apple Music que façam scrobbling pro Last.fm).

> **Status:** planejamento. Nada implementado ainda.
> **Pré-requisito de leitura:** `CLAUDE.md`, `SPOTIFY_API.md`, e `BACKEND_ROADMAP.md` (no repo do frontend).

---

## Sumário

1. [Por que Last.fm](#1-por-que-lastfm)
2. [Diferenças vs Spotify (resumo)](#2-diferenças-vs-spotify-resumo)
3. [Pré-requisitos externos](#3-pré-requisitos-externos)
4. [Fluxo de autenticação Last.fm](#4-fluxo-de-autenticação-lastfm)
5. [Endpoints relevantes da API](#5-endpoints-relevantes-da-api)
6. [Assinatura de requests (`api_sig`)](#6-assinatura-de-requests-api_sig)
7. [Mudanças no projeto](#7-mudanças-no-projeto)
8. [Filtro por álbum no Last.fm](#8-filtro-por-álbum-no-lastfm)
9. [Edge cases](#9-edge-cases)
10. [Passo a passo de implementação](#10-passo-a-passo-de-implementação)
11. [Checklist de testes](#11-checklist-de-testes)
12. [Referências](#12-referências)

---

## 1. Por que Last.fm

- **Apple Music API direta custa US$ 99/ano** (Apple Developer Program). Inviável pra um app de 6 amigos.
- **Last.fm API é grátis**, sem rate limit publicado pra uso normal.
- **Cobre Apple Music indiretamente:** users de Apple Music podem ativar scrobbling via apps como Marvis, NepTunes, Soor, Marvis Pro ou plugins de scrobbling. O backend do KISCO lê o histórico do Last.fm sem se importar de qual app veio.
- **Cobre também Tidal, YouTube Music, Deezer, Plex** — qualquer player que tenha integração de scrobbling.
- **Session keys do Last.fm não expiram** — sem complexidade de refresh token.

**Tradeoff:** Last.fm é um intermediário. O dado tem latência (alguns segundos a minutos) e depende do user ter scrobbling ativo. Não é "Apple Music nativo".

---

## 2. Diferenças vs Spotify (resumo)

| | Spotify | Last.fm |
|---|---|---|
| Fluxo de auth | OAuth 2.0 Authorization Code | Last.fm Web Auth (token → sessão) |
| Refresh token | Sim, expira em 1h | **Não. Session key é permanente.** |
| Onde roda o auth | Backend (callback HTTP) | Backend (callback HTTP) |
| Custo | Grátis | Grátis |
| Credenciais | `client_id` + `client_secret` | `api_key` + `shared_secret` |
| Identificador do user | `spotify_id` (string opaca) | `username` (handle público do Last.fm) |
| Assinatura de requests | Não (só Bearer token) | **Sim (MD5 dos params + secret)** em chamadas autenticadas |
| Recently played | `GET /v1/me/player/recently-played` | `user.getRecentTracks` |
| Filtro por álbum | Por `track.album.id` (Spotify ID) | Por **nome** do álbum ou MBID |

---

## 3. Pré-requisitos externos

### 3.1. Criar API Account no Last.fm

1. Login com qualquer conta Last.fm em https://www.last.fm/api/account/create
2. Preencher:
   - **Application name:** `KISCO`
   - **Application description:** "Homepage that shows what 6 friends are listening to from a specific album."
   - **Application homepage:** `https://kisco.facedoor.solutions` (ou o domínio final)
   - **Callback URL:** `http://127.0.0.1:8000/auth/lastfm/callback` (dev). Em prod, trocar pelo domínio real.
3. Submit. A página seguinte mostra:
   - **API Key** (público — vai pro frontend e logs sem problema)
   - **Shared Secret** (privado — só backend, NUNCA versionado)

### 3.2. Decisão de redirect URI

- Last.fm aceita `localhost` *e* `127.0.0.1` no callback de dev — diferente do Spotify, que exige `127.0.0.1`.
- Pra consistência com o que já existe no projeto, **usar `127.0.0.1:8000`** também aqui.

### 3.3. Variáveis de ambiente novas

Adicionar ao `.env`:

```env
LASTFM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LASTFM_SHARED_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LASTFM_REDIRECT_URI=http://127.0.0.1:8000/auth/lastfm/callback
```

E atualizar `.env.example` (sem valores reais).

---

## 4. Fluxo de autenticação Last.fm

Last.fm chama isso de **"Web Application Authentication"**. Documentação oficial: https://www.last.fm/api/webauth

### 4.1. Diagrama

```
[Frontend]                [Backend]                 [Last.fm]
    |                        |                          |
    |-- click "Login Last.fm"|                          |
    |----------------------->|                          |
    |                        |-- redirect 302 --------->|
    |                        |   www.last.fm/api/auth/  |
    |                        |   ?api_key=X&cb=Y        |
    |                        |                          |
    |                        |       user autoriza      |
    |                        |                          |
    |<--------- 302 redirect ---------------------------|
    |  callback_url?token=ABC                           |
    |                        |                          |
    |-- GET /auth/lastfm/    |                          |
    |   callback?token=ABC ->|                          |
    |                        |-- POST auth.getSession ->|
    |                        |   (assinado)             |
    |                        |<-- session_key + name ---|
    |                        |                          |
    |                        |-- upsert User no DB      |
    |                        |-- set cookie session     |
    |<-- 302 redirect FRONTEND_URL                       |
```

### 4.2. Passo 1 — Iniciar auth (`GET /auth/lastfm`)

Backend monta a URL e redireciona:

```
http://www.last.fm/api/auth/?api_key=<API_KEY>&cb=<REDIRECT_URI>
```

> **Nota:** Last.fm **não tem campo `state`** no fluxo padrão (diferente de OAuth). Se quiser proteção CSRF, codar `state` dentro do `cb` (ex: `cb=...&kisco_state=xxx`) ou usar cookie HttpOnly assinado com `itsdangerous` antes do redirect e validar na callback.

### 4.3. Passo 2 — Callback recebe `token`

Last.fm redireciona o user de volta com `?token=<auth_token>` na query string.

> Esse `token` é **temporário**, válido por 60 minutos, e só pode ser trocado uma vez por uma session key.

### 4.4. Passo 3 — Trocar `token` por `session_key`

Backend faz `GET ws.audioscrobbler.com/2.0/` com:

| Param | Valor |
|---|---|
| `method` | `auth.getSession` |
| `api_key` | sua API key |
| `token` | o token recebido na callback |
| `api_sig` | MD5 dos params (ver §6) |
| `format` | `json` |

Resposta:

```json
{
  "session": {
    "name": "username_lastfm",
    "key": "d580d57f32848f5dcf574d1ce18d78b2",
    "subscriber": 0
  }
}
```

- **`name`** → handle público do Last.fm (`username`).
- **`key`** → session key permanente. Salvar no DB. Usar em todas as chamadas autenticadas futuras.
- **`subscriber`** → `1` se for assinante Last.fm Pro. Não relevante pro KISCO.

### 4.5. Passo 4 — Persistir e redirecionar

- Upsert no DB (modelo `User` com `provider="lastfm"`, ver §7).
- Set cookie de sessão (mesmo esquema do Spotify).
- 302 redirect pro `FRONTEND_URL`.

---

## 5. Endpoints relevantes da API

Base URL: `https://ws.audioscrobbler.com/2.0/`
Todos os requests são GET com params na query string. Adicionar `&format=json` em todos.

### 5.1. `auth.getSession` (autenticação)

Trocar `token` por `session_key`. Ver §4.4. **Requer assinatura.**

### 5.2. `user.getRecentTracks` (uso principal do KISCO)

Pega histórico de scrobbles. **Não requer assinatura nem session key** se o profile for público — basta `api_key` + `user`.

| Param | Obrigatório | Descrição |
|---|---|---|
| `method` | sim | `user.getRecentTracks` |
| `user` | sim | username do Last.fm |
| `api_key` | sim | sua API key |
| `limit` | não | default 50, max 200 |
| `page` | não | default 1 |
| `from` | não | unix timestamp (UTC) — mostrar scrobbles desde |
| `to` | não | unix timestamp (UTC) — mostrar scrobbles até |
| `extended` | não | `1` retorna info extra (loved, image bigger, artist mbid) |
| `format` | não | `json` |

Resposta (resumida):

```json
{
  "recenttracks": {
    "track": [
      {
        "artist": { "#text": "The Beatles", "mbid": "..." },
        "album": { "#text": "Abbey Road", "mbid": "..." },
        "name": "Come Together",
        "mbid": "...",
        "url": "https://www.last.fm/music/...",
        "image": [
          { "size": "small", "#text": "..." },
          { "size": "medium", "#text": "..." },
          { "size": "large", "#text": "..." },
          { "size": "extralarge", "#text": "..." }
        ],
        "date": { "uts": "1699000000", "#text": "01 Nov 2023, 12:00" },
        "@attr": { "nowplaying": "true" }
      }
    ],
    "@attr": {
      "user": "username",
      "totalPages": "1234",
      "page": "1",
      "perPage": "50",
      "total": "61700"
    }
  }
}
```

**Atenção:**
- Se `@attr.nowplaying === "true"` no track, é o que está tocando agora — **não tem `date.uts`**.
- Tracks sem `mbid` são comuns (scrobbling de fontes que não preencheram).
- Imagens têm 4 tamanhos: `small`, `medium`, `large`, `extralarge`.

### 5.3. `user.getInfo` (opcional — pegar avatar/display name)

```
?method=user.getInfo&user=<name>&api_key=<KEY>&format=json
```

Resposta tem `realname`, `image`, `country`, `playcount`. Útil pra preencher `display_name` e `avatar_url` no `User`.

### 5.4. `track.getInfo` (opcional — info detalhada de uma track)

Útil se quiser exibir duração ou MBID consistente. Ver §8 sobre filtro por álbum.

---

## 6. Assinatura de requests (`api_sig`)

Algumas chamadas (incluindo `auth.getSession`) exigem `api_sig`. Algoritmo:

1. **Pegar todos os params da chamada**, EXCETO `format` e `callback`.
2. **Ordenar alfabeticamente por nome do parâmetro.**
3. **Concatenar como `name1value1name2value2...`** (sem separador, sem `=`, sem `&`).
4. **Append `shared_secret`** ao final da string.
5. **MD5 hash** da string resultante (lowercase hex).

### Exemplo

Params:
```
api_key   = abc123
method    = auth.getSession
token     = xyz789
```

String concatenada (alfabética):
```
api_keyabc123methodauth.getSessiontokenxyz789
```

Append shared_secret (`mysecret`):
```
api_keyabc123methodauth.getSessiontokenxyz789mysecret
```

MD5:
```
1f3870be274f6c49b3e31a0c6728957f
```

Adicionar `api_sig=1f3870be274f6c49b3e31a0c6728957f` à request final (e o `format=json` *depois* de calcular).

### Implementação Python

```python
import hashlib

def sign_lastfm_params(params: dict[str, str], shared_secret: str) -> str:
    """Calcula api_sig conforme spec do Last.fm."""
    filtered = {k: v for k, v in params.items() if k not in ("format", "callback")}
    concat = "".join(f"{k}{filtered[k]}" for k in sorted(filtered))
    concat += shared_secret
    return hashlib.md5(concat.encode("utf-8")).hexdigest()
```

---

## 7. Mudanças no projeto

### 7.1. Estrutura final

```
app/
├── config.py                  # + LASTFM_API_KEY, LASTFM_SHARED_SECRET, LASTFM_REDIRECT_URI
├── constants.py               # + URLs/limits Last.fm
├── db.py                      # sem mudança
├── models.py                  # REFATORAR — multi-provider (ver §7.4)
├── main.py                    # include router lastfm
├── spotify_adapter.py         # sem mudança
├── spotify_for_user.py        # sem mudança (mas considerar abstração — §7.7)
├── lastfm_adapter.py          # NOVO — cliente HTTP "burro"
├── lastfm_for_user.py         # NOVO — service layer
└── routes/
    ├── auth.py                # + /auth/lastfm, /auth/lastfm/callback
    └── users.py               # ajustar pra ler de qualquer provider
```

### 7.2. `app/config.py` — adicionar

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REDIRECT_URI: str

    LASTFM_API_KEY: str
    LASTFM_SHARED_SECRET: str
    LASTFM_REDIRECT_URI: str

    FRONTEND_URL: str
    DATABASE_URL: str
    SESSION_SECRET: str
```

### 7.3. `app/constants.py` — adicionar

```python
# Last.fm
LASTFM_AUTH_URL = "http://www.last.fm/api/auth/"
LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
LASTFM_RECENT_MAX_LIMIT = 200

# Filtro por álbum (KISCO)
ALBUM_NAME_LASTFM = "Kiss All The Time"      # Disco Ocasionally
ARTIST_NAME_LASTFM = "Disco Ocasionally"     # confirmar grafia exata como aparece no scrobble
```

> **Nota:** Last.fm não tem ID estável universal por álbum. Filtragem é por nome (case-insensitive, normalizado). Ver §8.

### 7.4. `app/models.py` — refatoração multi-provider

**Opção A — recomendada: tabela única com discriminador `provider`.**

```python
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from typing import Literal

Provider = Literal["spotify", "lastfm"]


class User(SQLModel, table=True):
    # PK composta: (provider, provider_user_id)
    provider: Provider = Field(primary_key=True)
    provider_user_id: str = Field(primary_key=True)  # spotify_id ou lastfm username

    display_name: str
    avatar_url: str | None = None

    # Spotify-only (nullable)
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None

    # Last.fm-only (nullable)
    lastfm_session_key: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

**Opção B — tabela `User` + tabela `Provider` separada** (1:N, user pode plugar Spotify *e* Last.fm). Mais limpo, mais setup. Adiar pra v2 se necessário.

**Recomendação:** ir de Opção A. Cada user escolhe um provider; trocar = re-login.

**Migração:** SQLite local + sem Alembic = drop + recreate. Avisar usuários (os 6 amigos) que vão precisar re-logar uma vez.

### 7.5. `app/lastfm_adapter.py` — cliente burro

Espelha `spotify_adapter.py`. Funções principais:

```python
import hashlib
import httpx
from app.config import settings
from app.constants import LASTFM_API_BASE


def _sign(params: dict[str, str]) -> str:
    filtered = {k: v for k, v in params.items() if k not in ("format", "callback")}
    concat = "".join(f"{k}{filtered[k]}" for k in sorted(filtered))
    concat += settings.LASTFM_SHARED_SECRET
    return hashlib.md5(concat.encode("utf-8")).hexdigest()


async def exchange_token_for_session(token: str) -> dict:
    """Troca o auth token recebido na callback por uma session key permanente."""
    params = {
        "method": "auth.getSession",
        "api_key": settings.LASTFM_API_KEY,
        "token": token,
    }
    params["api_sig"] = _sign(params)
    params["format"] = "json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        resp.raise_for_status()
        return resp.json()  # {"session": {"name": ..., "key": ..., "subscriber": ...}}


async def get_user_info(username: str) -> dict:
    params = {
        "method": "user.getInfo",
        "user": username,
        "api_key": settings.LASTFM_API_KEY,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_recent_tracks(username: str, limit: int = 50) -> dict:
    params = {
        "method": "user.getRecentTracks",
        "user": username,
        "api_key": settings.LASTFM_API_KEY,
        "limit": str(limit),
        "extended": "0",
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        resp.raise_for_status()
        return resp.json()
```

> **Importante:** Last.fm pode retornar HTTP 200 *com* corpo `{"error": <code>, "message": "..."}`. **Verificar `error` no JSON**, não confiar só no status code. Errors comuns:
> - `4` — Authentication Failed (token inválido)
> - `9` — Invalid session key
> - `10` — Invalid API key
> - `14` — Token has not been authorized
> - `15` — Token has expired
> - `16` — Service offline (retry)
> - `26` — Suspended API key
> - `29` — Rate limit exceeded

### 7.6. `app/lastfm_for_user.py` — service layer

```python
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models import User
from app import lastfm_adapter


async def upsert_user_from_session(
    db: Session,
    session_key: str,
    username: str,
) -> User:
    """Após auth.getSession, cria/atualiza o User."""
    info = await lastfm_adapter.get_user_info(username)
    user_obj = info.get("user", {})
    display_name = user_obj.get("realname") or username
    images = user_obj.get("image", [])
    avatar_url = next(
        (img["#text"] for img in images if img.get("size") == "extralarge" and img.get("#text")),
        None,
    )

    existing = db.exec(
        select(User).where(
            User.provider == "lastfm",
            User.provider_user_id == username,
        )
    ).first()

    now = datetime.now(timezone.utc)
    if existing:
        existing.lastfm_session_key = session_key
        existing.display_name = display_name
        existing.avatar_url = avatar_url
        existing.updated_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        provider="lastfm",
        provider_user_id=username,
        display_name=display_name,
        avatar_url=avatar_url,
        lastfm_session_key=session_key,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def fetch_recent_filtered(
    username: str,
    album_name: str,
    limit: int = 5,
) -> list[dict]:
    """Pega scrobbles recentes e filtra por álbum (case-insensitive)."""
    data = await lastfm_adapter.get_recent_tracks(username, limit=200)
    tracks = data.get("recenttracks", {}).get("track", [])
    target = album_name.strip().casefold()
    filtered = [
        t for t in tracks
        if t.get("album", {}).get("#text", "").strip().casefold() == target
    ]
    return filtered[:limit]
```

### 7.7. Abstração `MusicProvider` (opcional, mas recomendado)

Antes de adicionar Last.fm, considerar refatorar pra interface comum. Caso contrário, `routes/users.py` vira uma cadeia de `if user.provider == "spotify": ... elif user.provider == "lastfm": ...` que cresce a cada novo provider.

```python
# app/providers/base.py
from typing import Protocol
from app.models import User


class MusicProvider(Protocol):
    async def fetch_recent_for_album(
        self, user: User, limit: int
    ) -> list[dict]: ...


# app/providers/spotify.py — implementa MusicProvider via spotify_for_user
# app/providers/lastfm.py  — implementa MusicProvider via lastfm_for_user

PROVIDERS: dict[str, MusicProvider] = {
    "spotify": SpotifyProvider(),
    "lastfm": LastfmProvider(),
}
```

E em `routes/users.py`:

```python
provider = PROVIDERS[user.provider]
tracks = await provider.fetch_recent_for_album(user, limit=TRACKS_PER_USER)
```

### 7.8. `app/routes/auth.py` — adicionar endpoints

```python
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from app.config import settings
from app.constants import LASTFM_AUTH_URL
from app.db import get_session
from app import lastfm_adapter, lastfm_for_user

router = APIRouter(prefix="/auth")


@router.get("/lastfm")
async def lastfm_login():
    qs = urlencode({
        "api_key": settings.LASTFM_API_KEY,
        "cb": settings.LASTFM_REDIRECT_URI,
    })
    return RedirectResponse(f"{LASTFM_AUTH_URL}?{qs}", status_code=302)


@router.get("/lastfm/callback")
async def lastfm_callback(token: str, db=Depends(get_session)):
    data = await lastfm_adapter.exchange_token_for_session(token)
    if "error" in data:
        raise HTTPException(400, f"Last.fm error: {data.get('message')}")

    session = data["session"]
    session_key = session["key"]
    username = session["name"]

    user = await lastfm_for_user.upsert_user_from_session(db, session_key, username)

    response = RedirectResponse(settings.FRONTEND_URL, status_code=302)
    # Set cookie de sessão (mesmo padrão do Spotify — itsdangerous signed cookie)
    # session_id = sign(f"lastfm:{username}")
    # response.set_cookie("kisco_session", session_id, httponly=True, samesite="lax")
    return response
```

### 7.9. `app/routes/users.py` — ajustar

Iterar sobre todos os users (de qualquer provider) e dispatchar pro provider correto. Idealmente via abstração §7.7.

---

## 8. Filtro por álbum no Last.fm

### Problema

Spotify retorna `track.album.id` — string opaca, comparação direta. Last.fm retorna `track.album.#text` — string livre, escrita pelo scrobbler.

### Implicações

- "Kiss All The Time" pode aparecer como `Kiss All The Time`, `Kiss all the time`, `Kiss All The Time (Deluxe)`, etc.
- Versões deluxe/remaster de outros álbuns podem ter o mesmo título.
- Tracks sem álbum vêm com `album.#text = ""`.

### Estratégia v1

**Match case-insensitive em `album.#text` E `artist.#text`** (não basta o álbum — precisa do artista também).

```python
def matches_album(track: dict, album_name: str, artist_name: str) -> bool:
    a = track.get("album", {}).get("#text", "").strip().casefold()
    ar = track.get("artist", {}).get("#text", "").strip().casefold()
    return a == album_name.casefold() and ar == artist_name.casefold()
```

### Estratégia v2 (se necessário)

Usar **MBID** (MusicBrainz ID) quando disponível. Pegar o MBID do álbum uma vez via `album.getInfo` e comparar com `track.album.mbid`. Fallback pro nome se MBID estiver ausente.

```python
TARGET_ALBUM_MBID = "..."  # buscar uma vez via album.getInfo e hardcodar

def matches_album_v2(track: dict) -> bool:
    mbid = track.get("album", {}).get("mbid")
    if mbid and mbid == TARGET_ALBUM_MBID:
        return True
    # fallback nome+artista
    return matches_album(track, ALBUM_NAME_LASTFM, ARTIST_NAME_LASTFM)
```

---

## 9. Edge cases

### 9.1. User authoriza no Last.fm mas profile é privado

`user.getRecentTracks` retorna `error: 17 (Login: User required to be logged in)`. Solução: usar a `session_key` salva pra autenticar a chamada (adicionar `sk=<key>` + `api_sig` aos params). Implementar **só se** algum user reportar problema; default Last.fm é profile público.

### 9.2. Token na callback expirado/inválido

Last.fm retorna `error: 14` ou `15`. Mostrar página de erro e oferecer retry no `/auth/lastfm`.

### 9.3. User tenta logar com Spotify e Last.fm

Com Opção A do modelo (PK composta), seriam **dois rows distintos** no DB. Decidir produto:
- (a) Permitir e mostrar duas entradas separadas na homepage? Esquisito.
- (b) Bloquear segundo provider e exigir logout?
- (c) Linkar via email/identidade externa? Complexo, fora do escopo v1.

**Recomendação v1:** (b). Cookie de sessão guarda só um par `(provider, user_id)`. Se já tem sessão, novo login substitui.

### 9.4. Scrobble "now playing" vs scrobble passado

Tracks com `@attr.nowplaying === "true"` **não têm `date.uts`**. Se a UI ordena por timestamp, tratar nowplaying como "agora" (timestamp = `time.time()`).

### 9.5. Rate limiting

Last.fm não publica limite oficial mas histórico é "5 req/s por IP, 30 req/min". Pra 6 users com paralelismo `asyncio.gather`, irrelevante. Se ampliar, adicionar `asyncio.Semaphore(5)`.

### 9.6. Last.fm offline (`error: 16`)

Retry com backoff (1 tentativa, 1s). Se falhar, retornar lista vazia pro frontend e logar — não derrubar o endpoint inteiro.

### 9.7. User deleta a conexão no Last.fm

Last.fm não notifica revogação. Próxima chamada autenticada retorna `error: 9 (Invalid session key)`. Tratar marcando o user pra re-auth, mesma lógica do `invalid_grant` do Spotify.

### 9.8. Caracteres especiais no signature

Last.fm exige UTF-8 antes do MD5. Strings com acento (em nomes/álbuns) **não vão pro `auth.getSession`**, então na prática raro causar problema. Se for chamar métodos que aceitem queries livres, garantir `.encode("utf-8")` antes do hash.

---

## 10. Passo a passo de implementação

Seguir nessa ordem. Cada passo é um commit lógico.

### Fase 1 — Setup (sem código de produção)

- [ ] **1.1** Criar API account em https://www.last.fm/api/account/create (§3.1)
- [ ] **1.2** Salvar `API Key` e `Shared Secret` no gerenciador de senhas
- [ ] **1.3** Adicionar variáveis ao `.env` local (§3.3)
- [ ] **1.4** Atualizar `.env.example`
- [ ] **1.5** Adicionar `LASTFM_API_KEY`, `LASTFM_SHARED_SECRET`, `LASTFM_REDIRECT_URI` em `app/config.py` (§7.2)
- [ ] **1.6** Adicionar constantes em `app/constants.py` (§7.3)

### Fase 2 — Modelo de dados

- [ ] **2.1** Refatorar `app/models.py` pra Opção A (§7.4)
- [ ] **2.2** Apagar `kisco.db` local (drop + recreate no startup)
- [ ] **2.3** Atualizar todos os pontos do código que referenciam `User.spotify_id` direto pra usar `(provider, provider_user_id)`
- [ ] **2.4** Atualizar `spotify_for_user.py` pra criar `User(provider="spotify", provider_user_id=spotify_id, ...)`
- [ ] **2.5** Rodar smoke test do fluxo Spotify pra garantir que não quebrou

### Fase 3 — Cliente Last.fm (camada burra)

- [ ] **3.1** Criar `app/lastfm_adapter.py` com `_sign`, `exchange_token_for_session`, `get_user_info`, `get_recent_tracks` (§7.5)
- [ ] **3.2** Escrever teste unitário pra `_sign` com vetores conhecidos (a docs do Last.fm tem exemplos)
- [ ] **3.3** Testar `get_recent_tracks` manualmente com username público qualquer (ex: `rj` — conta de teste oficial do Last.fm)

### Fase 4 — Service layer

- [ ] **4.1** Criar `app/lastfm_for_user.py` com `upsert_user_from_session` e `fetch_recent_filtered` (§7.6)
- [ ] **4.2** Adicionar tratamento de `error` no JSON (não basta status code) (§7.5 nota)
- [ ] **4.3** Testar com user real fazendo scrobbling

### Fase 5 — Rotas de auth

- [ ] **5.1** Adicionar `/auth/lastfm` e `/auth/lastfm/callback` em `app/routes/auth.py` (§7.8)
- [ ] **5.2** Reaproveitar mecanismo de cookie/session do Spotify
- [ ] **5.3** (Opcional) Implementar CSRF state via cookie assinado com `itsdangerous` (§4.2 nota)
- [ ] **5.4** Smoke test end-to-end: clicar no botão → autorizar Last.fm → voltar → ver cookie → ver row no DB

### Fase 6 — Endpoint de users

- [ ] **6.1** (Recomendado) Refatorar pra abstração `MusicProvider` (§7.7)
- [ ] **6.2** Atualizar `app/routes/users.py` pra dispatcher por provider
- [ ] **6.3** Confirmar que `/users` retorna formato consistente independente do provider (mesmo schema de track no JSON)
- [ ] **6.4** Testar paralelismo com `asyncio.gather` misturando users de Spotify e Last.fm

### Fase 7 — Frontend (no repo `../kisco/`)

- [ ] **7.1** Adicionar botão "Login com Last.fm" ao lado de "Login com Spotify"
- [ ] **7.2** Garantir que homepage exibe corretamente users dos dois providers (mesmo card, mesmo formato)
- [ ] **7.3** Tratar avatar fallback quando Last.fm não tem imagem

### Fase 8 — Testes

- [ ] **8.1** Teste unitário `_sign` (vetor conhecido)
- [ ] **8.2** Teste de integração (mock httpx) pro fluxo de callback
- [ ] **8.3** Teste de filtro por álbum com payload real salvo (fixture)
- [ ] **8.4** Smoke test: 1 user Spotify + 1 user Last.fm, ambos aparecem em `/users`

### Fase 9 — Deploy

- [ ] **9.1** Cadastrar callback URL de produção no Last.fm dashboard
- [ ] **9.2** Configurar `LASTFM_*` vars no provedor de hosting
- [ ] **9.3** Documentar no README como os 6 amigos podem ativar scrobbling no app que usam (Apple Music → Marvis/NepTunes/Soor; Tidal/YouTube/etc → docs respectivas)

---

## 11. Checklist de testes

### Unitários

- [ ] `_sign` com params do exemplo da spec (resultado MD5 conhecido)
- [ ] `_sign` ignora `format` e `callback`
- [ ] `_sign` ordena alfabeticamente
- [ ] `matches_album` case-insensitive
- [ ] `matches_album` exige artista E álbum

### Integração (httpx mock)

- [ ] Callback com `token` válido → cria User no DB
- [ ] Callback com Last.fm respondendo `error: 14` → 400 + mensagem
- [ ] Callback com Last.fm offline (`error: 16`) → retry, depois 503
- [ ] `get_recent_tracks` parseia "now playing" sem date corretamente

### End-to-end manual

- [ ] Botão "Login Last.fm" no frontend → autoriza → volta com cookie → row no DB
- [ ] `/users` mostra tracks filtradas pelo álbum certo
- [ ] User do Spotify e user do Last.fm coexistem em `/users`
- [ ] User com 0 scrobbles do álbum: card aparece vazio (não erro)
- [ ] Re-login do mesmo Last.fm user: row é atualizado, não duplicado

---

## 12. Referências

### Last.fm

- **Docs principais:** https://www.last.fm/api
- **Web Auth Flow:** https://www.last.fm/api/webauth
- **Assinatura (`api_sig`):** https://www.last.fm/api/authspec
- **`auth.getSession`:** https://www.last.fm/api/show/auth.getSession
- **`user.getRecentTracks`:** https://www.last.fm/api/show/user.getRecentTracks
- **`user.getInfo`:** https://www.last.fm/api/show/user.getInfo
- **Códigos de erro:** https://www.last.fm/api/errorcodes

### Apple Music → Last.fm scrobbling

- **Marvis Pro (iOS/macOS):** https://appstore.com/marvispro — paga, mais robusto
- **NepTunes (macOS):** https://github.com/IneoO/NepTunes — grátis, open source
- **Soor (iOS):** https://www.soorapp.com/ — paga
- **Last.fm Desktop Scrobbler:** descontinuado oficialmente, mas forks ativos existem

### Project local

- `SPOTIFY_API.md` — referência da API Spotify (espelhar estilo aqui)
- `BACKEND_ROADMAP.md` (no repo do frontend) — plano mestre
- `CLAUDE.md` — convenções do projeto (Pydantic v2, async, redirect URI 127.0.0.1)
