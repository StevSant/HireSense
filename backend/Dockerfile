FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-fonts-recommended texlive-fonts-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "hiresense.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
