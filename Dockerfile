FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    UV_VERSION=0.7.5 \
    NODE_MAJOR=24

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg ca-certificates && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN pip install "uv==${UV_VERSION}"

COPY pyproject.toml ./

RUN uv pip install --system .

COPY mineflayer_scripts/package.json ./mineflayer_scripts/
RUN cd mineflayer_scripts && \
    npm install

COPY . .

CMD ["python", "main.py"]