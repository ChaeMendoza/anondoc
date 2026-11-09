FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANONDOC_HOST=0.0.0.0 \
    ANONDOC_PORT=8000 \
    ANONDOC_TEMP_DIR=/tmp/anondoc

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY anondoc ./anondoc

# Usuario sin privilegios; el directorio temporal es privado (0700) y se purga al iniciar y al apagar.
RUN useradd -m -u 1001 anondocuser \
    && mkdir -p /tmp/anondoc \
    && chown -R anondocuser:anondocuser /tmp/anondoc \
    && chmod 700 /tmp/anondoc
USER 1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"]

CMD ["python", "-m", "anondoc.main"]
