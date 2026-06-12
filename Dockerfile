FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates openssl \
        libatomic1 \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    "litellm[proxy,caching,extra-proxy]==1.88.1" \
    boto3 \
    prisma \
    hypercorn

COPY bedrock_auto_router/ debug_summary_callback/ vscode_context.py litellm_config.yaml ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Prisma CLI (via prisma-python/nodeenv) needs libatomic + node; generate once at build.
RUN PRISMA_DIR="$(python -c 'import os; from litellm.proxy.db import prisma_client as pc; print(os.path.dirname(os.path.dirname(pc.__file__)))')" \
    && cd "${PRISMA_DIR}" \
    && DATABASE_URL="postgresql://litellm:litellm@localhost:5432/litellm" python -m prisma generate

ENV LITELLM_MODE=PRODUCTION \
    PYTHONUNBUFFERED=1

EXPOSE 4000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--config", "/app/litellm_config.yaml", "--port", "4000"]
