# Imagen base ligera de Python
FROM python:3.11-slim

# Evitar que apt pida confirmaciones interactivas durante la compilación
ENV DEBIAN_FRONTEND=noninteractive

# Actualizar repositorios, ca-certificates e instalar Tesseract + OpenCV/GL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt-get/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la carpeta actual
COPY . .

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para iniciar la API en producción
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]