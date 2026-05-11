# Imagem base com Python 3.11 enxuta.
FROM python:3.11-slim

# Copia o binario do uv de uma imagem oficial pre-buildada (rapido e confiavel).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copia so os manifests primeiro pra cachear o layer de deps.
# Mudancas no codigo nao invalidam o cache de instalacao.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copia o codigo da aplicacao.
COPY app ./app

# Variavel pra uv usar o ambiente que ele acabou de criar.
ENV PATH="/app/.venv/bin:$PATH"

# Porta que o uvicorn escuta dentro do container.
EXPOSE 8000

# Sobe o servidor escutando em todas as interfaces pra o Fly conseguir rotear.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
