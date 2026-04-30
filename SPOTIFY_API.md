# Spotify Web API — Referência do Projeto Kisco

Resumo dos endpoints e fluxos da API do Spotify usados pelo backend.
Referência rápida pra implementação — não substitui a doc oficial.

Doc oficial: https://developer.spotify.com/documentation/web-api

---

## 1. Authorization Code Flow

Fluxo OAuth 2.0 que troca uma autorização do usuário por tokens de acesso.

### 1.1 Request User Authorization

`GET https://accounts.spotify.com/authorize`

Constrói URL com query params; usuário é redirecionado pra essa URL.

| Param | Obrig. | Valor |
|---|---|---|
| `client_id` | Sim | Client ID do app (vem do `.env`). |
| `response_type` | Sim | `code` |
| `redirect_uri` | Sim | URI exata cadastrada no Dashboard. Compara byte-a-byte (case, barra final, etc.). |
| `state` | Recomendado | String aleatória pra proteção contra CSRF (RFC-6749). |
| `scope` | Opcional | Lista separada por **espaço**. Se omitido, só dados públicos. |
| `show_dialog` | Opcional | `true` força reaprovação. Default `false`. |

**Resposta:** redireciona pra `redirect_uri?code=<auth_code>&state=<state>`.

### 1.2 Request an Access Token

`POST https://accounts.spotify.com/api/token`

**Headers:**

| Header | Valor |
|---|---|
| `Authorization` | `Basic <base64(client_id:client_secret)>` |
| `Content-Type` | `application/x-www-form-urlencoded` |

**Body** (form-urlencoded, NÃO JSON):

| Campo | Valor |
|---|---|
| `grant_type` | `authorization_code` |
| `code` | Code recebido em 1.1. |
| `redirect_uri` | Mesma URI do passo anterior (apenas validação, sem redirect real). |

**Response (200 OK):**
```json
{
  "access_token": "NgCXRK...MzYjw",
  "token_type": "Bearer",
  "scope": "user-read-private user-read-email",
  "expires_in": 3600,
  "refresh_token": "NgAagA...Um_SHo"
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `access_token` | string | Bearer token. Use em `Authorization: Bearer ...`. |
| `token_type` | string | Sempre `"Bearer"`. |
| `scope` | string | Scopes concedidos, separados por **espaço**. |
| `expires_in` | int | Segundos até expirar. Tipicamente `3600` (1h). |
| `refresh_token` | string | Token de longa duração pra renovação. Persistir no DB. |

> Cálculo do `token_expires_at` no projeto: `now_utc + timedelta(seconds=expires_in)`.

### 1.3 Refresh Token

Mesmo endpoint: `POST https://accounts.spotify.com/api/token`.

**Headers** (idênticos ao 1.2):

| Header | Valor |
|---|---|
| `Authorization` | `Basic <base64(client_id:client_secret)>` (obrigatório no Authorization Code Flow). |
| `Content-Type` | `application/x-www-form-urlencoded` |

**Body** (form-urlencoded):

| Campo | Obrig. | Valor |
|---|---|---|
| `grant_type` | Sim | `refresh_token` |
| `refresh_token` | Sim | O `refresh_token` salvo do passo 1.2. |
| `client_id` | Só PKCE | Não se aplica neste projeto (usamos Authorization Code Flow padrão, com Basic Auth). |

**Response (200 OK):**
```json
{
  "access_token": "BQBLuPRYBQ...BP8stIv5xr-Iwaf4l8eg",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "AQAQfyEFmJJuCvAFh...cG_m-2KTgNDaDMQqjrOa3",
  "scope": "user-read-email user-read-private"
}
```

> **Detalhe crítico (do roadmap §9.2):** o campo `refresh_token` na resposta de refresh **pode ou não** vir. Se vier, atualizar no banco; se não, manter o anterior. Nunca sobrescrever com `null`.

> Vida útil do `access_token`: 1 hora (`expires_in: 3600`). O wrapper (§10 do roadmap) deve fazer pré-check de 30s de margem.

Doc: https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens

---

## 2. Endpoints de dados

Todos em `https://api.spotify.com/v1` (host diferente do auth).

Header obrigatório em todos: `Authorization: Bearer <access_token>`.

### 2.1 Get Current User's Profile

`GET /v1/me`

**Scopes necessários no projeto:** `user-read-private`. Adicionar `user-read-email` apenas se for usar email.

**Response (200 OK):**
```json
{
  "country": "string",
  "display_name": "string",
  "email": "string",
  "explicit_content": {
    "filter_enabled": false,
    "filter_locked": false
  },
  "external_urls": { "spotify": "string" },
  "followers": { "href": "string", "total": 0 },
  "href": "string",
  "id": "string",
  "images": [
    {
      "url": "https://i.scdn.co/image/ab67...",
      "height": 300,
      "width": 300
    }
  ],
  "product": "string",
  "type": "string",
  "uri": "string"
}
```

**Mapeamento pro modelo `User` do projeto:**

| Campo da API | Campo do `User` | Notas |
|---|---|---|
| `id` | `spotify_id` (PK) | String base62, estável. |
| `display_name` | `display_name` | Pode ser `null` em contas raras (sem nome configurado) — tratar como string vazia ou fallback. |
| `images[0].url` | `avatar_url` | Array `images` pode estar vazio (`[]`) se user não tem foto. Tratar com `images[0].url if images else None`. |

**curl de teste:**
```
curl --request GET \
  --url https://api.spotify.com/v1/me \
  --header 'Authorization: Bearer <token>'
```

Doc: https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile

### 2.2 Get Recently Played Tracks

`GET /v1/me/player/recently-played`

**Scopes necessários:** `user-read-recently-played`.

**Query params:**

| Param | Tipo | Notas |
|---|---|---|
| `limit` | int | Default 20. Min 1. **Máx 50** (limite duro). |
| `after` | int (ms) | Cursor Unix timestamp. Itens depois de (sem incluir). Mutuamente exclusivo com `before`. |
| `before` | int (ms) | Cursor Unix timestamp. Itens antes de (sem incluir). |

**Não existe filtro server-side por álbum.** Filtragem por `ALBUM_ID` acontece em Python depois de receber a resposta.

**Response (200 OK):**
```json
{
  "href": "string",
  "limit": 0,
  "next": "string",
  "cursors": { "after": "string", "before": "string" },
  "total": 0,
  "items": [
    {
      "track": {
        "album": {
          "album_type": "compilation",
          "total_tracks": 9,
          "external_urls": { "spotify": "string" },
          "href": "string",
          "id": "2up3OPMp9Tb4dAKM2erWXQ",
          "images": [
            { "url": "https://i.scdn.co/image/ab67...", "height": 300, "width": 300 }
          ],
          "name": "string",
          "release_date": "1981-12",
          "release_date_precision": "year",
          "type": "album",
          "uri": "spotify:album:2up3OPMp9Tb4dAKM2erWXQ",
          "artists": [
            { "id": "string", "name": "string", "type": "artist", "uri": "string", "external_urls": {...}, "href": "string" }
          ]
        },
        "artists": [
          { "id": "string", "name": "string", "type": "artist", "uri": "string", "external_urls": {...}, "href": "string" }
        ],
        "duration_ms": 0,
        "explicit": false,
        "href": "string",
        "id": "string",
        "name": "string",
        "popularity": 0,
        "preview_url": "string",
        "track_number": 0,
        "type": "track",
        "uri": "string",
        "is_local": false
      },
      "played_at": "string",
      "context": {
        "type": "string",
        "href": "string",
        "external_urls": { "spotify": "string" },
        "uri": "string"
      }
    }
  ]
}
```

**Caminhos consumidos pelo projeto** (filtragem + montagem do card):

| Caminho | Uso |
|---|---|
| `items[].track.album.id` | Comparar com `ALBUM_ID` para filtrar. |
| `items[].track.name` | Vira `title` no card (`UserCard`). |
| `items[].track.album.images[1].url` | Vira `cover` no card. Tipicamente `images[1]` é 300x300 (`images[0]` é 640, `images[2]` é 64). Se array tiver tamanho < 3, fallback pro disponível. |

**Pseudocódigo da filtragem (vai em `spotify_for_user.py`, §10 do roadmap):**
```
filtered = [
    {"title": item["track"]["name"],
     "cover": item["track"]["album"]["images"][1]["url"]}
    for item in response["items"]
    if item["track"]["album"]["id"] == ALBUM_ID
][:5]
```

Doc: https://developer.spotify.com/documentation/web-api/reference/get-recently-played

### 2.3 Get Currently Playing Track — referência (não usado no v1)

`GET /v1/me/player/currently-playing`

Não faz parte do escopo atual; incluído pra referência futura.

**Scopes necessários:** `user-read-currently-playing` ou `user-read-playback-state`.

---

## 3. Scopes

Lista oficial agrupada por categoria. **Pedir o mínimo necessário** — mais scopes = mais fricção no consentimento.

### Scopes usados no projeto

| Scope | Categoria | Por quê |
|---|---|---|
| `user-read-private` | Users | Necessário pra `/v1/me` retornar perfil completo (display_name, images). |
| `user-read-recently-played` | Listening History | Necessário pra `/v1/me/player/recently-played`. |

### Lista completa (referência)

**Images**
- `ugc-image-upload`

**Spotify Connect**
- `user-read-playback-state`
- `user-modify-playback-state`
- `user-read-currently-playing`

**Playback**
- `app-remote-control`
- `streaming`

**Playlists**
- `playlist-read-private`
- `playlist-read-collaborative`
- `playlist-modify-private`
- `playlist-modify-public`

**Follow**
- `user-follow-modify`
- `user-follow-read`

**Listening History**
- `user-read-playback-position`
- `user-top-read`
- `user-read-recently-played` ← **usado**

**Library**
- `user-library-modify`
- `user-library-read`

**Users**
- `user-read-email`
- `user-read-private` ← **usado**
- `user-personalized`

**Open Access**
- `user-soa-link`
- `user-soa-unlink`
- `soa-manage-entitlements`
- `soa-manage-partner`
- `soa-create-partner`

Doc: https://developer.spotify.com/documentation/web-api/concepts/scopes

---

## 4. Status codes e error responses

### 4.1 Status codes da Web API

| Código | Significado | Tratamento no projeto |
|---|---|---|
| 200 | OK — body com dados. | Caso feliz. |
| 201 | Created — recurso novo. | Não usado (não criamos no Spotify). |
| 202 | Accepted — em processamento. | Não usado. |
| 204 | No Content — sucesso sem body. | Espere em alguns endpoints (não nos nossos). |
| 304 | Not Modified — usar cache. | Não usado. |
| 400 | Bad Request — sintaxe inválida (ex.: `id` mal formado). | Logar e propagar como 500 ao front (bug nosso). |
| 401 | Unauthorized — token ausente, expirado ou inválido. | Wrapper faz refresh + retry **uma vez**. Se persistir, propagar. |
| 403 | Forbidden — token válido, mas sem permissão (scopes insuficientes ou ação proibida). | **Não fazer refresh** (não resolve). Propagar/logar. |
| 404 | Not Found — recurso não existe. | Propagar; trate como dado vazio se aplicável. |
| 429 | Too Many Requests — rate limit. | Ler `Retry-After`, dormir, retry uma vez (ver §5). |
| 500 / 502 / 503 | Erro do lado do Spotify. | Propagar. Pode tentar retry com backoff exponencial. |

### 4.2 Formato de erro padrão (Web API)

Endpoints de dados (`api.spotify.com/v1/...`) retornam:

```json
{
  "error": {
    "status": 400,
    "message": "Invalid base62 id"
  }
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `error.status` | int | Espelha o HTTP status. |
| `error.message` | string | Descrição curta. **Inglês**, não localizado. |

### 4.3 Formato de erro do endpoint de auth (`accounts.spotify.com/api/token`)

Segue **RFC 6749** (OAuth 2.0), formato diferente:

```json
{
  "error": "invalid_client",
  "error_description": "Invalid client secret"
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `error` | string | Código padronizado RFC 6749 (ex.: `invalid_grant`, `invalid_client`, `invalid_request`). |
| `error_description` | string | Texto livre humano. |

**Códigos relevantes pro projeto:**
- `invalid_grant` — refresh token revogado ou expirado, ou code já usado. **Sinal de que o user precisa relogar**. Pode marcar `User.needs_reauth = True` (se adicionar esse campo) ou retornar `tracks: []` graciosamente.
- `invalid_client` — `SPOTIFY_CLIENT_SECRET` errado (bug de config nosso).
- `invalid_request` — body mal formado (bug nosso).

### 4.4 401: token expirado vs token revogado

**Spotify NÃO documenta diferença formal** — ambos retornam HTTP 401 no mesmo formato. A distinção tem que ser **comportamental**, não por status code:

| Cenário | Sintoma observável | Ação do wrapper |
|---|---|---|
| **Access token expirado** (caso comum) | 401 em endpoint de dados → refresh em `/api/token` retorna **200** com novos tokens. | Refresh automático + retry. Pré-check de expiração com margem de 30s evita maioria dos casos. |
| **Access token revogado** (raro — user desautorizou no painel Spotify) | 401 em endpoint de dados → refresh em `/api/token` retorna **400 `invalid_grant`**. | Não há recuperação automática. User precisa refazer login. Logar e retornar fallback (`tracks: []`). |
| **Access token inválido** (ex.: corrompido no DB) | 401 → refresh **funciona** mas próximo retry pode dar 401 de novo. | Mesma lógica de refresh + retry **uma única vez**. Sem loop. |

**Mensagens observáveis em 401** (pra log, não decisão de fluxo):
- `"The access token expired"` — caso de expiração natural.
- `"Invalid access token"` — corrompido/malformado.
- Outras variações possíveis.

> Regra prática do wrapper (§10 do roadmap): **sempre tente refresh em 401**. O sucesso ou falha do refresh é que diferencia expirado de revogado — não tente parsear `error.message`.

---

## 5. Rate limiting

Doc oficial: https://developer.spotify.com/documentation/web-api/concepts/rate-limits

### 5.1 Como funciona

- **Escopo:** por **app** (não por user). Todas as chamadas de todos os users do Kisco contam contra o mesmo limite.
- **Janela:** rolling de **30 segundos**.
- **Quota mode:**
  - **Development Mode** (default): limite mais baixo, suficiente pro desenvolvimento.
  - **Extended Quota Mode**: solicitação manual via Dashboard. Provável necessidade se o app crescer além de poucos usuários.
- **Limite numérico exato:** Spotify não publica. Geralmente está na casa de **180 requests/min** em modo dev, mas é informal — não dependa.

### 5.2 Resposta 429

- Status: **429 Too Many Requests**.
- Header: **`Retry-After`** com valor em **segundos** (inteiro).
- Body: pode estar vazio ou com `{"error": {"status": 429, "message": "..."}}`.

### 5.3 Estratégia recomendada no wrapper

```
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", "1"))
    await asyncio.sleep(retry_after)
    # retry uma vez
```

- **Não retry mais de 1×** sem backoff exponencial — pode entrar em loop.
- Em chamadas paralelas (`asyncio.gather` em `/users`), 429 pode afetar múltiplos users simultaneamente. `return_exceptions=True` no gather isola falhas.
- Pra v1 do projeto (6 users), 429 é improvável. Tratamento simples basta.

### 5.4 Mitigações estruturais (futuro)

- Cache local de respostas curtas (ex.: 30s).
- Batch endpoints quando disponíveis (não há pra recently-played).
- Solicitar Extended Quota se o app crescer.

---

## 6. Constantes derivadas para `app/constants.py`

A partir do que está documentado, valores prontos:

```python
# URLs base
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Scopes (separados por ESPAÇO, não vírgula)
SPOTIFY_SCOPES = "user-read-private user-read-recently-played"

# Limites duros da API
RECENTLY_PLAYED_MAX_LIMIT = 50

# Vida útil do access token (segundos) — pra cálculo de margem de refresh
ACCESS_TOKEN_TTL_SECONDS = 3600
TOKEN_REFRESH_MARGIN_SECONDS = 30

# Album alvo: "Kiss All The Time" (Disco Ocasionally)
ALBUM_ID = "69BqE1V8Bzb9GCyeP1fFeR"

# Quantidade de tracks por user no card
TRACKS_PER_USER = 5
```

---

## Links oficiais

- Web API home: https://developer.spotify.com/documentation/web-api
- Authorization Code Flow: https://developer.spotify.com/documentation/web-api/tutorials/code-flow
- Refreshing Tokens: https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
- Scopes: https://developer.spotify.com/documentation/web-api/concepts/scopes
- Rate limits: https://developer.spotify.com/documentation/web-api/concepts/rate-limits
- Get Current User's Profile: https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile
- Get Recently Played: https://developer.spotify.com/documentation/web-api/reference/get-recently-played
- Search: https://developer.spotify.com/documentation/web-api/reference/search
- Dashboard: https://developer.spotify.com/dashboard
