FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml backend/README* ./
COPY backend/intentguard ./intentguard
RUN pip install --no-cache-dir .

# app.py resolves the dashboard at <root>/frontend; in the image the package
# lives at /app/intentguard, so the root is /
COPY frontend /frontend
COPY backend/scripts ./scripts

ENV INTENTGUARD_HOST=0.0.0.0 \
    INTENTGUARD_PORT=8400 \
    INTENTGUARD_STORE=sqlite \
    INTENTGUARD_SQLITE_PATH=/data/intentguard.db

VOLUME ["/data"]
EXPOSE 8400

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"INTENTGUARD_PORT\"]}/health')" || exit 1

CMD ["python", "-m", "uvicorn", "--factory", "intentguard.api.app:create_app", \
     "--host", "0.0.0.0", "--port", "8400"]
