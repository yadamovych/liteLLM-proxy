FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates openssl \
        libatomic1 \
        nodejs npm \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    "litellm[proxy,caching,extra-proxy]==1.88.1" \
    boto3 \
    prisma \
    hypercorn

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy package directories without trailing slash so they stay as subfolders under /app.
# (COPY foo/ ./ flattens contents into /app and types.py would shadow stdlib `types`.)
RUN PRISMA_DIR="$(python -c 'import os; from litellm.proxy.db import prisma_client as pc; print(os.path.dirname(os.path.dirname(pc.__file__)))')" \
    && cd "${PRISMA_DIR}" \
    && DATABASE_URL="postgresql://litellm:litellm@localhost:5432/litellm" python -m prisma generate

COPY bedrock_auto_router /app/bedrock_auto_router
COPY debug_summary_callback /app/debug_summary_callback
COPY litellm_config.yaml /app/

ENV LITELLM_MODE=PRODUCTION \
    PYTHONUNBUFFERED=1

EXPOSE 4000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--config", "/app/litellm_config.yaml", "--port", "4000"]
