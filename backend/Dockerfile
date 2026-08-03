FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/app.db

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full runtime tree; exclusions live in .dockerignore so new packages
# (e.g. generation_jobs) are included without maintaining a fragile whitelist.
COPY . .

RUN mkdir -p /data && chown -R appuser:appuser /data /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["python", "docker_entrypoint.py"]
