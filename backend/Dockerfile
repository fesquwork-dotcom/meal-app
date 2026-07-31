FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/app.db

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Python modules at package root
COPY *.py ./

# Domain packages
COPY strategy ./strategy/
COPY shopping ./shopping/
COPY memory ./memory/
COPY behavior ./behavior/
COPY decision ./decision/
COPY learning ./learning/
COPY learned_preferences ./learned_preferences/
COPY insights ./insights/
COPY trends ./trends/
COPY menu_plan ./menu_plan/
COPY plan_delta ./plan_delta/
COPY dev_tools ./dev_tools/

RUN mkdir -p /data && chown -R appuser:appuser /data /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["python", "docker_entrypoint.py"]
