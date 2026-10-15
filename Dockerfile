FROM python:3.12.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY app/ .
COPY chainlit.md .
COPY dbt_project/ /dbt_project/

RUN mkdir -p /data/chromadb

EXPOSE 80

CMD ["chainlit", "run", "chainlit_app.py", "--host", "0.0.0.0", "--port", "80"]
