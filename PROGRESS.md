# Kisco Backend — Progresso

## Fase A — Setup

- [x] Instalar Python e confirmar versão
- [x] Instalar gerenciador de dependências
- [x] Criar repo e inicializar git
- [x] Configurar `.gitignore`
- [x] Criar `.env` e `.env.example`
- [x] Gerar segredo de sessão
- [x] Criar ambiente virtual
- [x] Instalar dependências do projeto
- [x] Cadastrar Redirect URI no Spotify
- [x] Fazer primeiro commit

## Fase B — Esqueleto Python

- [x] Criar estrutura de pastas
- [x] Criar arquivos `__init__.py`
- [x] Criar arquivos vazios dos módulos
- [x] Preencher `app/constants.py`
- [x] Preencher `app/config.py`
- [x] Validar config com smoke test
- [x] Definir modelo `User` em `app/models.py`
- [x] Preencher `app/db.py` com engine e session
- [x] Preencher `app/main.py` mínimo com `/health`
- [x] Subir o servidor local
- [x] Confirmar criação automática do banco

## Fase C — Cliente Spotify "burro"

- [x] Implementar troca de code por tokens
- [x] Implementar refresh de access token
- [x] Implementar busca do perfil do usuário
- [x] Implementar busca do histórico recente
- [x] Garantir cliente puro sem deps internas
- [x] Smoke test manual de cada função

## Fase D — Rotas de auth

- [ ] Criar router de autenticação
- [ ] Implementar início do fluxo OAuth
- [ ] Implementar callback do OAuth
- [ ] Registrar router no app
- [ ] Testar fluxo manual end-to-end

## Fase E — Album discovery

- [x] Decidir álbum alvo
- [x] Descobrir ID do álbum
- [x] Persistir ID nas constantes

## Fase F — Wrapper de token

- [ ] Implementar wrapper com refresh e retry
- [ ] Implementar busca de tracks do álbum por usuário
- [ ] Tratar revogação de token no refresh

## Fase G — Endpoint `/users`

- [ ] Criar router de usuários
- [ ] Implementar listagem agregada de usuários
- [ ] Registrar router no app
- [ ] Configurar CORS
- [ ] Validar shape do JSON

## Fase H — Integração com frontend Next.js

- [ ] Criar `.env.local` no frontend
- [ ] Atualizar página de login para apontar ao backend
- [ ] Substituir mock da homepage por fetch real
- [ ] Renderizar lista de usuários com tratamento de erro
- [ ] Conferir contrato de props do `UserCard`

## Fase I — Verificação end-to-end e deploy

- [ ] Validar fluxo de login completo
- [ ] Validar renderização da homepage
- [ ] Validar cenário multi-usuário
- [ ] Validar refresh forçado de token
- [ ] Validar tratamento de revogação
- [ ] Validar erro de state mismatch
- [ ] Validar CORS entre frontend e backend
- [ ] Validar persistência após reinício
- [ ] Decidir plataforma de deploy
- [ ] Migrar banco para Postgres
- [ ] Cadastrar Redirect URI de produção
- [ ] Atualizar variáveis de ambiente de produção
- [ ] Fazer deploy e testar em produção

---

## Próximo passo

Abrir `app/models.py`.
