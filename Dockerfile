FROM ghcr.io/astral-sh/uv:python3.13-bookworm


RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


COPY pyproject.toml uv.lock README.md ./


RUN uv sync  --no-dev 

COPY . .


CMD ["uv", "run", "main.py"]