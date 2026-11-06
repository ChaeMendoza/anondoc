FROM python:3.12-slim

# Evitar prompts y configurar buffers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANONDOC_HOST=0.0.0.0 \
    ANONDOC_PORT=8000 \
    ANONDOC_TEMP_DIR=/tmp/anondoc

WORKDIR /app

# Instalar dependencias del sistema requeridas para PyMuPDF y LibreOffice (conversión complementaria)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorio de trabajo temporal no privilegiado
RUN mkdir -p /tmp/anondoc && useradd -m -u 1001 anondocuser && chown -R anondocuser:anondocuser /app /tmp/anondoc
USER anondocuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "-m", "anondoc.main"]
