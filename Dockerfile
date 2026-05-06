# syntax=docker/dockerfile:1
#
# Dockerfile para Crypto Tracker.
#
# Una sola imagen con tres entrypoints posibles:
#   - api:       FastAPI      → uvicorn src.api.server:app
#   - streamlit: Dashboard    → streamlit run app.py
#   - pipeline:  ETL cron job → crypto-tracker pipeline
#
# El docker-compose.yml orquesta ambos servicios.
#
# Uso directo (sin compose):
#   # API
#   docker build -t crypto-tracker .
#   docker run -p 8000:8000 crypto-tracker
#
#   # Streamlit (necesita la API ya corriendo)
#   docker run -p 8501:8501 \
#     -e API_BASE_URL=http://host.docker.internal:8000 \
#     crypto-tracker streamlit
#
#   # Pipeline (una vez)
#   docker run -e DATABASE_URL=... crypto-tracker pipeline

FROM python:3.12-slim

WORKDIR /app

# Copiar pyproject.toml + README.md (hatchling necesita el readme)
COPY pyproject.toml README.md ./
# Instalar en modo normal (no editable — en Docker no hace falta)
RUN pip install --no-cache-dir ".[dev,postgres]"

# Copiar el código fuente
COPY src/ src/
COPY app.py .
COPY tests/ tests/

# Puerto de la API (Streamlit usa 8501 por defecto)
EXPOSE 8000 8501

# Por defecto arranca la API.
# Usa $PORT si está definida (Render la asigna automáticamente),
# sino usa 8000 para desarrollo local.
CMD ["sh", "-c", "case ${ENTRYPOINT:-api} in \
  pipeline) crypto-tracker pipeline ;; \
  streamlit) streamlit run app.py ;; \
  *) uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8000} ;; \
esac"]
